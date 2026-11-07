"""Vistas de autenticación y consulta del perfil."""

from django.contrib.auth import get_user_model, login as login_django
from django.contrib.auth import logout as logout_django
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    CambioContrasenaSerializer,
    PerfilActualizarSerializer,
    PerfilUsuarioSerializer,
    TokenAccesoSerializer,
)
from .permissions import TienePermisoConfigurado


class TokenAccesoView(TokenObtainPairView):
    serializer_class = TokenAccesoSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            usuario = get_user_model().objects.get(
                pk=response.data["usuario"]["id"]
            )
            login_django(
                request._request,
                usuario,
                backend="django.contrib.auth.backends.ModelBackend",
            )
        return response


class CerrarSesionView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        logout_django(request._request)
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Debes enviar el refresh para cerrar la sesión."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as error:
            raise AuthenticationFailed(
                "El refresh es inválido, expiró o ya fue revocado."
            ) from error
        return Response(
            {"detail": "Sesión cerrada correctamente."},
            status=status.HTTP_200_OK,
        )


class CambiarContrasenaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CambioContrasenaSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        usuario = request.user
        usuario.set_password(serializer.validated_data["contrasena_nueva"])
        usuario.save(update_fields=["password"])
        return Response(
            {"detail": "La contraseña se actualizó correctamente."},
            status=status.HTTP_200_OK,
        )


class PerfilUsuarioView(RetrieveUpdateAPIView):
    serializer_class = PerfilUsuarioSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        permisos = [IsAuthenticated()]
        if self.request.method not in {"GET", "HEAD", "OPTIONS"}:
            permisos.append(TienePermisoConfigurado())
        return permisos

    @property
    def permiso_requerido(self):
        return "PERFIL.EDITAR"

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return PerfilActualizarSerializer
        return PerfilUsuarioSerializer

    def get_object(self):
        return self.request.user
