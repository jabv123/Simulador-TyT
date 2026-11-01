"""Configuración institucional del simulador."""

from django.db import models


class ConfiguracionSistema(models.Model):
    nombre_sistema = models.CharField(max_length=150)
    institucion = models.CharField(max_length=150)
    logo = models.CharField(max_length=255, null=True, blank=True)
    zona_horaria = models.CharField(max_length=50, default="America/Bogota")
    correo_contacto = models.EmailField(max_length=150, null=True, blank=True)
    telefono_contacto = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = "configuracion_sistema"
        verbose_name = "Configuración del sistema"
        verbose_name_plural = "Configuración del sistema"

    def __str__(self):
        return self.nombre_sistema
