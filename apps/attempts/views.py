"""API para iniciar, responder, enviar y consultar intentos."""

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import (
    HasModulePermission,
    PuedeVerResultados,
    filtrar_por_alcance,
    obtener_alcance,
    tiene_permiso,
)
from apps.quizzes.models import Cuestionario

from .models import Intento
from .serializers import (
    IntentoFinalizadoSerializer,
    IntentoPresentacionSerializer,
    IntentoResumenSerializer,
    RespuestaEntradaSerializer,
)
from .services import (
    finalizar_intento,
    finalizar_si_vencido,
    finalizar_vencidos,
    guardar_respuesta,
    iniciar_intento,
)


class IniciarIntentoView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"post": ("intentos", "iniciar")}
    permiso_requerido = "INTENTOS.INICIAR"

    def post(self, request, cuestionario_id):
        cuestionario = get_object_or_404(Cuestionario, pk=cuestionario_id)
        intento = iniciar_intento(cuestionario=cuestionario, usuario=request.user)
        return Response(
            IntentoPresentacionSerializer(intento).data,
            status=status.HTTP_201_CREATED,
        )


class DetalleIntentoView(generics.RetrieveAPIView):
    serializer_class = IntentoPresentacionSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "retrieve": [
            ("intentos", "ver"),
            ("intentos", "ver_nota_propia"),
        ],
    }

    def get_queryset(self):
        return Intento.objects.filter(usuario=self.request.user).select_related(
            "cuestionario"
        ).prefetch_related("respuestas")

    def retrieve(self, request, *args, **kwargs):
        intento = self.get_object()
        intento = finalizar_si_vencido(intento)
        return Response(self.get_serializer(intento).data)


class GuardarRespuestaView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "put": ("intentos", "responder"),
        "post": ("intentos", "responder"),
    }
    permiso_requerido = "INTENTOS.RESPONDER"

    def _guardar(self, request, intento_id):
        entrada = RespuestaEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        respuesta = guardar_respuesta(
            intento_id=intento_id,
            usuario=request.user,
            pregunta_id=entrada.validated_data["pregunta_id"],
            opcion_id=entrada.validated_data.get("opcion_seleccionada_id"),
            marcada_para_revision=entrada.validated_data.get(
                "marcada_para_revision"
            ),
            actualizar_opcion=(
                "opcion_seleccionada_id" in entrada.validated_data
            ),
        )
        if respuesta is None:
            intento = get_object_or_404(Intento, pk=intento_id)
            return Response(
                {
                    "mensaje": "El tiempo terminó y el intento se envió automáticamente.",
                    "intento": IntentoFinalizadoSerializer(intento).data,
                },
                status=status.HTTP_200_OK,
            )
        return Response({"mensaje": "Respuesta guardada."})

    def put(self, request, intento_id):
        return self._guardar(request, intento_id)

    def post(self, request, intento_id):
        return self._guardar(request, intento_id)


class EnviarIntentoView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "post": ("intentos", "finalizar"),
    }
    permiso_requerido = "INTENTOS.FINALIZAR"

    def post(self, request, intento_id):
        intento = get_object_or_404(
            Intento.objects.select_related("cuestionario"),
            pk=intento_id,
        )
        if intento.usuario_id != request.user.pk:
            raise PermissionDenied("No puedes enviar un intento de otra persona.")
        intento = finalizar_intento(intento)
        return Response(IntentoFinalizadoSerializer(intento).data)


class MisResultadosView(generics.ListAPIView):
    serializer_class = IntentoResumenSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "list": [
            ("intentos", "ver_nota_propia"),
            ("resultados", "ver_propia_nota"),
        ]
    }

    def get_queryset(self):
        queryset = Intento.objects.filter(
            usuario=self.request.user
        ).select_related("cuestionario", "usuario")
        finalizar_vencidos(queryset)
        return queryset


class ListaResultadosView(generics.ListAPIView):
    serializer_class = IntentoResumenSerializer
    permission_classes = [IsAuthenticated, PuedeVerResultados]

    def get_permiso_resultados(self):
        if tiene_permiso(self.request, "RESULTADOS", "VER"):
            return "RESULTADOS.VER"
        return "RESULTADOS.VER_PROPIA_NOTA"

    def get_queryset(self):
        queryset = Intento.objects.select_related("cuestionario", "usuario")
        permiso = self.get_permiso_resultados()
        alcance = obtener_alcance(
            self.request.user,
            permiso,
            request=self.request,
        )
        queryset = filtrar_por_alcance(
            queryset,
            self.request.user,
            permiso,
            "usuario" if alcance == "PROPIOS" else "cuestionario__docente",
            request=self.request,
        )
        cuestionario_id = (
            self.request.query_params.get("cuestionario")
            or self.request.query_params.get("cuestionario_id")
        )
        usuario_id = (
            self.request.query_params.get("usuario")
            or self.request.query_params.get("usuario_id")
        )
        if cuestionario_id:
            if not cuestionario_id.isdigit():
                raise ValidationError(
                    {"cuestionario": "El filtro debe ser un identificador numérico."}
                )
            queryset = queryset.filter(cuestionario_id=cuestionario_id)
        if usuario_id:
            if not usuario_id.isdigit():
                raise ValidationError(
                    {"usuario": "El filtro debe ser un identificador numérico."}
                )
            queryset = queryset.filter(usuario_id=usuario_id)
        finalizar_vencidos(queryset)
        return queryset


class DetalleResultadoView(generics.RetrieveAPIView):
    serializer_class = IntentoPresentacionSerializer
    permission_classes = [IsAuthenticated, PuedeVerResultados]

    def get_permiso_resultados(self):
        if tiene_permiso(self.request, "RESULTADOS", "VER"):
            return "RESULTADOS.VER"
        return "RESULTADOS.VER_PROPIA_NOTA"

    def get_queryset(self):
        queryset = Intento.objects.select_related(
            "cuestionario", "usuario"
        ).prefetch_related("respuestas")
        permiso = self.get_permiso_resultados()
        alcance = obtener_alcance(
            self.request.user,
            permiso,
            request=self.request,
        )
        propietario = "usuario" if alcance == "PROPIOS" else "cuestionario__docente"
        return filtrar_por_alcance(
            queryset,
            self.request.user,
            permiso,
            propietario,
            request=self.request,
        )

    def retrieve(self, request, *args, **kwargs):
        intento = self.get_object()
        intento = finalizar_si_vencido(intento)
        serializer = self.get_serializer(
            intento,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)
