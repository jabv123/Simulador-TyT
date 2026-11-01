"""Autenticación JWT que comprueba el estado actual de la cuenta."""

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings

from .models import Estado


class AutenticacionJWTActiva(JWTAuthentication):
    """Rechaza access tokens pertenecientes a cuentas desactivadas."""

    def get_user(self, validated_token):
        identificador = validated_token.get(api_settings.USER_ID_CLAIM)
        if identificador is None:
            raise AuthenticationFailed(
                "El token no contiene un identificador de usuario válido.",
                code="usuario_no_identificado",
            )
        modelo_usuario = get_user_model()
        try:
            usuario = modelo_usuario.objects.get(
                **{api_settings.USER_ID_FIELD: identificador}
            )
        except modelo_usuario.DoesNotExist as error:
            raise AuthenticationFailed(
                "La cuenta asociada al token ya no existe.",
                code="usuario_no_encontrado",
            ) from error
        if not usuario.is_active or usuario.rol.estado != Estado.ACTIVO:
            raise AuthenticationFailed(
                "La cuenta está inactiva. Contacta al administrador.",
                code="cuenta_inactiva",
            )
        return usuario
