"""API de administración del banco de preguntas."""

from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import (
    HasModulePermission,
    PuedeConsultarCategorias,
    filtrar_por_alcance,
    permiso_de_vista,
    tiene_permiso,
)

from .models import Categoria, EstadoContenido, Pregunta
from .pagination import PaginacionPreguntas
from .serializers import CategoriaSerializer, PreguntaSerializer


class ListaCategoriasView(generics.ListCreateAPIView):
    serializer_class = CategoriaSerializer
    permission_classes = [IsAuthenticated, PuedeConsultarCategorias]
    required_permissions = {
        "list": [("categorias", "ver"), ("preguntas", "ver")],
        "create": ("categorias", "crear"),
    }
    permiso_requerido = "CATEGORIAS.GESTIONAR"

    def get_queryset(self):
        permiso = permiso_de_vista(self.request, self)
        if self.request.method in {"GET", "HEAD"} and not tiene_permiso(
            self.request, "CATEGORIAS", "VER"
        ):
            permiso = "PREGUNTAS.VER"
        return filtrar_por_alcance(
            Categoria.objects.all(),
            self.request.user,
            permiso,
            None,
            request=self.request,
        )


class DetalleCategoriaView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CategoriaSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "retrieve": ("categorias", "ver"),
        "update": ("categorias", "editar"),
        "destroy": ("categorias", "desactivar"),
    }

    def get_queryset(self):
        return filtrar_por_alcance(
            Categoria.objects.all(),
            self.request.user,
            permiso_de_vista(self.request, self),
            None,
            request=self.request,
        )

    def perform_destroy(self, instance):
        instance.estado = EstadoContenido.INACTIVO
        instance.save(update_fields=["estado"])


class ListaPreguntasView(generics.ListCreateAPIView):
    serializer_class = PreguntaSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    filter_backends = [SearchFilter]
    search_fields = ["enunciado", "texto_base"]
    pagination_class = PaginacionPreguntas
    required_permissions = {
        "list": ("preguntas", "ver"),
        "create": ("preguntas", "crear"),
    }
    permiso_requerido = "PREGUNTAS.GESTIONAR"

    def get_queryset(self):
        queryset = Pregunta.objects.select_related(
            "categoria", "creado_por"
        ).prefetch_related("opciones")
        categoria = self.request.query_params.get("categoria")
        tipo = self.request.query_params.get("tipo")
        estado = self.request.query_params.get("estado")
        if categoria:
            if not categoria.isdecimal():
                raise ValidationError(
                    {"categoria": "El filtro categoría debe ser un identificador numérico."}
                )
            queryset = queryset.filter(categoria_id=categoria)
        if tipo:
            if tipo not in {"MULTIPLE", "VERDADERO_FALSO"}:
                raise ValidationError(
                    {"tipo": "El filtro tipo debe ser MULTIPLE o VERDADERO_FALSO."}
                )
            queryset = queryset.filter(tipo=tipo)
        if estado:
            estados = {valor.lower(): valor for valor in EstadoContenido.values}
            valor_estado = estados.get(estado.lower())
            if valor_estado is None:
                raise ValidationError(
                    {"estado": "El filtro estado debe ser Activo o Inactivo."}
                )
            queryset = queryset.filter(estado=valor_estado)
        return filtrar_por_alcance(
            queryset,
            self.request.user,
            permiso_de_vista(self.request, self),
            "creado_por",
            request=self.request,
        )


class DetallePreguntaView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PreguntaSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "retrieve": ("preguntas", "ver"),
        "update": ("preguntas", "editar"),
        "destroy": ("preguntas", "desactivar"),
    }

    def get_queryset(self):
        queryset = Pregunta.objects.select_related(
            "categoria", "creado_por"
        ).prefetch_related("opciones")
        return filtrar_por_alcance(
            queryset,
            self.request.user,
            permiso_de_vista(self.request, self),
            "creado_por",
            request=self.request,
        )

    def perform_destroy(self, instance):
        instance.estado = EstadoContenido.INACTIVO
        instance.save(update_fields=["estado"])
