"""Pruebas de reglas de configuración de cuestionarios."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.accounts.models import Rol, Usuario
from apps.questions.models import Categoria, OpcionRespuesta, Pregunta
from apps.quizzes.models import (
    Cuestionario,
    CuestionarioPregunta,
    EstadoCuestionario,
)
from apps.quizzes.services import (
    crear_cuestionario,
    publicar_cuestionario,
)
from apps.attempts.models import Intento


class CuestionarioReglasTests(APITestCase):
    def setUp(self):
        rol = Rol.objects.get(nombre="Administrador")
        self.usuario = Usuario.objects.create_user(
            "DOC-1",
            "Password-segura-123",
            nombre="Docente de prueba",
            correo="docente@test.local",
            rol=rol,
        )
        self.categoria = Categoria.objects.create(nombre="Comprensión")
        self.pregunta = Pregunta.objects.create(
            categoria=self.categoria,
            enunciado="Enunciado de prueba",
            creado_por=self.usuario,
        )
        OpcionRespuesta.objects.create(
            pregunta=self.pregunta,
            texto_opcion="Correcta",
            es_correcta=True,
        )
        OpcionRespuesta.objects.create(
            pregunta=self.pregunta,
            texto_opcion="Incorrecta",
            es_correcta=False,
        )
        self.pregunta_dos = Pregunta.objects.create(
            categoria=self.categoria,
            enunciado="Segundo enunciado de prueba",
            creado_por=self.usuario,
        )
        OpcionRespuesta.objects.create(
            pregunta=self.pregunta_dos,
            texto_opcion="Correcta",
            es_correcta=True,
        )
        OpcionRespuesta.objects.create(
            pregunta=self.pregunta_dos,
            texto_opcion="Incorrecta",
            es_correcta=False,
        )

    def datos(self):
        ahora = timezone.now()
        return {
            "nombre": "Simulacro",
            "fecha_apertura": ahora + timedelta(hours=1),
            "fecha_cierre": ahora + timedelta(days=1),
            "tiempo_limite_minutos": 60,
            "intentos_permitidos": 2,
            "calificacion_maxima": Decimal("5.00"),
            "calificacion_aprobacion": Decimal("3.00"),
            "estado": "PROGRAMADO",
        }

    def test_rechaza_cierre_anterior_a_apertura(self):
        datos = self.datos()
        datos["fecha_cierre"] = datos["fecha_apertura"] - timedelta(minutes=1)
        with self.assertRaises(ValidationError):
            crear_cuestionario(
                datos=datos,
                preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
                docente=self.usuario,
            )

    def test_rechaza_calificacion_aprobacion_fuera_del_rango(self):
        datos = self.datos()
        datos["calificacion_aprobacion"] = Decimal("5.01")
        with self.assertRaises(ValidationError):
            crear_cuestionario(
                datos=datos,
                preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
                docente=self.usuario,
            )

    def test_rechaza_intentos_cero(self):
        datos = self.datos()
        datos["intentos_permitidos"] = 0
        with self.assertRaises(ValidationError):
            crear_cuestionario(
                datos=datos,
                preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
                docente=self.usuario,
            )

    def test_rechaza_tiempo_cero_y_calificacion_maxima_no_positiva(self):
        datos = self.datos()
        datos["tiempo_limite_minutos"] = 0
        with self.assertRaises(ValidationError):
            crear_cuestionario(
                datos=datos,
                preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
                docente=self.usuario,
            )
        datos = self.datos()
        datos["calificacion_maxima"] = Decimal("0")
        with self.assertRaises(ValidationError):
            crear_cuestionario(
                datos=datos,
                preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
                docente=self.usuario,
            )

    def test_rechaza_nota_de_aprobacion_negativa(self):
        datos = self.datos()
        datos["calificacion_aprobacion"] = Decimal("-0.01")
        with self.assertRaises(ValidationError):
            crear_cuestionario(
                datos=datos,
                preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
                docente=self.usuario,
            )

    def test_api_crea_y_devuelve_relaciones_de_preguntas(self):
        self.client.force_authenticate(self.usuario)
        datos = self.datos()
        respuesta = self.client.post(
            reverse("quizzes:cuestionarios"),
            {
                **datos,
                "fecha_apertura": datos["fecha_apertura"].isoformat(),
                "fecha_cierre": datos["fecha_cierre"].isoformat(),
                "preguntas": [
                    {
                        "pregunta": self.pregunta.pk,
                        "orden": 1,
                        "puntaje": "2.00",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(len(respuesta.data["preguntas"]), 1)
        self.assertEqual(respuesta.data["preguntas"][0]["puntaje"], "2.00")
        lista = self.client.get(reverse("quizzes:cuestionarios"))
        self.assertEqual(lista.status_code, 200)
        self.assertEqual(len(lista.data), 1)

    def test_validacion_del_modelo_rechaza_fechas_invalidas(self):
        datos = self.datos()
        cuestionario = Cuestionario(
            docente=self.usuario,
            **{
                **datos,
                "fecha_cierre": datos["fecha_apertura"],
            },
        )
        with self.assertRaises(DjangoValidationError):
            cuestionario.full_clean()

    def test_estado_efectivo_no_publica_un_borrador_manual(self):
        datos = self.datos()
        datos["estado"] = EstadoCuestionario.BORRADOR
        cuestionario = crear_cuestionario(
            datos=datos,
            preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
            docente=self.usuario,
        )
        self.assertEqual(
            cuestionario.estado_efectivo(),
            EstadoCuestionario.BORRADOR,
        )

    def test_no_crea_cuestionario_publicado_sin_preguntas(self):
        self.client.force_authenticate(self.usuario)
        datos = self.datos()
        datos["estado"] = EstadoCuestionario.DISPONIBLE
        respuesta = self.client.post(
            reverse("quizzes:cuestionarios"),
            {
                **datos,
                "fecha_apertura": timezone.now().isoformat(),
                "fecha_cierre": (timezone.now() + timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("preguntas", respuesta.data)

    def test_draft_sin_preguntas_se_puede_crear_pero_no_publicar(self):
        datos = self.datos()
        datos["estado"] = EstadoCuestionario.BORRADOR
        cuestionario = crear_cuestionario(datos=datos, docente=self.usuario)
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.post(
            reverse(
                "quizzes:cuestionario-publicar",
                args=[cuestionario.pk],
            )
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("preguntas", respuesta.data)

    def test_publicar_requiere_preguntas_y_calcula_estado(self):
        datos = self.datos()
        datos["estado"] = EstadoCuestionario.BORRADOR
        cuestionario = crear_cuestionario(
            datos=datos,
            preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
            docente=self.usuario,
        )
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.post(
            reverse(
                "quizzes:cuestionario-publicar",
                args=[cuestionario.pk],
            )
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], EstadoCuestionario.PROGRAMADO)
        self.assertEqual(
            respuesta.data["puntaje_total_posible"],
            Decimal("1.00"),
        )

    def test_endpoints_agregan_reordenan_y_quitan_preguntas(self):
        cuestionario = crear_cuestionario(
            datos=self.datos(),
            preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
            docente=self.usuario,
        )
        self.client.force_authenticate(self.usuario)
        base = reverse("quizzes:cuestionario-preguntas", args=[cuestionario.pk])
        agregada = self.client.post(
            base,
            {"pregunta": self.pregunta_dos.pk, "puntaje": "2.00"},
            format="json",
        )
        self.assertEqual(agregada.status_code, 201, agregada.data)
        self.assertEqual(agregada.data["orden"], 2)
        actualizada = self.client.put(
            base,
            [
                {
                    "pregunta": self.pregunta.pk,
                    "orden": 2,
                    "puntaje": "1.00",
                },
                {
                    "pregunta": self.pregunta_dos.pk,
                    "orden": 1,
                    "puntaje": "3.00",
                },
            ],
            format="json",
        )
        self.assertEqual(actualizada.status_code, 200, actualizada.data)
        self.assertEqual(actualizada.data[0]["pregunta"], self.pregunta_dos.pk)
        cuestionario.refresh_from_db()
        self.assertEqual(cuestionario.puntaje_total_posible, Decimal("4.00"))
        quitada = self.client.delete(
            reverse(
                "quizzes:cuestionario-pregunta-detalle",
                args=[cuestionario.pk, self.pregunta_dos.pk],
            )
        )
        self.assertEqual(quitada.status_code, 204)

    def test_disponibles_incluye_intentos_usados_y_restantes_del_estudiante(self):
        rol = Rol.objects.get(nombre="Estudiante")
        estudiante = Usuario.objects.create_user(
            "EST-QUIZ-1",
            "Password-segura-123",
            nombre="Estudiante de prueba",
            correo="estudiante-quiz@test.local",
            rol=rol,
        )
        datos = self.datos()
        datos.update(
            {
                "fecha_apertura": timezone.now() - timedelta(hours=1),
                "fecha_cierre": timezone.now() + timedelta(hours=1),
                "estado": EstadoCuestionario.DISPONIBLE,
                "intentos_permitidos": 3,
            }
        )
        cuestionario = crear_cuestionario(
            datos=datos,
            preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
            docente=self.usuario,
        )
        Intento.objects.create(
            cuestionario=cuestionario,
            usuario=estudiante,
            numero_intento=1,
        )
        self.client.force_authenticate(estudiante)
        respuesta = self.client.get(reverse("quizzes:disponibles"))
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(len(respuesta.data), 1)
        self.assertEqual(respuesta.data[0]["intentos_usados"], 1)
        self.assertEqual(respuesta.data[0]["intentos_restantes"], 2)

    def test_un_cuestionario_con_intentos_solo_puede_cerrarse(self):
        cuestionario = crear_cuestionario(
            datos=self.datos(),
            preguntas=[{"pregunta": self.pregunta, "puntaje": Decimal("1.00")}],
            docente=self.usuario,
        )
        Intento.objects.create(cuestionario=cuestionario, usuario=self.usuario)
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.patch(
            reverse("quizzes:cuestionario-detalle", args=[cuestionario.pk]),
            {"descripcion": "Cambio no permitido"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("solo puede cerrarse", str(respuesta.data))
        cierre = self.client.patch(
            reverse("quizzes:cuestionario-detalle", args=[cuestionario.pk]),
            {"estado": EstadoCuestionario.CERRADO},
            format="json",
        )
        self.assertEqual(cierre.status_code, 200, cierre.data)
        self.assertEqual(cierre.data["estado"], EstadoCuestionario.CERRADO)
