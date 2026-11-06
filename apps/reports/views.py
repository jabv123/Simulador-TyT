from __future__ import annotations

import io
from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasModulePermission
from apps.attempts.models import EstadoIntento, Intento

from .forms import (
    ReportFilterForm,
    obtener_anios_disponibles,
    obtener_cursos_disponibles,
    obtener_ejes_disponibles,
    obtener_estudiantes_disponibles,
    obtener_periodos_disponibles,
)
from .selectors import get_base_intento_queryset
from .services import (
    aplicar_filtros,
    obtener_kpis,
    obtener_resumen_agregado,
    obtener_tabla_resultados,
)


class ReportesTemplateView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return render(request, "acceso_denegado.html", status=401)
        if not request.user.has_perm("REPORTES.VER"):
            return render(request, "acceso_denegado.html", status=403)

        try:
            page = max(1, int(request.GET.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        order_by = request.GET.get("orden", "fecha")
        order_dir = request.GET.get("direccion", "desc")
        tipo = (request.GET.get("tipo") or "general").lower()

        form = ReportFilterForm(request.GET or None)
        queryset = get_base_intento_queryset()
        filtros = {}
        if form.is_valid():
            filtros = form.get_filters()
            queryset = aplicar_filtros(queryset, filtros)
        if tipo not in {"general", "curso", "estudiante", "eje"}:
            tipo = "general"

        tabla = obtener_tabla_resultados(
            queryset,
            page_size=10,
            page=page,
            order_by=order_by,
            order_dir=order_dir,
        )
        resumen = obtener_resumen_agregado(queryset, tipo)
        contexto = {
            "form": form,
            "filtros": filtros,
            "tipo": tipo,
            "resumen": resumen,
            "indicadores": obtener_kpis(queryset),
            "tablas": tabla["items"],
            "paginacion": {
                "page": tabla["page"],
                "page_size": tabla["page_size"],
                "total": tabla["total"],
                "total_paginas": tabla["total_paginas"],
            },
            "orden": order_by,
            "direccion": order_dir,
            "anios": obtener_anios_disponibles(),
            "periodos": obtener_periodos_disponibles(),
            "cursos": obtener_cursos_disponibles(),
            "ejes": obtener_ejes_disponibles(),
            "estudiantes": obtener_estudiantes_disponibles(),
        }
        return render(request, "reports/reportes.html", contexto)


class ReportesApiView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"get": ("reportes", "ver")}

    def get(self, request):
        form = ReportFilterForm(request.query_params)
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        filtros = form.get_filters()
        queryset = get_base_intento_queryset()
        queryset = aplicar_filtros(queryset, filtros)
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        order_by = request.query_params.get("orden", "fecha")
        order_dir = request.query_params.get("direccion", "desc")
        tipo = request.query_params.get("tipo", "general").lower()

        tabla = obtener_tabla_resultados(
            queryset,
            page_size=10,
            page=page,
            order_by=order_by,
            order_dir=order_dir,
        )
        datos = {
            "filtros": filtros,
            "tipo": tipo,
            "indicadores": obtener_kpis(queryset),
            "resultados": tabla["items"],
            "paginacion": {
                "page": tabla["page"],
                "page_size": tabla["page_size"],
                "total": tabla["total"],
                "total_paginas": tabla["total_paginas"],
            },
        }
        if tipo in {"curso", "estudiante", "eje"}:
            datos["resumen"] = obtener_resumen_agregado(queryset, tipo)
        elif tipo == "general":
            datos["resumen"] = obtener_resumen_agregado(queryset, "general")
        return Response(datos)


class ApiFiltrosView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"get": ("reportes", "ver")}

    def get(self, request, tipo=None):
        tipo = tipo or request.path.rstrip("/").split("/")[-1]
        if tipo == "periodos":
            anio = request.query_params.get("anio")
            return Response(obtener_periodos_disponibles(anio))
        if tipo == "cursos":
            anio = request.query_params.get("anio")
            periodo = request.query_params.get("periodo")
            return Response(obtener_cursos_disponibles(anio, periodo))
        if tipo == "ejes":
            anio = request.query_params.get("anio")
            periodo = request.query_params.get("periodo")
            curso = request.query_params.get("curso")
            return Response(obtener_ejes_disponibles(anio, periodo, curso))
        if tipo == "estudiantes":
            curso = request.query_params.get("curso")
            texto = request.query_params.get("q")
            anio = request.query_params.get("anio")
            periodo = request.query_params.get("periodo")
            return Response(obtener_estudiantes_disponibles(curso, texto, anio, periodo))
        return Response({"detail": "Tipo de filtro no soportado."}, status=404)


class ExportarReporteView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"get": ("reportes", "ver")}

    def get(self, request):
        form = ReportFilterForm(request.query_params)
        filtros = {}
        if form.is_valid():
            filtros = form.get_filters()
        queryset = get_base_intento_queryset()
        queryset = aplicar_filtros(queryset, filtros)
        registros = list(
            queryset.filter(
                estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO]
            )
            .select_related("cuestionario", "usuario")
            .order_by("-fecha_fin", "-calificacion_final")
        )

        resumen_data = obtener_resumen_agregado(queryset, "general")
        kpis = resumen_data.get("kpis", {}) if isinstance(resumen_data, dict) else {}
        top_cursos = resumen_data.get("top_cursos", []) if isinstance(resumen_data, dict) else []
        top_estudiantes = resumen_data.get("top_estudiantes", []) if isinstance(resumen_data, dict) else []
        top_ejes = resumen_data.get("top_ejes", []) if isinstance(resumen_data, dict) else []

        filtro_label = "Todos los registros"
        if filtros:
            partes = []
            if filtros.get("anio"):
                partes.append(f"Año: {filtros['anio']}")
            if filtros.get("periodo"):
                partes.append(f"Período: {filtros['periodo']}")
            if filtros.get("curso"):
                partes.append(f"Curso: {filtros['curso']}")
            if filtros.get("estudiante"):
                partes.append(f"Estudiante: {filtros['estudiante']}")
            if filtros.get("eje"):
                partes.append(f"Eje: {filtros['eje']}")
            if partes:
                filtro_label = " | ".join(partes)

        workbook = Workbook()

        resumen = workbook.active
        resumen.title = "Resumen ejecutivo"
        resumen.merge_cells("A1:F1")
        resumen["A1"] = "Reporte ejecutivo académico"
        resumen["A1"].font = Font(bold=True, size=14, color="FFFFFF")
        resumen["A1"].fill = PatternFill("solid", fgColor="1F4E78")
        resumen["A1"].alignment = {"horizontal": "center"}

        resumen.append([])
        resumen.append(["Filtro aplicado", filtro_label])
        resumen.append(["Total de intentos", len(registros)])
        resumen.append(["Promedio general", round(float(kpis.get("promedio") or 0), 2)])
        resumen.append(["Aprobados", kpis.get("aprobados", 0)])
        resumen.append(["No aprobados", kpis.get("no_aprobados", 0)])
        resumen.append(["% aprobación", f"{float(kpis.get('porcentaje_aprobacion') or 0):.2f}%"])
        resumen.append(["Mejor curso", (top_cursos[0]["nombre"] if top_cursos else "N/A")])
        resumen.append(["Mejor eje", (top_ejes[0]["nombre"] if top_ejes else "N/A")])

        for row in range(3, resumen.max_row + 1):
            resumen[f"A{row}"].font = Font(bold=True)
            resumen[f"A{row}"].fill = PatternFill("solid", fgColor="EAF3FF")

        resumen.freeze_panes = "A4"

        detalle = workbook.create_sheet("Detalle")
        headers = [
            "Año",
            "Período",
            "Curso",
            "Estudiante",
            "Identificación",
            "Fecha",
            "Calificación",
            "Estado",
        ]
        detalle.append(headers)
        for item in registros:
            fecha_apertura = getattr(item.cuestionario, "fecha_apertura", None)
            anio = fecha_apertura.year if fecha_apertura else ""
            periodo = "1°" if fecha_apertura and fecha_apertura.month <= 6 else "2°" if fecha_apertura else ""
            detalle.append([
                anio,
                periodo,
                item.cuestionario.nombre if item.cuestionario else "",
                item.usuario.nombre if item.usuario else "",
                item.usuario.codigo if item.usuario else "",
                (item.fecha_fin or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
                float(item.calificacion_final or 0),
                item.get_estado_display(),
            ])
        for cell in detalle[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="4F81BD")
        detalle.freeze_panes = "A2"

        ranking = workbook.create_sheet("Ranking")
        ranking.append(["Top cursos", "Promedio", "Aprobados"])
        for item in top_cursos[:5]:
            ranking.append([item.get("nombre", "N/A"), float(item.get("promedio") or 0), item.get("aprobados", 0)])
        ranking.append([])
        ranking.append(["Top estudiantes", "Promedio", "Intentos"])
        for item in top_estudiantes[:5]:
            ranking.append([item.get("nombre", "N/A"), float(item.get("promedio") or 0), item.get("intentos", 0)])
        ranking.append([])
        ranking.append(["Top ejes", "Promedio", "Intentos"])
        for item in top_ejes[:5]:
            ranking.append([item.get("nombre", "N/A"), float(item.get("promedio") or 0), item.get("intentos", 0)])
        for cell in ranking[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="3C6E71")

        for ws in (resumen, detalle, ranking):
            for column_cells in ws.columns:
                values = [cell.value for cell in column_cells if cell.value is not None]
                if not values:
                    width = 12
                else:
                    width = max(len(str(value)) for value in values) + 2
                ws.column_dimensions[column_cells[0].column_letter].width = min(max(width, 12), 32)

        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        nombre = "reporte_consolidado.xlsx"
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return response
