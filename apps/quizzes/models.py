"""Modelos de cuestionarios y preguntas asociadas."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.questions.models import Pregunta


class EstadoCuestionario(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"
    PROGRAMADO = "PROGRAMADO", "Programado"
    DISPONIBLE = "DISPONIBLE", "Disponible"
    CERRADO = "CERRADO", "Cerrado"


class Cuestionario(models.Model):
    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="docente_id",
        related_name="cuestionarios_creados",
        null=True,
        blank=True,
    )
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    fecha_apertura = models.DateTimeField()
    fecha_cierre = models.DateTimeField()
    tiempo_limite_minutos = models.PositiveIntegerField()
    intentos_permitidos = models.PositiveIntegerField()
    calificacion_maxima = models.DecimalField(max_digits=5, decimal_places=2)
    calificacion_aprobacion = models.DecimalField(max_digits=5, decimal_places=2)
    mezclar_preguntas = models.BooleanField(default=True)
    mezclar_respuestas = models.BooleanField(default=True)
    permitir_revision = models.BooleanField(default=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoCuestionario.choices,
        default=EstadoCuestionario.BORRADOR,
    )
    preguntas = models.ManyToManyField(
        Pregunta,
        through="CuestionarioPregunta",
        related_name="cuestionarios",
    )

    class Meta:
        db_table = "cuestionarios"
        ordering = ["-fecha_apertura", "nombre"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_cierre__gt=models.F("fecha_apertura")),
                name="ck_cuestionarios_fechas",
            ),
            models.CheckConstraint(
                condition=Q(calificacion_maxima__gt=0),
                name="ck_cuestionarios_nota_maxima",
            ),
            models.CheckConstraint(
                condition=Q(calificacion_aprobacion__gte=0)
                & Q(calificacion_aprobacion__lte=models.F("calificacion_maxima")),
                name="ck_cuestionarios_nota_aprobacion",
            ),
            models.CheckConstraint(
                condition=Q(calificacion_aprobacion__gte=0),
                name="ck_cuestionarios_nota_no_negativa",
            ),
            models.CheckConstraint(
                condition=Q(tiempo_limite_minutos__gt=0),
                name="ck_cuestionarios_tiempo",
            ),
            models.CheckConstraint(
                condition=Q(intentos_permitidos__gt=0),
                name="ck_cuestionarios_intentos",
            ),
            models.CheckConstraint(
                condition=Q(estado__in=EstadoCuestionario.values),
                name="ck_cuestionarios_estado",
            ),
        ]
        indexes = [
            models.Index(fields=["estado"], name="idx_cuestionarios_estado"),
            models.Index(
                fields=["estado", "fecha_apertura", "fecha_cierre"],
                name="idx_cuestionario_disponible",
            ),
            models.Index(fields=["nombre"], name="idx_cuestionario_nombre"),
        ]

    def clean(self):
        errores = {}
        if self.fecha_apertura and self.fecha_cierre:
            if self.fecha_cierre <= self.fecha_apertura:
                errores["fecha_cierre"] = (
                    "La fecha de cierre debe ser posterior a la apertura."
                )
        if self.calificacion_maxima is not None:
            if self.calificacion_maxima <= 0:
                errores["calificacion_maxima"] = (
                    "La calificación máxima debe ser mayor que cero."
                )
        if self.calificacion_aprobacion is not None:
            if self.calificacion_aprobacion < 0:
                errores["calificacion_aprobacion"] = (
                    "La nota de aprobación no puede ser negativa."
                )
            elif (
                self.calificacion_maxima is not None
                and self.calificacion_aprobacion > self.calificacion_maxima
            ):
                errores["calificacion_aprobacion"] = (
                    "La nota de aprobación no puede superar la máxima."
                )
        if (
            self.tiempo_limite_minutos is not None
            and self.tiempo_limite_minutos <= 0
        ):
            errores["tiempo_limite_minutos"] = (
                "El tiempo límite debe ser mayor que cero."
            )
        if self.intentos_permitidos is not None and self.intentos_permitidos <= 0:
            errores["intentos_permitidos"] = (
                "La cantidad de intentos debe ser mayor que cero."
            )
        if errores:
            raise ValidationError(errores)

    def estado_efectivo(self, ahora=None):
        """Calcula el estado por fechas sin publicar un borrador manual."""
        if self.estado in {
            EstadoCuestionario.BORRADOR,
            EstadoCuestionario.CERRADO,
        }:
            return self.estado

        ahora = ahora or timezone.now()
        if ahora < self.fecha_apertura:
            return EstadoCuestionario.PROGRAMADO
        if ahora > self.fecha_cierre:
            return EstadoCuestionario.CERRADO
        return EstadoCuestionario.DISPONIBLE

    @property
    def puntaje_total_posible(self):
        return sum(
            (item.puntaje for item in self.preguntas_configuradas.all()),
            start=Decimal("0"),
        )

    def __str__(self):
        return self.nombre


class CuestionarioPregunta(models.Model):
    cuestionario = models.ForeignKey(
        Cuestionario,
        on_delete=models.CASCADE,
        db_column="cuestionario_id",
        related_name="preguntas_configuradas",
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.PROTECT,
        db_column="pregunta_id",
        related_name="configuraciones_cuestionario",
    )
    orden = models.PositiveIntegerField(default=1)
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, default=1)

    class Meta:
        db_table = "cuestionario_preguntas"
        ordering = ["orden", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["cuestionario", "pregunta"],
                name="uk_cuestionario_pregunta",
            ),
            models.CheckConstraint(
                condition=Q(puntaje__gt=0),
                name="ck_cuestionario_preguntas_puntaje",
            ),
        ]
        indexes = [
            models.Index(fields=["pregunta"], name="idx_cp_pregunta"),
            models.Index(
                fields=["cuestionario", "orden"],
                name="idx_cp_cuestionario_orden",
            ),
        ]

    def __str__(self):
        return f"{self.cuestionario}: pregunta {self.pregunta_id}"
