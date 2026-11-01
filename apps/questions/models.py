"""Modelos del banco de preguntas."""

from django.conf import settings
from django.db import models
from django.db.models import Q


class EstadoContenido(models.TextChoices):
    ACTIVO = "Activo", "Activo"
    INACTIVO = "Inactivo", "Inactivo"


class TipoPregunta(models.TextChoices):
    MULTIPLE = "MULTIPLE", "Selección múltiple"
    VERDADERO_FALSO = "VERDADERO_FALSO", "Verdadero o falso"


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoContenido.choices,
        default=EstadoContenido.ACTIVO,
    )

    class Meta:
        db_table = "categorias"
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["nombre"], name="idx_categorias_nombre"),
            models.Index(fields=["estado"], name="idx_categorias_estado"),
        ]

    def __str__(self):
        return self.nombre


class Pregunta(models.Model):
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        db_column="categoria_id",
        related_name="preguntas",
    )
    tipo = models.CharField(
        max_length=50,
        choices=TipoPregunta.choices,
        default=TipoPregunta.MULTIPLE,
    )
    texto_base = models.TextField(null=True, blank=True)
    enunciado = models.TextField()
    retroalimentacion = models.TextField(null=True, blank=True)
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    estado = models.CharField(
        max_length=20,
        choices=EstadoContenido.choices,
        default=EstadoContenido.ACTIVO,
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        db_column="creado_por",
        related_name="preguntas_creadas",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "preguntas"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(puntaje__gt=0),
                name="ck_preguntas_puntaje",
            ),
        ]
        indexes = [
            models.Index(
                fields=["categoria", "estado"],
                name="idx_preg_cat_estado",
            ),
            models.Index(fields=["tipo"], name="idx_preg_tipo"),
        ]

    def __str__(self):
        return self.enunciado[:80]


class OpcionRespuesta(models.Model):
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        db_column="pregunta_id",
        related_name="opciones",
    )
    texto_opcion = models.TextField()
    es_correcta = models.BooleanField(default=False)
    retroalimentacion = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "opciones_respuesta"
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["pregunta", "es_correcta"],
                name="idx_opc_preg_correcta",
            ),
        ]

    def __str__(self):
        return self.texto_opcion[:80]
