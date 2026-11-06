from __future__ import annotations

import calendar
from datetime import datetime
from decimal import Decimal

from django.db.models import Avg, Count, F, Max, Min, Q

from apps.attempts.models import EstadoIntento

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


def obtener_kpis(queryset):
    finalizados = queryset.filter(
        estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO]
    )
    total_intentos = finalizados.count()
    estudiantes_distintos = finalizados.values("usuario_id").distinct().count()
    promedio = finalizados.aggregate(promedio=Avg("calificacion_final"))["promedio"]
    if promedio is None:
        promedio = Decimal("0")
    nota_minima = finalizados.aggregate(minima=Min("calificacion_final"))["minima"]
    nota_maxima = finalizados.aggregate(maxima=Max("calificacion_final"))["maxima"]
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
):
    orden_map = {
        "usuario": "usuario__nombre",
        "identificacion": "usuario__codigo",
        "curso": "cuestionario__nombre",
        "simulacro": "cuestionario__nombre",
        "fecha": "fecha_fin",
        "nota": "calificacion_final",
        "estado": "estado",
    }

    campo = orden_map.get(order_by, "-fecha_fin")
    if order_dir == "asc":
        if campo.startswith("-"):
            campo = campo[1:]
    elif order_dir == "desc" and not campo.startswith("-"):
        campo = f"-{campo}"

    registros = list(
        queryset.filter(
            estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO]
        )
        .select_related("cuestionario", "usuario")
        .order_by(campo, "-fecha_fin", "-calificacion_final")
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

    items = [
        {
            "usuario": item.usuario.nombre,
            "identificacion": item.usuario.codigo,
            "curso": item.cuestionario.nombre,
            "simulacro": item.cuestionario.nombre,
            "fecha": item.fecha_fin.isoformat() if item.fecha_fin else None,
            "nota": item.calificacion_final,
            "estado": item.get_estado_display(),
        }
        for item in registros
    ]

    if page_size:
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_paginas": total_paginas,
        }
    return {"items": items, "page": 1, "page_size": total, "total": total, "total_paginas": 1}


def obtener_resumen_agregado(queryset, tipo="general"):
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
            promedio=Avg("calificacion_final"),
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

    if tipo == "estudiante":
        qs = base.values("usuario_id", "usuario__nombre", "usuario__codigo").annotate(
            intentos=Count("id"),
            promedio=Avg("calificacion_final"),
            aprobados=Count(
                "id",
                filter=Q(calificacion_final__gte=F("cuestionario__calificacion_aprobacion")),
            ),
        )
        return [
            {
                "id": item["usuario_id"],
                "nombre": item["usuario__nombre"],
                "identificacion": item["usuario__codigo"],
                "intentos": item["intentos"],
                "aprobados": item["aprobados"],
                "promedio": item["promedio"],
            }
            for item in qs.order_by("-promedio", "-intentos")
        ]

    if tipo == "eje":
        qs = base.filter(respuestas__pregunta__categoria__isnull=False).values(
            "respuestas__pregunta__categoria_id",
            "respuestas__pregunta__categoria__nombre",
        ).annotate(
            preguntas=Count("respuestas__pregunta_id", distinct=True),
            intentos=Count("id", distinct=True),
            promedio=Avg("calificacion_final"),
        )
        return [
            {
                "id": item["respuestas__pregunta__categoria_id"],
                "nombre": item["respuestas__pregunta__categoria__nombre"],
                "preguntas": item["preguntas"],
                "intentos": item["intentos"],
                "promedio": item["promedio"],
            }
            for item in qs.order_by("-promedio")
        ]

    top_cursos = obtener_resumen_agregado(base, "curso")[:5]
    top_estudiantes = obtener_resumen_agregado(base, "estudiante")[:5]
    top_ejes = obtener_resumen_agregado(base, "eje")[:5]

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
