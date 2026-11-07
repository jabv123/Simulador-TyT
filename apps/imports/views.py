"""Endpoints de importación e historial de Excel."""

from io import BytesIO

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import (
    HasModulePermission,
    filtrar_por_alcance,
    permiso_de_vista,
    tiene_permiso,
)

from .models import Importacion
from .serializers import (
    ArchivoImportacionSerializer,
    ImportacionSerializer,
    PrevisualizacionImportacionSerializer,
)
from .services import (
    ENCABEZADOS_PLANTILLA,
    confirmar_importacion_excel,
    importar_preguntas_excel,
    previsualizar_preguntas_excel,
)


def validar_destino(request, cuestionario):
    if cuestionario is None:
        raise PermissionDenied("Debes indicar el cuestionario de destino.")
    if not tiene_permiso(request, "CUESTIONARIOS", "EDITAR"):
        raise PermissionDenied(
            "No tienes permiso para agregar preguntas a un cuestionario."
        )
    if not request.user._es_administrador() and cuestionario.docente_id != request.user.pk:
        raise PermissionDenied(
            "Solo puedes importar preguntas a tus propios cuestionarios."
        )
    if cuestionario.intentos.exists():
        raise PermissionDenied(
            "No se pueden agregar preguntas a un cuestionario con intentos."
        )


class ImportarExcelView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    parser_classes = [MultiPartParser, FormParser]
    required_permissions = {"post": ("importaciones", "importar")}
    permiso_requerido = "IMPORTACION.IMPORTAR"

    def post(self, request):
        entrada = ArchivoImportacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        cuestionario = entrada.validated_data.get("cuestionario")
        if cuestionario is not None:
            validar_destino(request, cuestionario)
        importacion = importar_preguntas_excel(
            archivo=entrada.validated_data["archivo"],
            usuario=request.user,
            cuestionario=cuestionario,
        )
        return Response(
            ImportacionSerializer(importacion).data,
            status=status.HTTP_201_CREATED,
        )


class PlantillaImportacionView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"get": ("importaciones", "importar")}

    def get(self, _request):
        libro = Workbook()
        hoja = libro.active
        hoja.title = "Preguntas"
        hoja.append(ENCABEZADOS_PLANTILLA)
        hoja.append(
            [
                "Razonamiento",
                "MULTIPLE",
                "Contexto opcional de la pregunta",
                "¿Cuánto es 2 + 2?",
                "4",
                "5",
                None,
                None,
                "A",
                "La respuesta correcta es cuatro.",
                1,
            ]
        )
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = f"A1:K{hoja.max_row}"
        for celda in hoja[1]:
            celda.font = Font(bold=True)
        salida = BytesIO()
        libro.save(salida)
        response = HttpResponse(
            salida.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = (
            'attachment; filename="plantilla_preguntas_saber_tyt.xlsx"'
        )
        return response


class PrevisualizarImportacionView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    parser_classes = [MultiPartParser, FormParser]
    required_permissions = {"post": ("importaciones", "importar")}

    def post(self, request):
        entrada = PrevisualizacionImportacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        cuestionario = entrada.validated_data["cuestionario"]
        validar_destino(request, cuestionario)
        resultado = previsualizar_preguntas_excel(
            entrada.validated_data["archivo"]
        )
        return Response(resultado, status=status.HTTP_200_OK)


class ConfirmarImportacionView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    parser_classes = [MultiPartParser, FormParser]
    required_permissions = {"post": ("importaciones", "importar")}

    def post(self, request):
        entrada = PrevisualizacionImportacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        cuestionario = entrada.validated_data["cuestionario"]
        validar_destino(request, cuestionario)
        importacion, previsualizacion = confirmar_importacion_excel(
            archivo=entrada.validated_data["archivo"],
            usuario=request.user,
            cuestionario=cuestionario,
        )
        return Response(
            {
                "importacion": ImportacionSerializer(importacion).data,
                "validas": previsualizacion["validas"],
                "duplicadas": previsualizacion["duplicadas"],
                "errores": previsualizacion["errores"],
                "preguntas_agregadas_cuestionario": (
                    previsualizacion["preguntas_agregadas_cuestionario"]
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ListaImportacionesView(generics.ListAPIView):
    serializer_class = ImportacionSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"list": ("importaciones", "ver")}

    def get_queryset(self):
        permiso = permiso_de_vista(self.request, self)
        return filtrar_por_alcance(
            Importacion.objects.select_related("usuario", "cuestionario"),
            self.request.user,
            permiso,
            "usuario",
            request=self.request,
        )


class ExportarHistorialImportacionesView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"get": ("importaciones", "ver")}
    categorias = ("validas", "duplicadas", "errores")
    titulos = {
        "validas": "Válida",
        "duplicadas": "Duplicada",
        "errores": "Con errores",
    }

    def get(self, request):
        tipo = request.query_params.get("tipo", "all")
        if tipo != "all" and tipo not in self.categorias:
            raise ValidationError({"tipo": "Selecciona un filtro de historial válido."})

        permiso = permiso_de_vista(request, self)
        importaciones = filtrar_por_alcance(
            Importacion.objects.select_related("usuario", "cuestionario"),
            request.user,
            permiso,
            "usuario",
            request=request,
        )
        libro = Workbook()
        hoja = libro.active
        hoja.title = "Historial de importaciones"
        hoja.append(
            [
                "Archivo",
                "Fecha de importación",
                "Cuestionario",
                "Resultado",
                "Tipo de fila",
                "Fila Excel",
                "Categoría",
                "Pregunta o detalle",
            ]
        )
        for celda in hoja[1]:
            celda.font = Font(bold=True)

        for importacion in importaciones:
            detalles = ImportacionSerializer.obtener_detalles(importacion)
            seleccionadas = self.categorias if tipo == "all" else (tipo,)
            for categoria in seleccionadas:
                registros = detalles.get(categoria, [])
                if categoria == "validas" and not registros and importacion.registros_exitosos:
                    registros = [
                        {
                            "pregunta": (
                                f"{importacion.registros_exitosos} fila(s) válida(s); "
                                "el detalle no se conservó en esta importación."
                            )
                        }
                    ]
                for registro in registros:
                    if isinstance(registro, dict):
                        fila = registro.get("fila", "")
                        nombre_categoria = registro.get("categoria", "")
                        descripcion = (
                            registro.get("pregunta")
                            or registro.get("motivo")
                            or registro.get("error")
                            or "Registro"
                        )
                    else:
                        fila = ""
                        nombre_categoria = ""
                        descripcion = str(registro)
                    hoja.append(
                        [
                            importacion.nombre_archivo,
                            importacion.fecha_importacion.strftime("%Y-%m-%d %H:%M"),
                            importacion.cuestionario.nombre if importacion.cuestionario else "",
                            importacion.estado_resultado,
                            self.titulos[categoria],
                            fila,
                            nombre_categoria,
                            descripcion,
                        ]
                    )

        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = hoja.dimensions
        for columna, ancho in {
            "A": 32,
            "B": 20,
            "C": 32,
            "D": 16,
            "E": 18,
            "F": 12,
            "G": 24,
            "H": 70,
        }.items():
            hoja.column_dimensions[columna].width = ancho
        for fila in hoja.iter_rows():
            for celda in fila:
                if isinstance(celda.value, str):
                    celda.data_type = "s"
        salida = BytesIO()
        libro.save(salida)
        response = HttpResponse(
            salida.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = (
            f'attachment; filename="historial_importaciones_{tipo}.xlsx"'
        )
        return response
