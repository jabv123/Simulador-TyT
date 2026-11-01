"""Modelos de intentos y respuestas de estudiantes."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.questions.models import OpcionRespuesta, Pregunta


class EstadoIntento(models.TextChoices):
    EN_PROGRESO = "EN_PROGRESO", "En progreso"
    FINALIZADO = "FINALIZADO", "Finalizado"
    TIEMPO_AGOTADO = "TIEMPO_AGOTADO", "Tiempo agotado"


class Intento(models.Model):
    cuestionario = models.ForeignKey(
        "quizzes.Cuestionario",
        on_delete=models.CASCADE,
        db_column="cuestionario_id",
        related_name="intentos",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="usuario_id",
        related_name="intentos",
    )
    numero_intento = models.PositiveIntegerField(default=1)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    duracion_segundos = models.PositiveIntegerField(null=True, blank=True)
    puntaje_obtenido = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    calificacion_final = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoIntento.choices,
        default=EstadoIntento.EN_PROGRESO,
    )

    class Meta:
        db_table = "intentos"
        ordering = ["-fecha_inicio"]
        constraints = [
            models.UniqueConstraint(
                fields=["cuestionario", "usuario", "numero_intento"],
                name="uq_intento",
            ),
            models.CheckConstraint(
                condition=Q(estado__in=EstadoIntento.values),
                name="ck_intentos_estado",
            ),
        ]
        indexes = [
            models.Index(
                fields=["usuario", "estado"],
                name="idx_intentos_usuario_estado",
            ),
            models.Index(fields=["fecha_inicio"], name="idx_intentos_fecha_inicio"),
        ]

    def __str__(self):
        return f"{self.cuestionario} - intento {self.numero_intento}"


class RespuestaIntento(models.Model):
    intento = models.ForeignKey(
        Intento,
        on_delete=models.CASCADE,
        db_column="intento_id",
        related_name="respuestas",
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.PROTECT,
        db_column="pregunta_id",
        related_name="respuestas_intento",
    )
    opcion_seleccionada = models.ForeignKey(
        OpcionRespuesta,
        on_delete=models.SET_NULL,
        db_column="opcion_seleccionada_id",
        related_name="respuestas_intento",
        null=True,
        blank=True,
    )
    es_correcta = models.BooleanField(default=False)
    puntaje_obtenido = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    marcada_para_revision = models.BooleanField(default=False)
    fecha_respuesta = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "respuestas_intento"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["intento", "pregunta"],
                name="uk_intento_pregunta",
            ),
        ]
        indexes = [
            models.Index(fields=["pregunta"], name="idx_resp_pregunta"),
        ]

    def __str__(self):
        return f"Respuesta {self.pregunta_id} del intento {self.intento_id}"
