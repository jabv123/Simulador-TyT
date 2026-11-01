"""Pruebas de validaciones del banco de preguntas."""

from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Rol, Usuario
from apps.questions.models import (
    Categoria,
    EstadoContenido,
    Pregunta,
    TipoPregunta,
)
from apps.quizzes.services import validar_preguntas
from rest_framework.exceptions import ValidationError


class PreguntasApiTests(APITestCase):
    def setUp(self):
        rol, _ = Rol.objects.get_or_create(nombre="Administrador")
        self.usuario = Usuario.objects.create_user(
            "ADMIN-1",
            "Admin-password-123",
            nombre="Administradora",
            correo="admin@test.local",
            rol=rol,
        )
        self.client.force_authenticate(self.usuario)
        self.categoria = Categoria.objects.create(nombre="Razonamiento")

    def datos_pregunta(self, tipo="MULTIPLE", opciones=None):
        return {
            "categoria": self.categoria.pk,
            "tipo": tipo,
            "enunciado": "¿Cuánto es dos más dos?",
            "puntaje": "1.00",
            "opciones": opciones
            or [
                {"texto_opcion": "Cuatro", "es_correcta": True},
                {"texto_opcion": "Cinco", "es_correcta": False},
            ],
        }

    def test_rechaza_pregunta_sin_una_respuesta_correcta(self):
        datos = self.datos_pregunta(
            opciones=[
                {"texto_opcion": "A", "es_correcta": False},
                {"texto_opcion": "B", "es_correcta": False},
            ]
        )
        respuesta = self.client.post(
            reverse("questions:preguntas"),
            datos,
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.categoria.preguntas.count(), 0)

    def test_verdadero_falso_exige_exactamente_dos_opciones(self):
        respuesta = self.client.post(
            reverse("questions:preguntas"),
            self.datos_pregunta(
                "VERDADERO_FALSO",
                [
                    {"texto_opcion": "Verdadero", "es_correcta": True},
                    {"texto_opcion": "Falso", "es_correcta": False},
                    {"texto_opcion": "Tal vez", "es_correcta": False},
                ],
            ),
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.categoria.preguntas.count(), 0)

    def test_crea_pregunta_valida_con_una_correcta(self):
        respuesta = self.client.post(
            reverse("questions:preguntas"),
            self.datos_pregunta(),
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(
            respuesta.data["opciones"][0]["es_correcta"],
            True,
        )

    def test_categoria_unica_y_se_puede_desactivar_sin_eliminar(self):
        duplicada = self.client.post(
            reverse("questions:categorias"),
            {"nombre": " razonamiento "},
            format="json",
        )
        self.assertEqual(duplicada.status_code, 400)
        self.assertIn("nombre", duplicada.data)

        eliminacion = self.client.delete(
            reverse("questions:categoria-detalle", args=[self.categoria.pk])
        )
        self.assertEqual(eliminacion.status_code, 204)
        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.estado, EstadoContenido.INACTIVO)
        self.assertTrue(Categoria.objects.filter(pk=self.categoria.pk).exists())

    def test_categoria_inactiva_no_acepta_preguntas_nuevas(self):
        self.categoria.estado = EstadoContenido.INACTIVO
        self.categoria.save(update_fields=["estado"])
        respuesta = self.client.post(
            reverse("questions:preguntas"),
            self.datos_pregunta(),
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("categoria", respuesta.data)

    def test_multipl_choice_admite_hasta_cuatro_y_rechaza_cinco(self):
        opciones = [
            {"texto_opcion": f"Opción {indice}", "es_correcta": indice == 1}
            for indice in range(1, 6)
        ]
        respuesta = self.client.post(
            reverse("questions:preguntas"),
            self.datos_pregunta(opciones=opciones),
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("entre 2 y 4", str(respuesta.data["opciones"]))

    def test_verdadero_falso_exige_opciones_con_nombres_correctos(self):
        respuesta = self.client.post(
            reverse("questions:preguntas"),
            self.datos_pregunta(
                "VERDADERO_FALSO",
                [
                    {"texto_opcion": "Sí", "es_correcta": True},
                    {"texto_opcion": "No", "es_correcta": False},
                ],
            ),
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Verdadero", str(respuesta.data["opciones"]))

        valida = self.client.post(
            reverse("questions:preguntas"),
            {
                **self.datos_pregunta(
                    "VERDADERO_FALSO",
                    [
                        {"texto_opcion": "Verdadero", "es_correcta": True},
                        {"texto_opcion": "Falso", "es_correcta": False},
                    ],
                ),
                "enunciado": "La tierra es redonda.",
            },
            format="json",
        )
        self.assertEqual(valida.status_code, 201, valida.data)

    def test_enunciado_duplicado_normalizado_no_se_guarda(self):
        original = self.client.post(
            reverse("questions:preguntas"),
            {
                **self.datos_pregunta(),
                "enunciado": "  ¿Cuál   es la RAZÓN?  ",
            },
            format="json",
        )
        self.assertEqual(original.status_code, 201, original.data)

        duplicada = self.client.post(
            reverse("questions:preguntas"),
            {
                **self.datos_pregunta(),
                "enunciado": "¿Cual es la razon?",
            },
            format="json",
        )
        self.assertEqual(duplicada.status_code, 400)
        self.assertIn("enunciado", duplicada.data)
        self.assertEqual(Pregunta.objects.count(), 1)

    def test_pregunta_asigna_creador_y_edicion_anidada_es_atomica(self):
        respuesta = self.client.post(
            reverse("questions:preguntas"),
            self.datos_pregunta(),
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        pregunta = Pregunta.objects.get(pk=respuesta.data["id"])
        self.assertEqual(pregunta.creado_por_id, self.usuario.pk)
        self.assertEqual(pregunta.opciones.count(), 2)

        actualizada = self.client.patch(
            reverse("questions:pregunta-detalle", args=[pregunta.pk]),
            {
                "opciones": [
                    {"texto_opcion": "Actualizada correcta", "es_correcta": True},
                    {"texto_opcion": "Actualizada incorrecta", "es_correcta": False},
                    {"texto_opcion": "Tercera", "es_correcta": False},
                ],
                "enunciado": "Enunciado actualizado",
            },
            format="json",
        )
        self.assertEqual(actualizada.status_code, 200, actualizada.data)
        pregunta.refresh_from_db()
        self.assertEqual(pregunta.opciones.count(), 3)
        self.assertEqual(pregunta.enunciado, "Enunciado actualizado")

    def test_eliminar_pregunta_solo_desactiva_y_conserva_opciones(self):
        creada = self.client.post(
            reverse("questions:preguntas"),
            self.datos_pregunta(),
            format="json",
        )
        pregunta_id = creada.data["id"]
        respuesta = self.client.delete(
            reverse("questions:pregunta-detalle", args=[pregunta_id])
        )
        self.assertEqual(respuesta.status_code, 204)
        pregunta = Pregunta.objects.get(pk=pregunta_id)
        self.assertEqual(pregunta.estado, EstadoContenido.INACTIVO)
        self.assertEqual(pregunta.opciones.count(), 2)

    def test_pregunta_inactiva_no_se_agrega_a_cuestionario_nuevo(self):
        pregunta = Pregunta.objects.create(
            categoria=self.categoria,
            enunciado="Pregunta que será desactivada",
            estado=EstadoContenido.INACTIVO,
            puntaje=Decimal("1.00"),
        )
        with self.assertRaises(ValidationError):
            validar_preguntas(
                [{"pregunta": pregunta, "puntaje": Decimal("1.00")}]
            )

    def test_listado_preguntas_busca_filtra_y_pagina(self):
        segunda_categoria = Categoria.objects.create(nombre="Álgebra")
        for indice in range(25):
            Pregunta.objects.create(
                categoria=self.categoria if indice < 12 else segunda_categoria,
                tipo=(
                    TipoPregunta.MULTIPLE
                    if indice % 2 == 0
                    else TipoPregunta.VERDADERO_FALSO
                ),
                enunciado=f"Pregunta de prueba número {indice}",
                estado=(
                    EstadoContenido.INACTIVO
                    if indice == 0
                    else EstadoContenido.ACTIVO
                ),
                puntaje=Decimal("1.00"),
            )
        pagina = self.client.get("/api/preguntas/?page_size=5")
        self.assertEqual(pagina.status_code, 200, pagina.data)
        self.assertEqual(pagina.data["count"], 25)
        self.assertEqual(len(pagina.data["results"]), 5)
        filtrada = self.client.get(
            f"/api/preguntas/?categoria={segunda_categoria.pk}"
            "&tipo=VERDADERO_FALSO&estado=Activo&search=21"
        )
        self.assertEqual(filtrada.status_code, 200, filtrada.data)
        self.assertEqual(filtrada.data["count"], 1)
        self.assertEqual(
            filtrada.data["results"][0]["enunciado"],
            "Pregunta de prueba número 21",
        )

    def test_estudiante_no_puede_administrar_categorias_ni_preguntas(self):
        estudiante_rol = Rol.objects.get(nombre="Estudiante")
        estudiante = Usuario.objects.create_user(
            "Q-STUDENT",
            "Student-Strong-123!",
            nombre="Estudiante",
            correo="question-student@test.local",
            rol=estudiante_rol,
        )
        self.client.force_authenticate(estudiante)
        listado = self.client.get(reverse("questions:preguntas"))
        creacion = self.client.post(
            reverse("questions:categorias"),
            {"nombre": "Sin permiso"},
            format="json",
        )
        self.assertEqual(listado.status_code, 403)
        self.assertEqual(creacion.status_code, 403)
