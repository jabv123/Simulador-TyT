"""Registro de importaciones de preguntas desde Excel."""

from django.conf import settings
from django.db import models


class EstadoImportacion(models.TextChoices):
    EN_PROCESO = "En proceso", "En proceso"
    EXITOSO = "Exitoso", "Exitoso"
    PARCIAL = "Parcial", "Parcial"
    SIN_CAMBIOS = "Sin cambios", "Sin cambios"
    FALLIDO = "Fallido", "Fallido"


class Importacion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        db_column="usuario_id",
        related_name="importaciones",
        null=True,
        blank=True,
    )
    cuestionario = models.ForeignKey(
        "quizzes.Cuestionario",
        on_delete=models.SET_NULL,
        db_column="cuestionario_id",
        related_name="importaciones",
        null=True,
        blank=True,
    )
    nombre_archivo = models.CharField(max_length=255)
    fecha_importacion = models.DateTimeField(auto_now_add=True)
    total_registros = models.PositiveIntegerField(default=0)
    registros_exitosos = models.PositiveIntegerField(default=0)
    registros_fallidos = models.PositiveIntegerField(default=0)
    detalles_error = models.TextField(null=True, blank=True)
    estado_resultado = models.CharField(
        max_length=50,
        choices=EstadoImportacion.choices,
        default=EstadoImportacion.EXITOSO,
    )

    class Meta:
        db_table = "importaciones"
        ordering = ["-fecha_importacion"]
        indexes = [
            models.Index(
                fields=["usuario", "fecha_importacion"],
                name="idx_imp_usuario_fecha",
            ),
            models.Index(
                fields=["estado_resultado", "fecha_importacion"],
                name="idx_imp_estado_fecha",
            ),
            models.Index(
                fields=["cuestionario", "fecha_importacion"],
                name="idx_imp_cuestionario_fecha",
            ),
        ]

    def __str__(self):
        return f"{self.nombre_archivo} ({self.estado_resultado})"
