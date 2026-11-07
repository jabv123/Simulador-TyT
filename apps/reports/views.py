from __future__ import annotations

import io

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import CursoAcademico, Grupo, Usuario
from apps.accounts.permissions import HasModulePermission
from apps.attempts.models import EstadoIntento
from apps.questions.models import Categoria
from apps.quizzes.models import Cuestionario

from .forms import (
    ReportFilterForm,
    obtener_anios_disponibles,
    obtener_cursos_academicos_disponibles,
    obtener_cursos_disponibles,
    obtener_ejes_disponibles,
    obtener_estudiantes_disponibles,
    obtener_grupos_academicos_disponibles,
    obtener_periodos_disponibles,
)
from .selectors import get_base_intento_queryset
from .services import (
    aplicar_filtros,
    calificacion_sobre_cinco,
    obtener_historial_individual,
    obtener_kpis,
    obtener_resumen_agregado,
    obtener_tabla_resultados,
)


def _filtros_legibles(filtros):
    etiquetas = {
        "anio": "Año",
        "periodo": "Período",
        "curso": "Simulacro",
        "curso_academico": "Curso académico",
        "grupo": "Grupo",
        "estudiante": "Estudiante",
        "eje": "Eje temático",
        "query": "Búsqueda",
        "tipo": "Vista",
    }
    modelos = {
        "curso": Cuestionario,
        "curso_academico": CursoAcademico,
        "grupo": Grupo,
        "estudiante": Usuario,
        "eje": Categoria,
    }
    partes = []
    for campo, etiqueta in etiquetas.items():
        valor = filtros.get(campo)
        if valor in (None, ""):
            continue
        if campo == "periodo":
            valor = f"{valor}° semestre"
        elif campo == "tipo":
            valor = dict(ReportFilterForm.TIPOS_RESUMEN).get(valor, valor)
        elif campo in modelos:
            objeto = modelos[campo].objects.filter(pk=valor).first()
            if objeto:
                valor = objeto.nombre if campo != "grupo" else str(objeto)
        partes.append(f"{etiqueta}: {valor}")
    return " | ".join(partes) if partes else "Todos los registros"


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
        if tipo not in {"general", "curso", "estudiante", "eje", "curso_grupo",
            "periodo",
            "dificultad",
        }:
            tipo = "general"

        tabla = obtener_tabla_resultados(
            queryset,
            page_size=10,
            page=page,
            order_by=order_by,
            order_dir=order_dir,
            include_identificacion=request.user.has_perm("USUARIOS.GESTIONAR"),
        )
        resumen = obtener_resumen_agregado(
            queryset,
            tipo,
            eje=filtros.get("eje"),
            include_identificacion=request.user.has_perm("USUARIOS.GESTIONAR"),
        )
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
            "cursos_academicos": obtener_cursos_academicos_disponibles(),
            "grupos_academicos": obtener_grupos_academicos_disponibles(),
            "ejes": obtener_ejes_disponibles(),
            "estudiantes": obtener_estudiantes_disponibles(
                include_identificacion=request.user.has_perm(
                    "USUARIOS.GESTIONAR"
                )
            ),
            "puede_ver_identificacion": request.user.has_perm(
                "USUARIOS.GESTIONAR"
            ),
            "historial": (
                obtener_historial_individual(
                    aplicar_filtros(get_base_intento_queryset(), filtros),
                    eje=filtros.get("eje"),
                )
                if filtros.get("estudiante")
                else []
            ),
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
        tipos_soportados = {
            "general",
            "curso",
            "curso_grupo",
            "estudiante",
            "eje",
            "periodo",
            "dificultad",
        }
        if tipo not in tipos_soportados:
            return Response(
                {"tipo": "Tipo de reporte no soportado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tabla = obtener_tabla_resultados(
            queryset,
            page_size=10,
            page=page,
            order_by=order_by,
            order_dir=order_dir,
            include_identificacion=request.user.has_perm("USUARIOS.GESTIONAR"),
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
        datos["resumen"] = obtener_resumen_agregado(
            queryset,
            "general" if tipo == "general" else tipo,
            eje=filtros.get("eje"),
            include_identificacion=request.user.has_perm("USUARIOS.GESTIONAR"),
        )
        if filtros.get("estudiante"):
            datos["historial"] = obtener_historial_individual(
                aplicar_filtros(get_base_intento_queryset(), filtros),
                eje=filtros.get("eje"),
            )
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
        if tipo == "cursos-academicos":
            return Response(obtener_cursos_academicos_disponibles())
        if tipo == "grupos":
            curso_academico = request.query_params.get("curso_academico")
            return Response(
                obtener_grupos_academicos_disponibles(curso_academico)
            )
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
            curso_academico = request.query_params.get("curso_academico")
            grupo = request.query_params.get("grupo")
            return Response(
                obtener_estudiantes_disponibles(
                    curso,
                    texto,
                    anio,
                    periodo,
                    curso_academico,
                    grupo,
                    request.user.has_perm("USUARIOS.GESTIONAR"),
                )
            )
        return Response({"detail": "Tipo de filtro no soportado."}, status=404)


class ExportarReporteView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"get": ("reportes", "exportar")}

    def get(self, request):
        form = ReportFilterForm(request.query_params)
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        reporte = request.query_params.get("reporte", "").upper()
        if reporte and reporte not in {"A", "B", "C"}:
            return Response(
                {"reporte": "El reporte debe ser A, B o C."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        filtros = form.get_filters()
        queryset = get_base_intento_queryset()
        queryset = aplicar_filtros(queryset, filtros)
        registros = list(
            queryset.filter(
                estado__in=[EstadoIntento.FINALIZADO, EstadoIntento.TIEMPO_AGOTADO]
            )
            .select_related("cuestionario", "usuario")
            .select_related("grupo_snapshot__curso")
            .order_by("-fecha_fin", "-calificacion_final")
        )

        puede_ver_identificacion = request.user.has_perm("USUARIOS.GESTIONAR")
        resumen_data = obtener_resumen_agregado(
            queryset,
            "general",
            eje=filtros.get("eje"),
            include_identificacion=puede_ver_identificacion,
        )
        kpis = resumen_data.get("kpis", {}) if isinstance(resumen_data, dict) else {}
        top_cursos = resumen_data.get("top_cursos", []) if isinstance(resumen_data, dict) else []
        top_estudiantes = resumen_data.get("top_estudiantes", []) if isinstance(resumen_data, dict) else []
        top_ejes = resumen_data.get("top_ejes", []) if isinstance(resumen_data, dict) else []
        por_periodo = obtener_resumen_agregado(queryset, "periodo")
        por_curso_grupo = obtener_resumen_agregado(queryset, "curso_grupo")
        por_eje = obtener_resumen_agregado(
            queryset,
            "eje",
            eje=filtros.get("eje"),
            contextual=True,
        )
        preguntas_dificiles = obtener_resumen_agregado(
            queryset,
            "dificultad",
            eje=filtros.get("eje"),
        )
        filtro_label = _filtros_legibles(filtros)
        generado = timezone.localtime()

        workbook = Workbook()

        resumen = workbook.active
        resumen.title = "Resumen ejecutivo"
        resumen.merge_cells("A1:F1")
        resumen["A1"] = "Reporte ejecutivo académico"
        resumen["A1"].font = Font(bold=True, size=14, color="FFFFFF")
        resumen["A1"].fill = PatternFill("solid", fgColor="1F4E78")
        resumen["A1"].alignment = Alignment(horizontal="center")

        resumen.append([])
        resumen.append(["Filtro aplicado", filtro_label])
        resumen.append(["Fecha de generación", generado.strftime("%Y-%m-%d %H:%M:%S %Z")])
        resumen.append(["Total de intentos", len(registros)])
        resumen.append(["Promedio general / 5,0", round(float(kpis.get("promedio") or 0), 2)])
        resumen.append(["Aprobados", kpis.get("aprobados", 0)])
        resumen.append(["No aprobados", kpis.get("no_aprobados", 0)])
        resumen.append(["% aprobación", f"{float(kpis.get('porcentaje_aprobacion') or 0):.2f}%"])
        resumen.append(["Mejor curso", (top_cursos[0]["nombre"] if top_cursos else "N/A")])
        resumen.append(["Mejor eje", (top_ejes[0]["nombre"] if top_ejes else "N/A")])

        for row in range(3, resumen.max_row + 1):
            resumen[f"A{row}"].font = Font(bold=True)
            resumen[f"A{row}"].fill = PatternFill("solid", fgColor="EAF3FF")

        resumen.freeze_panes = "A4"

        detalle = workbook.create_sheet("Reporte A - Consolidado")
        headers = [
            "Año",
            "Período",
            "Curso",
            "Grupo",
            "Simulacro",
            "Estudiante",
            "Fecha",
            "Calificación / 5,0",
            "Calificación original",
            "Escala original",
            "Resultado",
            "Estado del intento",
        ]
        if puede_ver_identificacion:
            headers.insert(6, "Identificación")
        detalle.append(headers)
        for item in registros:
            fecha_apertura = getattr(item.cuestionario, "fecha_apertura", None)
            anio = fecha_apertura.year if fecha_apertura else ""
            periodo = (
                "1° semestre"
                if fecha_apertura and fecha_apertura.month <= 6
                else "2° semestre"
                if fecha_apertura
                else ""
            )
            grupo = item.grupo_snapshot
            aprobado = (
                item.calificacion_final is not None
                and item.calificacion_final
                >= item.cuestionario.calificacion_aprobacion
            )
            fila = [
                anio,
                periodo,
                item.curso_nombre_snapshot
                or (grupo.curso.nombre if grupo else "Sin curso"),
                item.grupo_nombre_snapshot or (grupo.nombre if grupo else "Sin grupo"),
                item.cuestionario.nombre,
                item.usuario.nombre if item.usuario else "",
                (item.fecha_fin.strftime("%Y-%m-%d %H:%M:%S") if item.fecha_fin else ""),
                float(
                    calificacion_sobre_cinco(
                        item.calificacion_final,
                        item.cuestionario.calificacion_maxima,
                    )
                    or 0
                ),
                float(item.calificacion_final or 0),
                float(item.cuestionario.calificacion_maxima),
                "Aprobado" if aprobado else "No aprobado",
                item.get_estado_display(),
            ]
            if puede_ver_identificacion:
                fila.insert(6, item.usuario.codigo if item.usuario else "")
            detalle.append(fila)
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
        ranking.append(["Top ejes", "% aciertos", "Preguntas respondidas"])
        for item in top_ejes[:5]:
            ranking.append([
                item.get("nombre", "N/A"),
                float(item.get("porcentaje_aciertos") or 0),
                item.get("preguntas_respondidas", 0),
            ])
        for cell in ranking[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="3C6E71")

        periodos_ws = workbook.create_sheet("Año y período")
        periodos_ws.append(
            ["Año", "Período", "Evaluaciones", "Intentos", "Estudiantes", "Promedio / 5,0"]
        )
        for item in por_periodo:
            periodos_ws.append([
                item["anio"],
                item["periodo_nombre"],
                item["evaluaciones"],
                item["intentos"],
                item["estudiantes"],
                float(item["promedio"] or 0),
            ])

        grupos_ws = workbook.create_sheet("Cursos y grupos")
        grupos_ws.append([
            "Curso",
            "Grupo",
            "Estudiantes evaluados",
            "Intentos",
            "Promedio / 5,0",
            "Nota mínima / 5,0",
            "Nota máxima / 5,0",
            "Aprobados",
            "No aprobados",
        ])
        for item in por_curso_grupo:
            grupos_ws.append([
                item["curso"],
                item["grupo"],
                item["estudiantes"],
                item["intentos"],
                float(item["promedio"] or 0),
                float(item["nota_minima"] or 0),
                float(item["nota_maxima"] or 0),
                item["aprobados"],
                item["no_aprobados"],
            ])

        ejes_ws = workbook.create_sheet("Desempeño por eje")
        ejes_ws.append([
            "Año",
            "Período",
            "Curso",
            "Eje",
            "Respuestas registradas",
            "Aciertos",
            "Errores",
            "Porcentaje de aciertos",
            "Nota promedio / 5,0",
        ])
        for item in por_eje:
            ejes_ws.append([
                item["anio"],
                item["periodo"],
                item["curso"],
                item["nombre"],
                item["preguntas_respondidas"],
                item["respuestas_correctas"],
                item["errores"],
                float(item["porcentaje_aciertos"] or 0),
                float(item["nota"] or 0),
            ])

        dificultad_ws = workbook.create_sheet("Preguntas difíciles")
        dificultad_ws.append([
            "ID",
            "Pregunta",
            "Eje",
            "Total de respuestas",
            "Errores",
            "% aciertos",
        ])
        for item in preguntas_dificiles:
            dificultad_ws.append([
                item["id"],
                item["pregunta"],
                item["eje"] or "Sin eje",
                item["total_respuestas"],
                item["errores"],
                float(item["porcentaje_aciertos"] or 0),
            ])

        historial_ws = workbook.create_sheet("Reporte C - Historial")
        historial_ws.append([
            "Año",
            "Estudiante",
            "Curso",
            "Período",
            "Simulacro",
            "Fecha",
            "Preguntas respondidas",
            "Aciertos",
            "Errores",
            "Nota final / 5,0",
        ])
        for item in obtener_historial_individual(
            queryset,
            eje=filtros.get("eje"),
        ):
            historial_ws.append([
                item["anio"],
                item["estudiante"],
                item["curso"],
                item["periodo"],
                item["simulacro"],
                item["fecha"].strftime("%Y-%m-%d %H:%M:%S")
                if item["fecha"]
                else "",
                item["preguntas_respondidas"],
                item["aciertos"],
                item["errores"],
                float(item["nota"] or 0),
            ])

        for ws in workbook.worksheets:
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="4F81BD")
            for column_index, column_cells in enumerate(ws.columns, start=1):
                values = [cell.value for cell in column_cells if cell.value is not None]
                if not values:
                    width = 12
                else:
                    width = max(len(str(value)) for value in values) + 2
                ws.column_dimensions[get_column_letter(column_index)].width = min(
                    max(width, 12),
                    32,
                )

        if reporte:
            hojas_reporte = {
                "A": "Reporte A - Consolidado",
                "B": "Desempeño por eje",
                "C": "Reporte C - Historial",
            }
            hoja_seleccionada = hojas_reporte[reporte]
            for ws in list(workbook.worksheets):
                if ws.title not in {"Resumen ejecutivo", hoja_seleccionada}:
                    workbook.remove(ws)

        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        tipo_archivo = (
            f"{reporte.lower()}_"
            if reporte
            else f"{str(filtros.get('tipo', 'general')).replace('-', '_')}_"
        )
        nombre = f"reporte_academico_{tipo_archivo}{generado:%Y%m%d_%H%M%S}.xlsx"
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return response
