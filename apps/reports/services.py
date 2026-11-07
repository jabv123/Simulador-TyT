from __future__ import annotations

from decimal import Decimal

from django.db.models import (
    Avg,
    Case,
    CharField,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, ExtractMonth, ExtractYear, NullIf

from apps.attempts.models import EstadoIntento, RespuestaIntento
from apps.quizzes.models import CuestionarioPregunta

from .selectors import filter_intentos


def normalizar_filtros(filtros):
    if filtros is None:
        return {}
    if hasattr(filtros, "get"):
        return filtros
    if hasattr(filtros, "cleaned_data"):
        return filtros.cleaned_data
    return dict(filtros)


def aplicar_filtros(queryset, filtros):
    return filter_intentos(queryset, normalizar_filtros(filtros))


def calificacion_sobre_cinco(calificacion, maxima):
    if calificacion is None or not maxima:
        return None
    return (calificacion / maxima * Decimal("5")).quantize(Decimal("0.01"))


def expresion_nota_sobre_cinco():
    return ExpressionWrapper(
        F("calificacion_final")
        * Value(Decimal("5"))
        / F("cuestionario__calificacion_maxima"),
        output_field=DecimalField(max_digits=8, decimal_places=4),
    )


def obtener_kpis(queryset):
    finalizados = queryset.filter(
        estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO]
    )
    total_intentos = finalizados.count()
    estudiantes_distintos = finalizados.values("usuario_id").distinct().count()
    nota_normalizada = expresion_nota_sobre_cinco()
    agregados = finalizados.aggregate(
        promedio=Avg(nota_normalizada),
        minima=Min(nota_normalizada),
        maxima=Max(nota_normalizada),
    )
    promedio = agregados["promedio"]
    if promedio is None:
        promedio = Decimal("0")
    nota_minima = agregados["minima"]
    nota_maxima = agregados["maxima"]
    total_aprobados = finalizados.filter(
        calificacion_final__gte=F("cuestionario__calificacion_aprobacion")
    ).count()
    total_no_aprobados = total_intentos - total_aprobados
    porcentaje_aprobacion = (
        (Decimal(total_aprobados) / Decimal(total_intentos) * Decimal("100"))
        if total_intentos
        else Decimal("0")
    )
    return {
        "estudiantes_distintos": estudiantes_distintos,
        "intentos_finalizados": total_intentos,
        "promedio": promedio,
        "nota_minima": nota_minima,
        "nota_maxima": nota_maxima,
        "porcentaje_aprobacion": porcentaje_aprobacion,
        "aprobados": total_aprobados,
        "no_aprobados": total_no_aprobados,
    }


def obtener_tabla_resultados(
    queryset,
    *,
    page_size=None,
    page=None,
    order_by="-fecha_fin",
    order_dir="desc",
    include_identificacion=True,
):
    orden_map = {
        "usuario": "usuario__nombre",
        "identificacion": "usuario__codigo",
        "curso": "grupo_snapshot__curso__nombre",
        "grupo": "grupo_snapshot__nombre",
        "simulacro": "cuestionario__nombre",
        "fecha": "fecha_fin",
        "nota": "nota_sobre_cinco",
        "estado": "estado",
    }

    campo = orden_map.get(order_by, "-fecha_fin")
    if order_dir == "asc":
        if campo.startswith("-"):
            campo = campo[1:]
    elif order_dir == "desc" and not campo.startswith("-"):
        campo = f"-{campo}"

    registros_queryset = (
        queryset.filter(
            estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO]
        )
        .select_related("cuestionario", "usuario")
        .select_related("grupo_snapshot__curso")
    )
    if order_by == "nota":
        registros_queryset = registros_queryset.annotate(
            nota_sobre_cinco=expresion_nota_sobre_cinco()
        )
    registros = list(
        registros_queryset.order_by(campo, "-fecha_fin", "-calificacion_final")
    )

    total = len(registros)
    if page_size:
        page_size = int(page_size)
        page = max(1, int(page or 1))
        inicio = (page - 1) * page_size
        fin = inicio + page_size
        registros = registros[inicio:fin]
        total_paginas = max(1, (total + page_size - 1) // page_size) if total else 1
    else:
        page = 1
        total_paginas = 1

    items = []
    for item in registros:
        grupo = item.grupo_snapshot
        aprobado = (
            item.calificacion_final is not None
            and item.calificacion_final >= item.cuestionario.calificacion_aprobacion
        )
        items.append(
            {
                "usuario": item.usuario.nombre,
                "identificacion": (
                    item.usuario.codigo if include_identificacion else ""
                ),
                "curso": (
                    item.curso_nombre_snapshot
                    or (grupo.curso.nombre if grupo else "Sin curso")
                ),
                "grupo": (
                    item.grupo_nombre_snapshot
                    or (grupo.nombre if grupo else "Sin grupo")
                ),
                "simulacro": item.cuestionario.nombre,
                "fecha": item.fecha_fin.isoformat() if item.fecha_fin else None,
                "nota": calificacion_sobre_cinco(
                    item.calificacion_final,
                    item.cuestionario.calificacion_maxima,
                ),
                "nota_original": item.calificacion_final,
                "calificacion_maxima": item.cuestionario.calificacion_maxima,
                "estado": "Aprobado" if aprobado else "No aprobado",
                "estado_intento": item.get_estado_display(),
            }
        )

    if page_size:
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_paginas": total_paginas,
        }
    return {"items": items, "page": 1, "page_size": total, "total": total, "total_paginas": 1}


def obtener_resumen_agregado(
    queryset,
    tipo="general",
    *,
    eje=None,
    contextual=False,
    include_identificacion=True,
):
    base = queryset.filter(
        estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO]
    )

    if tipo == "curso":
        qs = base.values("cuestionario_id", "cuestionario__nombre").annotate(
            intentos=Count("id"),
            estudiantes=Count("usuario_id", distinct=True),
            aprobados=Count(
                "id",
                filter=Q(calificacion_final__gte=F("cuestionario__calificacion_aprobacion")),
            ),
            promedio=Avg(expresion_nota_sobre_cinco()),
            nota_minima=Min(expresion_nota_sobre_cinco()),
            nota_maxima=Max(expresion_nota_sobre_cinco()),
        )
        return [
            {
                "id": item["cuestionario_id"],
                "nombre": item["cuestionario__nombre"],
                "intentos": item["intentos"],
                "estudiantes": item["estudiantes"],
                "aprobados": item["aprobados"],
                "promedio": item["promedio"],
            }
            for item in qs.order_by("-intentos", "-promedio")
        ]

    if tipo == "curso_grupo":
        qs = base.values(
            "grupo_snapshot_id",
            "grupo_snapshot__nombre",
            "grupo_snapshot__curso_id",
            "grupo_snapshot__curso__nombre",
            "curso_nombre_snapshot",
            "grupo_nombre_snapshot",
        ).annotate(
            intentos=Count("id"),
            estudiantes=Count("usuario_id", distinct=True),
            aprobados=Count(
                "id",
                filter=Q(calificacion_final__gte=F("cuestionario__calificacion_aprobacion")),
            ),
            promedio=Avg(expresion_nota_sobre_cinco()),
            nota_minima=Min(expresion_nota_sobre_cinco()),
            nota_maxima=Max(expresion_nota_sobre_cinco()),
        )
        return [
            {
                "id": item["grupo_snapshot_id"],
                "curso_id": item["grupo_snapshot__curso_id"],
                "curso": (
                    item["curso_nombre_snapshot"]
                    or item["grupo_snapshot__curso__nombre"]
                    or "Sin curso"
                ),
                "grupo": (
                    item["grupo_nombre_snapshot"]
                    or item["grupo_snapshot__nombre"]
                    or "Sin grupo"
                ),
                "nombre": (
                    f"{item['curso_nombre_snapshot'] or item['grupo_snapshot__curso__nombre']} / "
                    f"{item['grupo_nombre_snapshot'] or item['grupo_snapshot__nombre']}"
                    if item["grupo_snapshot_id"]
                    else "Sin curso / sin grupo"
                ),
                "intentos": item["intentos"],
                "estudiantes": item["estudiantes"],
                "aprobados": item["aprobados"],
                "no_aprobados": item["intentos"] - item["aprobados"],
                "promedio": item["promedio"],
                "nota_minima": item["nota_minima"],
                "nota_maxima": item["nota_maxima"],
            }
            for item in qs.order_by("-intentos", "grupo_snapshot__curso__nombre", "grupo_snapshot__nombre")
        ]

    if tipo == "estudiante":
        qs = base.values("usuario_id", "usuario__nombre", "usuario__codigo").annotate(
            intentos=Count("id"),
            promedio=Avg(expresion_nota_sobre_cinco()),
            aprobados=Count(
                "id",
                filter=Q(calificacion_final__gte=F("cuestionario__calificacion_aprobacion")),
            ),
        )
        return [
            {
                "id": item["usuario_id"],
                "nombre": item["usuario__nombre"],
                "identificacion": (
                    item["usuario__codigo"] if include_identificacion else ""
                ),
                "intentos": item["intentos"],
                "aprobados": item["aprobados"],
                "promedio": item["promedio"],
            }
            for item in qs.order_by("-promedio", "-intentos")
        ]

    if tipo == "eje":
        return obtener_desempeno_ejes(base, eje=eje, contextual=contextual)

    if tipo == "periodo":
        return obtener_resumen_periodos(base)

    if tipo == "dificultad":
        return obtener_preguntas_dificiles(base, eje=eje)

    top_cursos = obtener_resumen_agregado(base, "curso_grupo")[:5]
    top_estudiantes = obtener_resumen_agregado(
        base,
        "estudiante",
        include_identificacion=include_identificacion,
    )[:5]
    top_ejes = obtener_resumen_agregado(base, "eje", eje=eje)[:5]

    mejor_curso = top_cursos[0] if top_cursos else None
    peor_curso = sorted(top_cursos, key=lambda item: item["promedio"] or 0)[0] if top_cursos else None
    mejor_eje = top_ejes[0] if top_ejes else None
    peor_eje = sorted(top_ejes, key=lambda item: item["promedio"] or 0)[0] if top_ejes else None

    return {
        "kpis": obtener_kpis(base),
        "top_cursos": top_cursos,
        "top_estudiantes": top_estudiantes,
        "top_ejes": top_ejes,
        "mejor_curso": mejor_curso,
        "peor_curso": peor_curso,
        "mejor_eje": mejor_eje,
        "peor_eje": peor_eje,
    }


def obtener_resumen_periodos(queryset):
    base = queryset.filter(
        estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO],
        cuestionario__fecha_apertura__isnull=False,
    ).annotate(
        anio_apertura=ExtractYear("cuestionario__fecha_apertura"),
        mes_apertura=ExtractMonth("cuestionario__fecha_apertura"),
    )
    qs = (
        base.annotate(
            periodo_numero=Case(
                When(mes_apertura__lte=6, then=Value(1)),
                default=Value(2),
            )
        )
        .values("anio_apertura", "periodo_numero")
        .annotate(
            evaluaciones=Count("cuestionario_id", distinct=True),
            intentos=Count("id"),
            estudiantes=Count("usuario_id", distinct=True),
            promedio=Avg(expresion_nota_sobre_cinco()),
        )
        .order_by("-anio_apertura", "periodo_numero")
    )
    return [
        {
            "anio": item["anio_apertura"],
            "periodo": item["periodo_numero"],
            "periodo_nombre": f"{item['periodo_numero']}° semestre",
            "evaluaciones": item["evaluaciones"],
            "intentos": item["intentos"],
            "estudiantes": item["estudiantes"],
            "promedio": item["promedio"],
        }
        for item in qs
    ]


def _resumen_respuestas_por_eje(queryset):
    intentos_finalizados = queryset.filter(
        estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO]
    )
    puntaje_configurado = CuestionarioPregunta.objects.filter(
        cuestionario_id=OuterRef("intento__cuestionario_id"),
        pregunta_id=OuterRef("pregunta_id"),
    ).values("puntaje")[:1]
    puntaje_obtenido = Case(
        When(es_correcta=True, then=F("puntaje_posible")),
        default=Value(Decimal("0")),
        output_field=DecimalField(max_digits=7, decimal_places=2),
    )
    return (
        RespuestaIntento.objects.filter(
            intento__in=intentos_finalizados,
            pregunta__categoria__isnull=False,
            opcion_seleccionada__isnull=False,
        )
        .annotate(puntaje_posible=Subquery(puntaje_configurado))
        .filter(puntaje_posible__isnull=False)
    ), puntaje_obtenido


def obtener_desempeno_ejes(queryset, *, eje=None, contextual=False):
    respuestas, puntaje_obtenido = _resumen_respuestas_por_eje(queryset)
    if eje:
        respuestas = respuestas.filter(pregunta__categoria_id=eje)
    campos_agrupacion = [
        "pregunta__categoria_id",
        "pregunta__categoria__nombre",
    ]
    if contextual:
        respuestas = respuestas.annotate(
            anio=ExtractYear("intento__cuestionario__fecha_apertura"),
            mes=ExtractMonth("intento__cuestionario__fecha_apertura"),
            curso=Coalesce(
                NullIf(
                    F("intento__curso_nombre_snapshot"),
                    Value(""),
                ),
                F("intento__grupo_snapshot__curso__nombre"),
                Value("Sin curso"),
                output_field=CharField(),
            ),
            periodo_numero=Case(
                When(mes__isnull=True, then=Value(None)),
                When(mes__lte=6, then=Value(1)),
                default=Value(2),
            ),
        )
        campos_agrupacion = [
            "anio",
            "periodo_numero",
            "curso",
            *campos_agrupacion,
        ]
    filas = (
        respuestas.values(*campos_agrupacion)
        .annotate(
            preguntas=Count("pregunta_id", distinct=True),
            preguntas_respondidas=Count("id"),
            respuestas_correctas=Count("id", filter=Q(es_correcta=True)),
            puntaje_obtenido=Sum(puntaje_obtenido),
            puntaje_posible=Sum("puntaje_posible"),
        )
        .order_by("pregunta__categoria__nombre")
    )
    resultado = []
    for item in filas:
        total = item["preguntas_respondidas"]
        correctas = item["respuestas_correctas"]
        posible = item["puntaje_posible"] or Decimal("0")
        nota = (
            (item["puntaje_obtenido"] or Decimal("0")) / posible * Decimal("5")
            if posible
            else None
        )
        fila = {
                "id": item["pregunta__categoria_id"],
                "nombre": item["pregunta__categoria__nombre"],
                "preguntas": item["preguntas"],
                "preguntas_respondidas": total,
                "respuestas_correctas": correctas,
                "errores": total - correctas,
                "porcentaje_aciertos": (
                    Decimal(correctas) / Decimal(total) * Decimal("100")
                    if total
                    else Decimal("0")
                ),
                "nota": nota,
                "promedio": nota,
            }
        if contextual:
            fila.update(
                {
                    "anio": item["anio"] or "",
                    "periodo": (
                        f"{item['periodo_numero']}° semestre"
                        if item["periodo_numero"]
                        else ""
                    ),
                    "curso": item["curso"],
                }
            )
        resultado.append(fila)
    if contextual:
        return sorted(
            resultado,
            key=lambda item: (
                str(item["anio"]),
                item["periodo"],
                item["curso"],
                item["nombre"],
            ),
        )
    return sorted(
        resultado,
        key=lambda item: item["porcentaje_aciertos"],
        reverse=True,
    )


def obtener_preguntas_dificiles(queryset, *, eje=None):
    respuestas, _ = _resumen_respuestas_por_eje(queryset)
    if eje:
        respuestas = respuestas.filter(pregunta__categoria_id=eje)
    filas = (
        respuestas.values(
            "pregunta_id",
            "pregunta__enunciado",
            "pregunta__categoria_id",
            "pregunta__categoria__nombre",
        )
        .annotate(
            total_respuestas=Count("id"),
            respuestas_correctas=Count("id", filter=Q(es_correcta=True)),
        )
        .order_by("respuestas_correctas", "pregunta_id")
    )
    resultado = []
    for item in filas:
        total = item["total_respuestas"]
        correctas = item["respuestas_correctas"]
        resultado.append(
            {
                "id": item["pregunta_id"],
                "pregunta": item["pregunta__enunciado"],
                "eje_id": item["pregunta__categoria_id"],
                "eje": item["pregunta__categoria__nombre"],
                "total_respuestas": total,
                "errores": total - correctas,
                "porcentaje_aciertos": (
                    Decimal(correctas) / Decimal(total) * Decimal("100")
                    if total
                    else Decimal("0")
                ),
            }
        )
    return sorted(
        resultado,
        key=lambda item: (item["porcentaje_aciertos"], -item["errores"], item["id"]),
    )


def obtener_historial_individual(queryset, *, eje=None):
    respuestas_filtro = Q(respuestas__opcion_seleccionada__isnull=False)
    if eje:
        respuestas_filtro &= Q(respuestas__pregunta__categoria_id=eje)
    intentos = (
        queryset.filter(
            estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO]
        )
        .select_related("cuestionario", "grupo_snapshot__curso")
        .annotate(
            preguntas_respondidas=Count(
                "respuestas",
                filter=respuestas_filtro,
                distinct=True,
            ),
            aciertos=Count(
                "respuestas",
                filter=respuestas_filtro & Q(respuestas__es_correcta=True),
                distinct=True,
            ),
        )
        .order_by("fecha_fin", "pk")
    )
    historial = []
    nota_anterior = None
    for intento in intentos:
        nota = calificacion_sobre_cinco(
            intento.calificacion_final,
            intento.cuestionario.calificacion_maxima,
        )
        historial.append(
            {
                "intento_id": intento.pk,
                "estudiante": intento.usuario.nombre,
                "simulacro": intento.cuestionario.nombre,
                "anio": (
                    intento.cuestionario.fecha_apertura.year
                    if intento.cuestionario.fecha_apertura
                    else ""
                ),
                "periodo": (
                    "1° semestre"
                    if intento.cuestionario.fecha_apertura
                    and intento.cuestionario.fecha_apertura.month <= 6
                    else "2° semestre"
                    if intento.cuestionario.fecha_apertura
                    else ""
                ),
                "curso": (
                    intento.curso_nombre_snapshot
                    or (
                        intento.grupo_snapshot.curso.nombre
                        if intento.grupo_snapshot_id
                        else "Sin curso"
                    )
                ),
                "grupo": (
                    intento.grupo_nombre_snapshot
                    or (
                        intento.grupo_snapshot.nombre
                        if intento.grupo_snapshot_id
                        else "Sin grupo"
                    )
                ),
                "fecha": intento.fecha_fin,
                "preguntas_respondidas": intento.preguntas_respondidas,
                "aciertos": intento.aciertos,
                "errores": intento.preguntas_respondidas - intento.aciertos,
                "nota": nota,
                "cambio": nota - nota_anterior if nota is not None and nota_anterior is not None else None,
                "estado": (
                    "Aprobado"
                    if intento.calificacion_final is not None
                    and intento.calificacion_final
                    >= intento.cuestionario.calificacion_aprobacion
                    else "No aprobado"
                ),
            }
        )
        nota_anterior = nota
    return historial
