"""API de administración y consulta de cuestionarios disponibles."""

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import (
    HasModulePermission,
    filtrar_por_alcance,
    permiso_de_vista,
)
from .models import Cuestionario, EstadoCuestionario
from .serializers import (
    ActualizarPreguntaCuestionarioSerializer,
    CuestionarioDisponibleSerializer,
    CuestionarioSerializer,
    PreguntaCuestionarioSerializer,
)
from .services import (
    agregar_pregunta,
    actualizar_pregunta,
    desactivar_cuestionario,
    publicar_cuestionario,
    quitar_pregunta,
    reemplazar_preguntas,
)


class ListaCuestionariosView(generics.ListCreateAPIView):
    serializer_class = CuestionarioSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "list": ("cuestionarios", "ver"),
        "create": ("cuestionarios", "crear"),
    }
    permiso_requerido = "CUESTIONARIOS.GESTIONAR"

    def get_queryset(self):
        queryset = Cuestionario.objects.select_related("docente").prefetch_related(
            "preguntas_configuradas__pregunta__opciones"
        )
        return filtrar_por_alcance(
            queryset,
            self.request.user,
            permiso_de_vista(self.request, self),
            "docente",
            request=self.request,
        )


class DetalleCuestionarioView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CuestionarioSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "retrieve": ("cuestionarios", "ver"),
        "update": ("cuestionarios", "editar"),
        "destroy": ("cuestionarios", "desactivar"),
    }
    permiso_requerido = "CUESTIONARIOS.GESTIONAR"

    def get_queryset(self):
        queryset = Cuestionario.objects.select_related("docente").prefetch_related(
            "preguntas_configuradas__pregunta__opciones"
        )
        return filtrar_por_alcance(
            queryset,
            self.request.user,
            permiso_de_vista(self.request, self),
            "docente",
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        cuestionario = self.get_object()
        desactivar_cuestionario(cuestionario)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CuestionariosDisponiblesView(generics.ListAPIView):
    serializer_class = CuestionarioDisponibleSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"list": ("cuestionarios", "ver_disponibles")}
    permiso_requerido = "CUESTIONARIOS.VER_DISPONIBLES"

    def get_queryset(self):
        ahora = timezone.now()
        return Cuestionario.objects.filter(
            estado__in=[
                EstadoCuestionario.PROGRAMADO,
                EstadoCuestionario.DISPONIBLE,
            ],
            fecha_apertura__lte=ahora,
            fecha_cierre__gte=ahora,
        ).select_related("docente").prefetch_related(
            "preguntas_configuradas__pregunta"
        ).annotate(
            intentos_usados=Count(
                "intentos",
                filter=Q(intentos__usuario=self.request.user),
                distinct=True,
            )
        )


class CuestionarioPreguntasView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "get": ("cuestionarios", "ver"),
        "post": ("cuestionarios", "editar"),
        "put": ("cuestionarios", "editar"),
    }

    def _cuestionario(self, request, pk):
        queryset = filtrar_por_alcance(
            Cuestionario.objects.prefetch_related(
                "preguntas_configuradas__pregunta"
            ),
            request.user,
            permiso_de_vista(request, self),
            "docente",
            request=request,
        )
        return get_object_or_404(queryset, pk=pk)

    def get(self, request, pk):
        cuestionario = self._cuestionario(request, pk)
        relaciones = cuestionario.preguntas_configuradas.all()
        return Response(
            PreguntaCuestionarioSerializer(relaciones, many=True).data
        )

    def post(self, request, pk):
        cuestionario = self._cuestionario(request, pk)
        entrada = PreguntaCuestionarioSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        relacion = agregar_pregunta(
            cuestionario=cuestionario,
            **entrada.validated_data,
        )
        return Response(
            PreguntaCuestionarioSerializer(relacion).data,
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, pk):
        cuestionario = self._cuestionario(request, pk)
        entrada = PreguntaCuestionarioSerializer(
            data=request.data,
            many=True,
        )
        entrada.is_valid(raise_exception=True)
        cuestionario = reemplazar_preguntas(
            cuestionario=cuestionario,
            preguntas=entrada.validated_data,
        )
        return Response(
            PreguntaCuestionarioSerializer(
                cuestionario.preguntas_configuradas.all(),
                many=True,
            ).data
        )


class CuestionarioPreguntaDetalleView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "patch": ("cuestionarios", "editar"),
        "delete": ("cuestionarios", "editar"),
    }

    def _cuestionario(self, request, pk):
        queryset = filtrar_por_alcance(
            Cuestionario.objects.all(),
            request.user,
            permiso_de_vista(request, self),
            "docente",
            request=request,
        )
        return get_object_or_404(queryset, pk=pk)

    def patch(self, request, pk, pregunta_id):
        cuestionario = self._cuestionario(request, pk)
        entrada = ActualizarPreguntaCuestionarioSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        relacion = actualizar_pregunta(
            cuestionario=cuestionario,
            pregunta_id=pregunta_id,
            datos=entrada.validated_data,
        )
        return Response(PreguntaCuestionarioSerializer(relacion).data)

    def delete(self, request, pk, pregunta_id):
        cuestionario = self._cuestionario(request, pk)
        quitar_pregunta(cuestionario=cuestionario, pregunta_id=pregunta_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicarCuestionarioView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"post": ("cuestionarios", "editar")}

    def post(self, request, pk):
        cuestionario = filtrar_por_alcance(
            Cuestionario.objects.all(),
            request.user,
            permiso_de_vista(request, self),
            "docente",
            request=request,
        )
        cuestionario = get_object_or_404(cuestionario, pk=pk)
        resultado = publicar_cuestionario(cuestionario)
        return Response(CuestionarioSerializer(resultado).data)


class DesactivarCuestionarioView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"post": ("cuestionarios", "desactivar")}

    def post(self, request, pk):
        cuestionario = filtrar_por_alcance(
            Cuestionario.objects.all(),
            request.user,
            permiso_de_vista(request, self),
            "docente",
            request=request,
        )
        cuestionario = get_object_or_404(cuestionario, pk=pk)
        resultado = desactivar_cuestionario(cuestionario)
        return Response(CuestionarioSerializer(resultado).data)
