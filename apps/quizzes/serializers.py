"""Serializadores de configuración y consulta de cuestionarios."""

from decimal import Decimal

from rest_framework import serializers

from apps.questions.models import Pregunta

from .models import (
    Cuestionario,
    CuestionarioPregunta,
    EstadoCuestionario,
)
from .services import (
    actualizar_cuestionario,
    crear_cuestionario,
    validar_datos_cuestionario,
)


class PreguntaCuestionarioSerializer(serializers.ModelSerializer):
    pregunta = serializers.PrimaryKeyRelatedField(queryset=Pregunta.objects.all())
    orden = serializers.IntegerField(min_value=1, required=False)
    puntaje = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        default=Decimal("1.00"),
    )

    class Meta:
        model = CuestionarioPregunta
        fields = ("pregunta", "orden", "puntaje")

    def validate_puntaje(self, valor):
        if valor <= 0:
            raise serializers.ValidationError("El puntaje por pregunta debe ser mayor que cero.")
        return valor


class CuestionarioSerializer(serializers.ModelSerializer):
    preguntas = PreguntaCuestionarioSerializer(
        source="preguntas_configuradas",
        many=True,
        required=False,
    )
    docente_nombre = serializers.ReadOnlyField(source="docente.nombre")
    estado_efectivo = serializers.SerializerMethodField()
    puntaje_total_posible = serializers.SerializerMethodField()

    class Meta:
        model = Cuestionario
        fields = (
            "id",
            "docente",
            "docente_nombre",
            "nombre",
            "descripcion",
            "fecha_apertura",
            "fecha_cierre",
            "tiempo_limite_minutos",
            "intentos_permitidos",
            "calificacion_maxima",
            "calificacion_aprobacion",
            "mezclar_preguntas",
            "mezclar_respuestas",
            "permitir_revision",
            "estado",
            "estado_efectivo",
            "puntaje_total_posible",
            "preguntas",
        )
        read_only_fields = ("id", "docente", "docente_nombre")

    def validate_estado(self, valor):
        if valor not in EstadoCuestionario.values:
            raise serializers.ValidationError(
                "El estado debe ser BORRADOR, PROGRAMADO, DISPONIBLE o CERRADO."
            )
        return valor

    def get_estado_efectivo(self, cuestionario):
        return cuestionario.estado_efectivo()

    def get_puntaje_total_posible(self, cuestionario):
        return cuestionario.puntaje_total_posible

    def validate(self, attrs):
        preguntas = attrs.get("preguntas_configuradas")
        datos = {
            key: value
            for key, value in attrs.items()
            if key != "preguntas_configuradas"
        }
        if self.instance:
            for campo in (
                "fecha_apertura",
                "fecha_cierre",
                "tiempo_limite_minutos",
                "intentos_permitidos",
                "calificacion_maxima",
                "calificacion_aprobacion",
            ):
                datos.setdefault(campo, getattr(self.instance, campo))
        validar_datos_cuestionario(datos)
        if preguntas is not None:
            for indice, item in enumerate(preguntas, start=1):
                item.setdefault("orden", indice)
        return attrs

    def create(self, validated_data):
        preguntas = validated_data.pop("preguntas_configuradas", None)
        return crear_cuestionario(
            datos=validated_data,
            preguntas=preguntas,
            docente=self.context["request"].user,
        )

    def update(self, instance, validated_data):
        preguntas = validated_data.pop("preguntas_configuradas", None)
        return actualizar_cuestionario(
            cuestionario=instance,
            datos=validated_data,
            preguntas=preguntas,
        )


class CuestionarioDisponibleSerializer(CuestionarioSerializer):
    intentos_usados = serializers.SerializerMethodField()
    intentos_restantes = serializers.SerializerMethodField()

    class Meta(CuestionarioSerializer.Meta):
        fields = CuestionarioSerializer.Meta.fields + (
            "intentos_usados",
            "intentos_restantes",
        )
        read_only_fields = fields

    def get_intentos_usados(self, cuestionario):
        return getattr(cuestionario, "intentos_usados", 0)

    def get_intentos_restantes(self, cuestionario):
        return max(
            0,
            cuestionario.intentos_permitidos
            - self.get_intentos_usados(cuestionario),
        )


class ActualizarPreguntaCuestionarioSerializer(serializers.Serializer):
    orden = serializers.IntegerField(min_value=1, required=False)
    puntaje = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Debes indicar el orden o el puntaje que deseas actualizar."
            )
        return attrs
