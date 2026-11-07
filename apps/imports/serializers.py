"""Serializadores de importaciones Excel."""

import json
from pathlib import PurePath

from rest_framework import serializers

from apps.quizzes.models import Cuestionario

from .models import Importacion


class ArchivoImportacionSerializer(serializers.Serializer):
    archivo = serializers.FileField()
    cuestionario_id = serializers.PrimaryKeyRelatedField(
        source="cuestionario",
        queryset=Cuestionario.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_archivo(self, archivo):
        from .services import TAMANO_MAXIMO_ARCHIVO

        if PurePath(archivo.name).suffix.casefold() != ".xlsx":
            raise serializers.ValidationError("El archivo debe tener formato .xlsx.")
        if archivo.size > TAMANO_MAXIMO_ARCHIVO:
            raise serializers.ValidationError("El archivo no puede superar los 10 MB.")
        return archivo


class PrevisualizacionImportacionSerializer(ArchivoImportacionSerializer):
    cuestionario_id = serializers.PrimaryKeyRelatedField(
        source="cuestionario",
        queryset=Cuestionario.objects.all(),
        required=False,
        allow_null=True,
    )


class ImportacionSerializer(serializers.ModelSerializer):
    registros_duplicados = serializers.SerializerMethodField()
    registros_con_errores = serializers.SerializerMethodField()

    class Meta:
        model = Importacion
        fields = (
            "id",
            "usuario",
            "cuestionario",
            "nombre_archivo",
            "fecha_importacion",
            "total_registros",
            "registros_exitosos",
            "registros_fallidos",
            "registros_duplicados",
            "registros_con_errores",
            "detalles_error",
            "estado_resultado",
        )
        read_only_fields = fields

    @staticmethod
    def obtener_detalles(importacion):
        detalles = json.loads(importacion.detalles_error or "{}")
        if isinstance(detalles, list):
            return {"duplicadas": [], "errores": detalles}
        return detalles

    def get_registros_duplicados(self, importacion):
        return len(self.obtener_detalles(importacion).get("duplicadas", []))

    def get_registros_con_errores(self, importacion):
        return len(self.obtener_detalles(importacion).get("errores", []))
