"""Pruebas de la página pública y configuración institucional."""

from django.test import TestCase
from django.urls import reverse

from .models import ConfiguracionSistema


class PaginaInicioTests(TestCase):
    def test_inicio_carga_la_interfaz_web(self):
        respuesta = self.client.get(reverse("inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Simulador Saber TyT")
        self.assertContains(respuesta, "static/js/app.js")
        self.assertContains(respuesta, "type=\"module\"")
        self.assertContains(respuesta, "toast-region")

    def test_acceso_denegado_carga_una_pagina_amigable(self):
        respuesta = self.client.get(reverse("acceso-denegado"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Acceso denegado")
        self.assertContains(respuesta, "Volver al inicio")

    def test_configuracion_publica_retorna_valores_institucionales(self):
        configuracion = ConfiguracionSistema.objects.first()
        configuracion.nombre_sistema = "Simulador de prueba"
        configuracion.institucion = "Institución de prueba"
        configuracion.save()
        respuesta = self.client.get(
            reverse("core:configuracion-publica")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.data["nombre_sistema"],
            "Simulador de prueba",
        )
