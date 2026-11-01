"""Serializadores que nunca exponen respuestas correctas durante una prueba."""

from rest_framework import serializers

from .models import Intento
from .services import obtener_resultado_final, preguntas_presentacion


class IntentoResumenSerializer(serializers.ModelSerializer):
    cuestionario_nombre = serializers.ReadOnlyField(source="cuestionario.nombre")
    usuario_nombre = serializers.ReadOnlyField(source="usuario.nombre")
    aprobado = serializers.SerializerMethodField()

    class Meta:
        model = Intento
        fields = (
            "id",
            "cuestionario",
            "cuestionario_nombre",
            "usuario",
            "usuario_nombre",
            "numero_intento",
            "fecha_inicio",
            "fecha_fin",
            "duracion_segundos",
            "puntaje_obtenido",
            "calificacion_final",
            "aprobado",
            "estado",
        )
        read_only_fields = fields

    def get_aprobado(self, intento):
        if intento.calificacion_final is None:
            return None
        return obtener_resultado_final(intento)["aprobado"]


class IntentoPresentacionSerializer(serializers.ModelSerializer):
    cuestionario_nombre = serializers.ReadOnlyField(source="cuestionario.nombre")
    fecha_limite = serializers.SerializerMethodField()
    segundos_restantes = serializers.SerializerMethodField()
    calificacion_maxima = serializers.SerializerMethodField()
    revision_disponible = serializers.SerializerMethodField()
    preguntas = serializers.SerializerMethodField()

    class Meta:
        model = Intento
        fields = (
            "id",
            "cuestionario",
            "cuestionario_nombre",
            "numero_intento",
            "fecha_inicio",
            "fecha_fin",
            "duracion_segundos",
            "estado",
            "puntaje_obtenido",
            "calificacion_final",
            "calificacion_maxima",
            "revision_disponible",
            "fecha_limite",
            "segundos_restantes",
            "preguntas",
        )
        read_only_fields = fields

    def get_calificacion_maxima(self, intento):
        return intento.cuestionario.calificacion_maxima

    def get_revision_disponible(self, intento):
        return (
            intento.estado != "EN_PROGRESO"
            and intento.cuestionario.permitir_revision
        )

    def get_fecha_limite(self, intento):
        from datetime import timedelta

        limite_por_tiempo = intento.fecha_inicio + timedelta(
            minutes=intento.cuestionario.tiempo_limite_minutos
        )
        return min(limite_por_tiempo, intento.cuestionario.fecha_cierre)

    def get_segundos_restantes(self, intento):
        from django.utils import timezone

        restante = (self.get_fecha_limite(intento) - timezone.now()).total_seconds()
        return max(0, int(restante)) if intento.estado == "EN_PROGRESO" else 0

    def get_preguntas(self, intento):
        respuestas = {
            respuesta.pregunta_id: respuesta
            for respuesta in intento.respuestas.select_related(
                "opcion_seleccionada"
            ).all()
        }
        mostrar_revision = self.get_revision_disponible(intento)
        resultado = []
        for relacion, opciones in preguntas_presentacion(intento):
            pregunta = relacion.pregunta
            respuesta = respuestas[pregunta.pk]
            pregunta_data = {
                "id": pregunta.pk,
                "texto_base": pregunta.texto_base,
                "enunciado": pregunta.enunciado,
                "tipo": pregunta.tipo,
                "puntaje": relacion.puntaje,
                "opciones": [
                    {
                        "id": opcion.pk,
                        "texto_opcion": opcion.texto_opcion,
                        **(
                            {"es_correcta": opcion.es_correcta}
                            if mostrar_revision
                            else {}
                        ),
                    }
                    for opcion in opciones
                ],
                "opcion_seleccionada_id": respuesta.opcion_seleccionada_id,
                "marcada_para_revision": respuesta.marcada_para_revision,
            }
            if mostrar_revision:
                pregunta_data["es_correcta"] = respuesta.es_correcta
                pregunta_data["puntaje_obtenido"] = respuesta.puntaje_obtenido
                pregunta_data["retroalimentacion"] = pregunta.retroalimentacion
            resultado.append(pregunta_data)
        return resultado


class RespuestaEntradaSerializer(serializers.Serializer):
    pregunta_id = serializers.IntegerField(min_value=1)
    opcion_seleccionada_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )
    marcada_para_revision = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not {"opcion_seleccionada_id", "marcada_para_revision"}.intersection(
            attrs
        ):
            raise serializers.ValidationError(
                "Debes indicar una opción o actualizar la marca de revisión."
            )
        return attrs


class IntentoFinalizadoSerializer(serializers.ModelSerializer):
    cuestionario_nombre = serializers.ReadOnlyField(source="cuestionario.nombre")
    calificacion_maxima = serializers.ReadOnlyField(
        source="cuestionario.calificacion_maxima"
    )
    aprobado = serializers.SerializerMethodField()
    revision_disponible = serializers.SerializerMethodField()
    preguntas = serializers.SerializerMethodField()

    class Meta:
        model = Intento
        fields = (
            "id",
            "cuestionario_nombre",
            "numero_intento",
            "estado",
            "calificacion_final",
            "calificacion_maxima",
            "aprobado",
            "revision_disponible",
            "preguntas",
        )
        read_only_fields = fields

    def get_aprobado(self, intento):
        return obtener_resultado_final(intento)["aprobado"]

    def get_revision_disponible(self, intento):
        return (
            intento.estado != "EN_PROGRESO"
            and intento.cuestionario.permitir_revision
        )

    def get_preguntas(self, intento):
        if not self.get_revision_disponible(intento):
            return []
        return IntentoPresentacionSerializer(
            intento,
            context={**self.context, "forzar_revision": True},
        ).data["preguntas"]
