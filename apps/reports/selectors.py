from __future__ import annotations

import calendar
from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.attempts.models import Intento
from apps.questions.models import Categoria
from apps.quizzes.models import Cuestionario

PERIODO_SEMESTRES = {
    "1": (1, 6),
    "2": (7, 12),
}


def normalizar_periodo(valor):
    if valor in (None, ""):
        return ""
    periodo = str(valor).strip()
    if periodo.lower() in {"todos", "all", "-"}:
        return ""
    if "-" in periodo:
        _, sem = periodo.rsplit("-", 1)
        periodo = sem.split("°", 1)[0].strip()
    return periodo


def periodo_a_mes_rango(periodo):
    periodo = normalizar_periodo(periodo)
    if periodo in PERIODO_SEMESTRES:
        return PERIODO_SEMESTRES[periodo]
    return None


def periodo_a_rango_fechas(periodo, anio=None):
    rango = periodo_a_mes_rango(periodo)
    if rango is None or anio is None:
        return None
    inicio_mes, fin_mes = rango
    inicio = timezone.make_aware(datetime(int(anio), inicio_mes, 1, 0, 0, 0))
    ultimo_dia = calendar.monthrange(int(anio), fin_mes)[1]
    fin = timezone.make_aware(datetime(int(anio), fin_mes, ultimo_dia, 23, 59, 59))
    return inicio, fin


def get_base_intento_queryset():
    return Intento.objects.select_related("cuestionario", "usuario")


def filter_intentos(queryset, filtros):
    if filtros is None:
        return queryset
    if hasattr(filtros, "get"):
        filtros = filtros
    elif hasattr(filtros, "cleaned_data"):
        filtros = filtros.cleaned_data
    else:
        filtros = dict(filtros)

    if not filtros:
        return queryset

    if "anio" in filtros and filtros["anio"] not in (None, ""):
        queryset = queryset.filter(cuestionario__fecha_apertura__year=filtros["anio"])
    if "periodo" in filtros and filtros["periodo"] not in (None, ""):
        periodo = str(filtros["periodo"]).strip()
        if periodo:
            if periodo in {"1", "2"}:
                inicio_mes, fin_mes = {"1": (1, 6), "2": (7, 12)}[periodo]
                anio = filtros.get("anio")
                if anio is not None:
                    inicio = timezone.make_aware(datetime(int(anio), inicio_mes, 1, 0, 0, 0))
                    ultimo_dia = calendar.monthrange(int(anio), fin_mes)[1]
                    fin = timezone.make_aware(datetime(int(anio), fin_mes, ultimo_dia, 23, 59, 59))
                    queryset = queryset.filter(
                        cuestionario__fecha_apertura__gte=inicio,
                        cuestionario__fecha_apertura__lte=fin,
                    )
                else:
                    ids = []
                    for intento in queryset.select_related("cuestionario"):
                        fecha = getattr(intento.cuestionario, "fecha_apertura", None)
                        if fecha is not None and inicio_mes <= fecha.month <= fin_mes:
                            ids.append(intento.pk)
                    queryset = queryset.filter(pk__in=ids)
    if "curso" in filtros and filtros["curso"] not in (None, ""):
        queryset = queryset.filter(cuestionario_id=filtros["curso"])
    if "eje" in filtros and filtros["eje"] not in (None, ""):
        queryset = queryset.filter(respuestas__pregunta__categoria_id=filtros["eje"]).distinct()
    if "estudiante" in filtros and filtros["estudiante"] not in (None, ""):
        queryset = queryset.filter(usuario_id=filtros["estudiante"])
    if "usuario" in filtros and filtros["usuario"] not in (None, ""):
        queryset = queryset.filter(usuario_id=filtros["usuario"])
    if "docente" in filtros and filtros["docente"] not in (None, ""):
        queryset = queryset.filter(cuestionario__docente_id=filtros["docente"])
    if "estado" in filtros and filtros["estado"] not in (None, ""):
        queryset = queryset.filter(estado=filtros["estado"])
    if "query" in filtros and filtros["query"] not in (None, ""):
        texto = str(filtros["query"]).strip()
        if texto:
            queryset = queryset.filter(
                Q(usuario__nombre__icontains=texto)
                | Q(usuario__codigo__icontains=texto)
                | Q(cuestionario__nombre__icontains=texto)
            )
    return queryset


def get_anios_disponibles():
    anios = {
        cuestionario.fecha_apertura.year
        for cuestionario in Cuestionario.objects.exclude(fecha_apertura__isnull=True).only("fecha_apertura")
        if cuestionario.fecha_apertura is not None
    }
    return sorted(anios, reverse=True)


def get_periodos_disponibles(anio=None):
    qs = Cuestionario.objects.exclude(fecha_apertura__isnull=True)
    if anio:
        qs = qs.filter(fecha_apertura__year=anio)
    meses = {
        cuestionario.fecha_apertura.month
        for cuestionario in qs.only("fecha_apertura")
        if cuestionario.fecha_apertura is not None
    }
    periodos = []
    for numero in ["1", "2"]:
        inicio, fin = PERIODO_SEMESTRES[numero]
        if any(inicio <= mes <= fin for mes in meses):
            periodos.append({"value": numero, "label": f"{numero}° semestre"})
    return periodos


def get_cursos_disponibles(anio=None, periodo=None):
    qs = Cuestionario.objects.exclude(fecha_apertura__isnull=True)
    if anio:
        qs = qs.filter(fecha_apertura__year=anio)
    if periodo:
        rango = periodo_a_mes_rango(periodo)
        if rango is not None and anio:
            fechas = periodo_a_rango_fechas(periodo, anio)
            if fechas is not None:
                inicio, fin = fechas
                qs = qs.filter(fecha_apertura__gte=inicio, fecha_apertura__lte=fin)
        elif rango is not None:
            cursos = []
            for cuestionario in qs.only("id", "nombre", "fecha_apertura"):
                if cuestionario.fecha_apertura is not None and rango[0] <= cuestionario.fecha_apertura.month <= rango[1]:
                    cursos.append({"id": cuestionario.id, "nombre": cuestionario.nombre})
            return cursos
    return list(qs.order_by("nombre").values("id", "nombre"))


def get_ejes_disponibles(anio=None, periodo=None, curso=None):
    qs = Categoria.objects.filter(estado="Activo")
    if curso:
        qs = qs.filter(preguntas__cuestionarios__id=curso).distinct()
    elif anio:
        qs = qs.filter(preguntas__cuestionarios__fecha_apertura__year=anio).distinct()
    if periodo:
        rango = periodo_a_mes_rango(periodo)
        if rango is not None and anio:
            fechas = periodo_a_rango_fechas(periodo, anio)
            if fechas is not None:
                inicio, fin = fechas
                qs = qs.filter(
                    preguntas__cuestionarios__fecha_apertura__gte=inicio,
                    preguntas__cuestionarios__fecha_apertura__lte=fin,
                ).distinct()
        elif rango is not None:
            categorias = []
            for categoria in qs.only("id", "nombre"):
                fechas = [
                    cuestionario.fecha_apertura
                    for cuestionario in categoria.preguntas.values_list("cuestionarios__fecha_apertura", flat=True)
                    if cuestionario is not None
                ]
                if any(rango[0] <= fecha.month <= rango[1] for fecha in fechas):
                    categorias.append({"id": categoria.id, "nombre": categoria.nombre})
            return categorias
    return list(qs.order_by("nombre").values("id", "nombre"))


def get_estudiantes_disponibles(curso=None, texto=None, anio=None, periodo=None):
    qs = Usuario.objects.filter(rol__nombre__iexact="Estudiante", estado="ACTIVO")
    if curso:
        qs = qs.filter(intentos__cuestionario_id=curso).distinct()
    if anio:
        qs = qs.filter(intentos__cuestionario__fecha_apertura__year=anio).distinct()
    if periodo:
        rango = periodo_a_mes_rango(periodo)
        if rango is not None and anio:
            fechas = periodo_a_rango_fechas(periodo, anio)
            if fechas is not None:
                inicio, fin = fechas
                qs = qs.filter(
                    intentos__cuestionario__fecha_apertura__gte=inicio,
                    intentos__cuestionario__fecha_apertura__lte=fin,
                ).distinct()
        elif rango is not None:
            estudiantes = []
            for estudiante in qs.only("id", "nombre", "codigo"):
                fechas = [
                    intento.cuestionario.fecha_apertura
                    for intento in estudiante.intentos.select_related("cuestionario").all()
                    if intento.cuestionario and intento.cuestionario.fecha_apertura is not None
                ]
                if any(rango[0] <= fecha.month <= rango[1] for fecha in fechas):
                    estudiantes.append({"id": estudiante.id, "nombre": estudiante.nombre, "codigo": estudiante.codigo})
            return estudiantes
    if texto:
        busqueda = texto.strip()
        if busqueda:
            qs = qs.filter(
                Q(nombre__icontains=busqueda)
                | Q(codigo__icontains=busqueda)
                | Q(correo__icontains=busqueda)
            )
    return list(qs.order_by("nombre").values("id", "nombre", "codigo"))
