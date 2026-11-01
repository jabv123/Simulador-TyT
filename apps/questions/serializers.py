"""Serializadores de categorías, preguntas y opciones."""

from rest_framework import serializers

from .models import Categoria, OpcionRespuesta, Pregunta, TipoPregunta
from .services import (
    actualizar_pregunta,
    crear_pregunta,
    validar_enunciado_unico,
    validar_opciones,
)


class CategoriaSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )

    class Meta:
        model = Categoria
        fields = ("id", "nombre", "descripcion", "estado")
        read_only_fields = ("id",)

    def validate_nombre(self, valor):
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError("El nombre de la categoría es obligatorio.")
        consulta = Categoria.objects.filter(nombre__iexact=valor)
        if self.instance:
            consulta = consulta.exclude(pk=self.instance.pk)
        if consulta.exists():
            raise serializers.ValidationError("Ya existe una categoría con ese nombre.")
        return valor


class OpcionRespuestaSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpcionRespuesta
        fields = ("id", "texto_opcion", "es_correcta", "retroalimentacion")
        read_only_fields = ("id",)


class PreguntaSerializer(serializers.ModelSerializer):
    opciones = OpcionRespuestaSerializer(many=True, required=False)
    categoria_nombre = serializers.ReadOnlyField(source="categoria.nombre")
    creado_por_nombre = serializers.ReadOnlyField(source="creado_por.nombre")

    class Meta:
        model = Pregunta
        fields = (
            "id",
            "categoria",
            "categoria_nombre",
            "tipo",
            "texto_base",
            "enunciado",
            "retroalimentacion",
            "puntaje",
            "estado",
            "creado_por",
            "creado_por_nombre",
            "opciones",
        )
        read_only_fields = ("id", "creado_por", "creado_por_nombre")

    def validate_tipo(self, valor):
        if valor not in TipoPregunta.values:
            raise serializers.ValidationError(
                "El tipo debe ser MULTIPLE o VERDADERO_FALSO."
            )
        return valor

    def validate_categoria(self, categoria):
        if categoria.estado != "Activo" and (
            self.instance is None or categoria.pk != self.instance.categoria_id
        ):
            raise serializers.ValidationError(
                "No se pueden crear preguntas en una categoría inactiva."
            )
        return categoria

    def validate_puntaje(self, valor):
        if valor <= 0:
            raise serializers.ValidationError("El puntaje debe ser mayor que cero.")
        return valor

    def validate(self, attrs):
        opciones = attrs.get("opciones")
        tipo = attrs.get(
            "tipo",
            self.instance.tipo if self.instance else TipoPregunta.MULTIPLE,
        )
        if opciones is not None:
            validar_opciones(tipo, opciones)
        elif self.instance is None:
            raise serializers.ValidationError(
                {"opciones": "Debes incluir las opciones de la pregunta."}
            )
        categoria = attrs.get(
            "categoria",
            self.instance.categoria if self.instance else None,
        )
        enunciado = attrs.get(
            "enunciado",
            self.instance.enunciado if self.instance else None,
        )
        if categoria is not None and enunciado:
            validar_enunciado_unico(
                enunciado,
                categoria.pk,
                excluir_id=self.instance.pk if self.instance else None,
            )
        return attrs

    def create(self, validated_data):
        opciones = validated_data.pop("opciones")
        return crear_pregunta(
            datos=validated_data,
            opciones=opciones,
            creado_por=self.context["request"].user,
        )

    def update(self, instance, validated_data):
        opciones = validated_data.pop("opciones", None)
        return actualizar_pregunta(
            pregunta=instance,
            datos=validated_data,
            opciones=opciones,
        )
