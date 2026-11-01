"""Pruebas de presentación, conservación y calificación de intentos."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APITestCase

from apps.accounts.models import Rol, Usuario
from apps.questions.models import Categoria, OpcionRespuesta, Pregunta
from apps.quizzes.models import (
    Cuestionario,
    CuestionarioPregunta,
    EstadoCuestionario,
)

from .models import EstadoIntento, Intento
from .services import finalizar_intento, guardar_respuesta, iniciar_intento


class IntentosServicioTests(APITestCase):
    def setUp(self):
        rol, _ = Rol.objects.get_or_create(nombre="Estudiante")
        self.usuario = Usuario.objects.create_user(
            "EST-1",
            "Student-password-123",
            nombre="Estudiante de prueba",
            correo="estudiante@test.local",
            rol=rol,
        )
        self.admin_rol, _ = Rol.objects.get_or_create(nombre="Administrador")
        self.docente = Usuario.objects.create_user(
            "DOC-1",
            "Teacher-password-123",
            nombre="Docente",
            correo="docente@test.local",
            rol=self.admin_rol,
        )
        categoria = Categoria.objects.create(nombre="Matemáticas")
        self.pregunta_1 = self.crear_pregunta(categoria, "¿Cuánto es 2 + 2?")
        self.pregunta_2 = self.crear_pregunta(categoria, "¿Cuánto es 3 + 3?")
        ahora = timezone.now()
        self.cuestionario = Cuestionario.objects.create(
            docente=self.docente,
            nombre="Prueba de cálculo",
            fecha_apertura=ahora - timedelta(minutes=1),
            fecha_cierre=ahora + timedelta(hours=1),
            tiempo_limite_minutos=30,
            intentos_permitidos=2,
            calificacion_maxima=Decimal("5.00"),
            calificacion_aprobacion=Decimal("3.00"),
            estado=EstadoCuestionario.DISPONIBLE,
            permitir_revision=True,
        )
        CuestionarioPregunta.objects.create(
            cuestionario=self.cuestionario,
            pregunta=self.pregunta_1,
            orden=1,
            puntaje=Decimal("2.00"),
        )
        CuestionarioPregunta.objects.create(
            cuestionario=self.cuestionario,
            pregunta=self.pregunta_2,
            orden=2,
            puntaje=Decimal("2.00"),
        )

    def crear_pregunta(self, categoria, enunciado):
        pregunta = Pregunta.objects.create(
            categoria=categoria,
            enunciado=enunciado,
            creado_por=self.docente,
        )
        OpcionRespuesta.objects.create(
            pregunta=pregunta,
            texto_opcion="Respuesta correcta",
            es_correcta=True,
        )
        OpcionRespuesta.objects.create(
            pregunta=pregunta,
            texto_opcion="Respuesta incorrecta",
            es_correcta=False,
        )
        return pregunta

    def test_iniciar_conserva_preguntas_sin_respuesta_y_califica(self):
        intento = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        self.assertEqual(intento.respuestas.count(), 2)
        respuesta = guardar_respuesta(
            intento_id=intento.pk,
            usuario=self.usuario,
            pregunta_id=self.pregunta_1.pk,
            opcion_id=self.pregunta_1.opciones.get(es_correcta=True).pk,
        )
        self.assertTrue(respuesta.es_correcta)
        resultado = finalizar_intento(intento)
        self.assertEqual(resultado.estado, EstadoIntento.FINALIZADO)
        self.assertEqual(resultado.puntaje_obtenido, Decimal("2.00"))
        self.assertEqual(resultado.calificacion_final, Decimal("2.50"))
        self.assertIsNone(
            resultado.respuestas.get(pregunta=self.pregunta_2).opcion_seleccionada
        )

    def test_no_inicia_antes_de_la_apertura(self):
        self.cuestionario.fecha_apertura = timezone.now() + timedelta(hours=2)
        self.cuestionario.fecha_cierre = timezone.now() + timedelta(days=1)
        self.cuestionario.save()
        with self.assertRaises(ValidationError):
            iniciar_intento(
                cuestionario=self.cuestionario,
                usuario=self.usuario,
            )
        self.assertEqual(Intento.objects.count(), 0)

    def test_api_de_presentacion_no_expone_la_respuesta_correcta(self):
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.post(
            f"/api/cuestionarios/{self.cuestionario.pk}/iniciar/",
            {},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        for pregunta in respuesta.data["preguntas"]:
            self.assertNotIn("es_correcta", pregunta)
            for opcion in pregunta["opciones"]:
                self.assertNotIn("es_correcta", opcion)

    def test_tiempo_agotado_finaliza_automaticamente(self):
        intento = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        Intento.objects.filter(pk=intento.pk).update(
            fecha_inicio=timezone.now() - timedelta(minutes=31)
        )
        respuesta = guardar_respuesta(
            intento_id=intento.pk,
            usuario=self.usuario,
            pregunta_id=self.pregunta_1.pk,
        )
        intento.refresh_from_db()
        self.assertIsNone(respuesta)
        self.assertEqual(intento.estado, EstadoIntento.TIEMPO_AGOTADO)

    def test_nota_del_ejemplo_veinte_preguntas_es_cuatro_sobre_cinco(self):
        preguntas = [self.pregunta_1, self.pregunta_2]
        for numero in range(3, 21):
            preguntas.append(
                self.crear_pregunta(
                    self.pregunta_1.categoria,
                    f"Pregunta de ejemplo {numero}",
                )
            )
        CuestionarioPregunta.objects.filter(
            cuestionario=self.cuestionario
        ).delete()
        CuestionarioPregunta.objects.bulk_create(
            [
                CuestionarioPregunta(
                    cuestionario=self.cuestionario,
                    pregunta=pregunta,
                    orden=orden,
                    puntaje=Decimal("1.00"),
                )
                for orden, pregunta in enumerate(preguntas, start=1)
            ]
        )
        intento = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        for pregunta in preguntas[:16]:
            guardar_respuesta(
                intento_id=intento.pk,
                usuario=self.usuario,
                pregunta_id=pregunta.pk,
                opcion_id=pregunta.opciones.get(es_correcta=True).pk,
            )
        resultado = finalizar_intento(intento)
        self.assertEqual(resultado.puntaje_obtenido, Decimal("16.00"))
        self.assertEqual(resultado.calificacion_final, Decimal("4.00"))

    def test_iniciar_reanuda_el_intento_en_curso(self):
        intento = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        reanudado = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        self.assertEqual(reanudado.pk, intento.pk)
        self.assertEqual(Intento.objects.count(), 1)

    def test_cierre_del_cuestionario_finaliza_automaticamente_al_consultar(self):
        intento = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        self.cuestionario.fecha_cierre = timezone.now() - timedelta(seconds=1)
        self.cuestionario.save(update_fields=["fecha_cierre"])
        from .services import finalizar_si_vencido

        intento = finalizar_si_vencido(intento)
        self.assertEqual(intento.estado, EstadoIntento.TIEMPO_AGOTADO)
        self.assertEqual(intento.respuestas.count(), 2)
        self.assertEqual(intento.calificacion_final, Decimal("0.00"))

    def test_revision_respuestas_correctas_desactivada_no_devuelve_clave(self):
        self.cuestionario.permitir_revision = False
        self.cuestionario.save(update_fields=["permitir_revision"])
        intento = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        resultado = finalizar_intento(intento)
        from .serializers import IntentoFinalizadoSerializer

        data = IntentoFinalizadoSerializer(resultado).data
        self.assertFalse(data["revision_disponible"])
        self.assertEqual(data["preguntas"], [])
        self.assertIn("calificacion_final", data)
        self.assertIn("aprobado", data)

    def test_marcar_para_revision_no_borra_la_opcion_seleccionada(self):
        intento = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        opcion = self.pregunta_1.opciones.get(es_correcta=True)
        guardar_respuesta(
            intento_id=intento.pk,
            usuario=self.usuario,
            pregunta_id=self.pregunta_1.pk,
            opcion_id=opcion.pk,
        )
        guardar_respuesta(
            intento_id=intento.pk,
            usuario=self.usuario,
            pregunta_id=self.pregunta_1.pk,
            marcada_para_revision=True,
            actualizar_opcion=False,
        )
        respuesta = intento.respuestas.get(pregunta=self.pregunta_1)
        self.assertEqual(respuesta.opcion_seleccionada_id, opcion.pk)
        self.assertTrue(respuesta.marcada_para_revision)

    def test_api_put_respuesta_y_finalizar_devuelven_nota_y_aprobacion(self):
        self.client.force_authenticate(self.usuario)
        inicio = self.client.post(
            f"/api/cuestionarios/{self.cuestionario.pk}/intentos/iniciar/",
            {},
            format="json",
        )
        self.assertEqual(inicio.status_code, 201, inicio.data)
        intento_id = inicio.data["id"]
        opcion = self.pregunta_1.opciones.get(es_correcta=True)
        guardada = self.client.put(
            f"/api/intentos/{intento_id}/respuestas/",
            {
                "pregunta_id": self.pregunta_1.pk,
                "opcion_seleccionada_id": opcion.pk,
            },
            format="json",
        )
        self.assertEqual(guardada.status_code, 200, guardada.data)
        final = self.client.post(
            f"/api/intentos/{intento_id}/finalizar/",
            {},
            format="json",
        )
        self.assertEqual(final.status_code, 200, final.data)
        self.assertEqual(final.data["calificacion_final"], "2.50")
        self.assertFalse(final.data["aprobado"])
        self.assertTrue(final.data["revision_disponible"])

    def test_estudiante_no_consulta_intento_ajeno_y_solo_ve_sus_resultados(self):
        otro = Usuario.objects.create_user(
            "EST-2",
            "Student-password-456",
            nombre="Otro estudiante",
            correo="estudiante2@test.local",
            rol=self.usuario.rol,
        )
        ajeno = Intento.objects.create(
            cuestionario=self.cuestionario,
            usuario=otro,
            numero_intento=1,
        )
        propio = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        self.client.force_authenticate(self.usuario)
        detalle = self.client.get(f"/api/intentos/{ajeno.pk}/")
        self.assertEqual(detalle.status_code, 404)
        resultados = self.client.get("/api/intentos/mis-resultados/")
        self.assertEqual(resultados.status_code, 200, resultados.data)
        self.assertEqual([item["id"] for item in resultados.data], [propio.pk])

    def test_resultados_admiten_filtros_por_cuestionario_y_usuario(self):
        intento = iniciar_intento(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
        )
        intento = finalizar_intento(intento)
        self.client.force_authenticate(self.docente)
        respuesta = self.client.get(
            "/api/resultados/",
            {
                "cuestionario_id": self.cuestionario.pk,
                "usuario_id": self.usuario.pk,
            },
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual([item["id"] for item in respuesta.data], [intento.pk])
        self.assertFalse(respuesta.data[0]["aprobado"])
        self.assertIsNotNone(respuesta.data[0]["duracion_segundos"])

    def test_iniciar_rechaza_a_un_usuario_que_no_es_estudiante(self):
        with self.assertRaises(PermissionDenied):
            iniciar_intento(
                cuestionario=self.cuestionario,
                usuario=self.docente,
            )
