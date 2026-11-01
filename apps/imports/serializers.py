"""Serializadores de importaciones Excel."""

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
        required=True,
    )


class ImportacionSerializer(serializers.ModelSerializer):
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
            "detalles_error",
            "estado_resultado",
        )
        read_only_fields = fields
