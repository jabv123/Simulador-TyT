"""Serializadores de autenticación y perfil de usuario."""

from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.serializers import ModelSerializer, ReadOnlyField, SerializerMethodField
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Estado, Permiso, Usuario


class TokenAccesoSerializer(TokenObtainPairSerializer):
    """Autentica por código o correo y agrega los datos básicos al JWT."""

    @classmethod
    def get_token(cls, usuario):
        token = super().get_token(usuario)
        token["nombre"] = usuario.nombre
        token["codigo"] = usuario.codigo
        token["rol"] = usuario.rol.nombre
        token["rol_id"] = usuario.rol_id
        token["permisos"] = cls.obtener_permisos(usuario)
        return token

    @staticmethod
    def obtener_permisos(usuario):
        if usuario._es_administrador():
            permisos = Permiso.objects.values_list("modulo", "accion")
        else:
            permisos = usuario.rol.permisos_configurados.select_related(
                "permiso"
            ).values_list("permiso__modulo", "permiso__accion")
        return [f"{modulo}.{accion}" for modulo, accion in permisos]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop(self.username_field, None)
        self.fields["codigo"] = serializers.CharField(
            required=False,
            allow_blank=True,
            label="Código o correo electrónico",
            trim_whitespace=True,
        )
        self.fields["correo"] = serializers.EmailField(
            required=False,
            allow_blank=True,
            label="Correo electrónico",
        )
        self.fields["password"].label = "Contraseña"

    def validate(self, attrs):
        identificador = attrs.get("codigo") or attrs.get("correo")
        password = attrs.get("password")
        if not identificador or not password:
            raise serializers.ValidationError(
                {"detail": "Debes ingresar tu código o correo y la contraseña."}
            )

        campo = "correo" if "@" in identificador else "codigo"
        consulta = {f"{campo}__iexact": identificador.strip()}
        usuario = Usuario.objects.select_related("rol").filter(**consulta).first()
        if usuario is None or not check_password(password, usuario.password):
            raise AuthenticationFailed("El código/correo o la contraseña son incorrectos.")
        if not usuario.is_active or usuario.rol.estado != Estado.ACTIVO:
            raise AuthenticationFailed("La cuenta está inactiva. Contacta al administrador.")

        refresh = self.get_token(usuario)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "usuario": {
                "id": usuario.pk,
                "nombre": usuario.nombre,
                "rol": usuario.rol.nombre,
                "permisos": self.obtener_permisos(usuario),
            },
        }


class TokenRenovarSerializer(TokenRefreshSerializer):
    """Impide renovar tokens cuando la cuenta o su rol fueron desactivados."""

    def validate(self, attrs):
        try:
            refresh = RefreshToken(attrs["refresh"])
        except TokenError as error:
            raise AuthenticationFailed(
                "El refresh es inválido, expiró o ya fue revocado."
            ) from error

        identificador = refresh.get(api_settings.USER_ID_CLAIM)
        usuario = Usuario.objects.filter(
            **{api_settings.USER_ID_FIELD: identificador}
        ).first()
        if (
            usuario is None
            or not usuario.is_active
            or usuario.rol.estado != Estado.ACTIVO
        ):
            raise AuthenticationFailed(
                "La cuenta está inactiva y no puede renovar su sesión."
            )
        try:
            return super().validate(attrs)
        except (TokenError, AuthenticationFailed) as error:
            raise AuthenticationFailed(
                "El refresh es inválido, expiró o ya fue revocado."
            ) from error


class CambioContrasenaSerializer(serializers.Serializer):
    contrasena_actual = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        label="Contraseña actual",
    )
    contrasena_nueva = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        validators=[validate_password],
        label="Contraseña nueva",
    )

    def validate(self, attrs):
        usuario = self.context["request"].user
        if not check_password(attrs["contrasena_actual"], usuario.password):
            raise serializers.ValidationError(
                {"contrasena_actual": "La contraseña actual es incorrecta."}
            )
        if attrs["contrasena_actual"] == attrs["contrasena_nueva"]:
            raise serializers.ValidationError(
                {"contrasena_nueva": "La contraseña nueva debe ser diferente."}
            )
        return attrs


class PerfilUsuarioSerializer(ModelSerializer):
    rol = ReadOnlyField(source="rol.nombre")
    permisos = SerializerMethodField()

    class Meta:
        model = Usuario
        fields = (
            "id",
            "nombre",
            "codigo",
            "correo",
            "foto",
            "telefono",
            "estado",
            "fecha_creacion",
            "rol",
            "permisos",
        )
        read_only_fields = fields

    def get_permisos(self, usuario):
        if usuario._es_administrador():
            return [
                {"modulo": modulo, "accion": accion, "alcance": "TODOS"}
                for modulo, accion in Permiso.objects.values_list(
                    "modulo", "accion"
                )
            ]
        return [
            {
                "modulo": asignacion.permiso.modulo,
                "accion": asignacion.permiso.accion,
                "alcance": asignacion.alcance,
            }
            for asignacion in usuario.rol.permisos_configurados.select_related(
                "permiso"
            )
        ]


class PerfilActualizarSerializer(ModelSerializer):
    class Meta:
        model = Usuario
        fields = ("nombre", "foto", "telefono")

    def validate_nombre(self, valor):
        if not valor.strip():
            raise serializers.ValidationError("El nombre no puede estar vacío.")
        return valor.strip()
