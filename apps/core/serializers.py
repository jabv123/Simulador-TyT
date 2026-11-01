"""Serializador de la configuración institucional."""

from rest_framework import serializers

from .models import ConfiguracionSistema


class ConfiguracionSistemaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionSistema
        fields = (
            "id",
            "nombre_sistema",
            "institucion",
            "logo",
            "zona_horaria",
            "correo_contacto",
            "telefono_contacto",
        )
        read_only_fields = ("id",)
