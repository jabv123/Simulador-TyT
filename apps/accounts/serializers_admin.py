"""Serializadores de administración de usuarios, roles y permisos."""

from django.contrib.auth.password_validation import validate_password
from django.core.validators import MinLengthValidator
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import (
    AlcancePermiso,
    Estado,
    Permiso,
    Rol,
    Usuario,
)
from .services import reemplazar_permisos_rol


class PermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permiso
        fields = ("id", "modulo", "accion", "descripcion")


class AsignacionPermisoSerializer(serializers.Serializer):
    permiso_id = serializers.PrimaryKeyRelatedField(
        source="permiso",
        queryset=Permiso.objects.all(),
    )
    alcance = serializers.ChoiceField(choices=AlcancePermiso.choices)


class RolAdministracionSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(
        max_length=50,
        validators=[
            UniqueValidator(
                queryset=Rol.objects.all(),
                message="Ya existe un rol con ese nombre.",
            )
        ],
    )
    permisos = AsignacionPermisoSerializer(
        source="asignaciones_entrada",
        many=True,
        required=False,
        write_only=True,
    )
    permisos_configurados = serializers.SerializerMethodField()

    class Meta:
        model = Rol
        fields = (
            "id",
            "nombre",
            "descripcion",
            "estado",
            "permisos",
            "permisos_configurados",
        )

    def get_permisos_configurados(self, rol):
        filas = rol.permisos_configurados.select_related("permiso").all()
        return [
            {
                "permiso_id": fila.permiso_id,
                "modulo": fila.permiso.modulo,
                "accion": fila.permiso.accion,
                "alcance": fila.alcance,
            }
            for fila in filas
        ]

    def validate(self, attrs):
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", ""))
        estado = attrs.get("estado", getattr(self.instance, "estado", Estado.ACTIVO))
        if self.instance and self.instance.nombre.casefold() in {
            "administrador",
            "estudiante",
        }:
            if nombre.casefold() != self.instance.nombre.casefold():
                raise serializers.ValidationError(
                    {"nombre": "No se puede cambiar el nombre de un rol predeterminado."}
                )
            if self.instance.estado == Estado.ACTIVO and estado != Estado.ACTIVO:
                raise serializers.ValidationError(
                    {"estado": "No se puede desactivar un rol predeterminado."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        asignaciones = validated_data.pop("asignaciones_entrada", [])
        rol = Rol.objects.create(**validated_data)
        self._guardar_permisos(rol, asignaciones)
        return rol

    @transaction.atomic
    def update(self, instance, validated_data):
        asignaciones = validated_data.pop("asignaciones_entrada", None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.save()
        if asignaciones is not None:
            self._guardar_permisos(instance, asignaciones)
        return instance

    @staticmethod
    def _guardar_permisos(rol, asignaciones):
        reemplazar_permisos_rol(rol, asignaciones)


class UsuarioAdministracionSerializer(serializers.ModelSerializer):
    rol = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.filter(estado=Estado.ACTIVO),
        error_messages={
            "does_not_exist": "El rol seleccionado no existe o está inactivo.",
            "incorrect_type": "El rol debe identificarse con un número válido.",
        },
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
        validators=[MinLengthValidator(8), validate_password],
        style={"input_type": "password"},
    )
    rol_nombre = serializers.ReadOnlyField(source="rol.nombre")

    class Meta:
        model = Usuario
        fields = (
            "id",
            "nombre",
            "codigo",
            "correo",
            "password",
            "foto",
            "telefono",
            "estado",
            "fecha_creacion",
            "rol",
            "rol_nombre",
        )
        read_only_fields = ("id", "fecha_creacion", "rol_nombre", "estado")

    def validate_codigo(self, valor):
        if Usuario.objects.filter(codigo__iexact=valor).exclude(
            pk=getattr(self.instance, "pk", None)
        ).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese código.")
        return valor

    def validate_correo(self, valor):
        if Usuario.objects.filter(correo__iexact=valor).exclude(
            pk=getattr(self.instance, "pk", None)
        ).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese correo.")
        return valor

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": "La contraseña es obligatoria al crear un usuario."}
            )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        codigo = validated_data.pop("codigo")
        return Usuario.objects.create_user(
            codigo=codigo,
            password=password,
            **validated_data,
        )

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class EstadoUsuarioSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(
        choices=Estado.choices,
        error_messages={"invalid_choice": "El estado debe ser ACTIVO o INACTIVO."},
    )


class RestablecerContrasenaSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        validators=[MinLengthValidator(8), validate_password],
        style={"input_type": "password"},
        label="Nueva contraseña",
    )
