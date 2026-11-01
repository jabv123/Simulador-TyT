"""Pruebas de carga Excel y detalle de errores por fila."""

import json
from datetime import timedelta
from io import BytesIO

from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from rest_framework.test import APITestCase

from apps.accounts.models import Rol, Usuario
from apps.imports.models import Importacion
from apps.imports.services import importar_preguntas_excel
from apps.questions.models import Categoria, OpcionRespuesta, Pregunta
from apps.quizzes.models import Cuestionario, CuestionarioPregunta


class ImportacionExcelTests(TestCase):
    def setUp(self):
        rol, _ = Rol.objects.get_or_create(nombre="Administrador")
        self.usuario = Usuario.objects.create_user(
            "ADMIN-1",
            "Admin-password-123",
            nombre="Administradora",
            correo="admin@test.local",
            rol=rol,
        )

    def crear_archivo(self):
        libro = Workbook()
        hoja = libro.active
        hoja.append(
            [
                "categoria",
                "tipo",
                "enunciado",
                "opcion_1",
                "opcion_2",
                "respuesta_correcta",
                "puntaje",
            ]
        )
        hoja.append(
            [
                "Razonamiento",
                "MULTIPLE",
                "¿Cuánto es 2 + 2?",
                "4",
                "5",
                "1",
                1,
            ]
        )
        hoja.append(
            [
                "Razonamiento",
                "VERDADERO_FALSO",
                "El cielo es verde.",
                "Verdadero",
                "Falso",
                "3",
                1,
            ]
        )
        contenido = BytesIO()
        libro.save(contenido)
        contenido.seek(0)
        contenido.name = "preguntas.xlsx"
        contenido.size = contenido.getbuffer().nbytes
        return contenido

    def test_importa_validas_y_reporta_numero_de_fila_invalida(self):
        importacion = importar_preguntas_excel(
            archivo=self.crear_archivo(),
            usuario=self.usuario,
        )
        self.assertEqual(importacion.total_registros, 2)
        self.assertEqual(importacion.registros_exitosos, 1)
        self.assertEqual(importacion.registros_fallidos, 1)
        self.assertEqual(Pregunta.objects.count(), 1)
        errores = json.loads(importacion.detalles_error)
        self.assertEqual(errores[0]["fila"], 3)


class ImportacionExcelApiTests(APITestCase):
    encabezados = [
        "categoria",
        "tipo",
        "texto_base",
        "pregunta",
        "opcion_a",
        "opcion_b",
        "opcion_c",
        "opcion_d",
        "respuesta_correcta",
        "retroalimentacion",
        "puntaje",
    ]

    def setUp(self):
        rol, _ = Rol.objects.get_or_create(nombre="Administrador")
        self.usuario = Usuario.objects.create_user(
            "IMPORT-ADMIN",
            "Import-Admin-123!",
            nombre="Admin importación",
            correo="import-admin@test.local",
            rol=rol,
        )
        self.client.force_authenticate(self.usuario)
        ahora = timezone.now()
        self.cuestionario = Cuestionario.objects.create(
            docente=self.usuario,
            nombre="Cuestionario importación",
            fecha_apertura=ahora + timedelta(hours=1),
            fecha_cierre=ahora + timedelta(days=1),
            tiempo_limite_minutos=30,
            intentos_permitidos=1,
            calificacion_maxima=10,
            calificacion_aprobacion=6,
        )

    def crear_libro(self, filas, nombre="importacion.xlsx"):
        libro = Workbook()
        hoja = libro.active
        hoja.append(self.encabezados)
        for fila in filas:
            hoja.append(fila)
        contenido = BytesIO()
        libro.save(contenido)
        contenido.seek(0)
        contenido.name = nombre
        contenido.size = len(contenido.getvalue())
        return contenido

    def fila(self, categoria, enunciado, **cambios):
        fila = [
            categoria,
            "MULTIPLE",
            None,
            enunciado,
            "A",
            "B",
            None,
            None,
            "A",
            None,
            1,
        ]
        indices = {nombre: indice for indice, nombre in enumerate(self.encabezados)}
        for campo, valor in cambios.items():
            fila[indices[campo]] = valor
        return fila

    def datos_post(self, archivo):
        return {
            "archivo": archivo,
            "cuestionario_id": str(self.cuestionario.pk),
        }

    def test_descarga_plantilla_excel_con_ejemplo(self):
        respuesta = self.client.get("/api/importaciones/plantilla/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(
            "plantilla_preguntas_saber_tyt.xlsx",
            respuesta["Content-Disposition"],
        )
        libro = load_workbook(BytesIO(respuesta.content), data_only=True)
        filas = list(libro.active.iter_rows(values_only=True))
        self.assertEqual(tuple(filas[0]), tuple(self.encabezados))
        self.assertEqual(filas[1][0], "Razonamiento")
        self.assertEqual(filas[1][3], "¿Cuánto es 2 + 2?")

    def test_previsualizacion_no_guarda_y_clasifica_filas(self):
        categoria = Categoria.objects.create(nombre="Existente")
        existente = Pregunta.objects.create(
            categoria=categoria,
            enunciado="Pregunta que ya está en el banco",
            creado_por=self.usuario,
        )
        OpcionRespuesta.objects.create(
            pregunta=existente,
            texto_opcion="A",
            es_correcta=True,
        )
        OpcionRespuesta.objects.create(
            pregunta=existente,
            texto_opcion="B",
            es_correcta=False,
        )
        archivo = self.crear_libro(
            [
                self.fila("Nueva", "Pregunta nueva"),
                self.fila("Nueva", " Pregunta   NUEVA "),
                self.fila("Existente", "Pregunta que ya está en el banco"),
                self.fila(
                    "Nueva",
                    "Pregunta inválida",
                    respuesta_correcta=None,
                ),
            ]
        )
        respuesta = self.client.post(
            "/api/importaciones/previsualizar/",
            self.datos_post(archivo),
            format="multipart",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual([item["fila"] for item in respuesta.data["validas"]], [2])
        self.assertEqual(
            [item["fila"] for item in respuesta.data["duplicadas"]],
            [3, 4],
        )
        self.assertEqual([item["fila"] for item in respuesta.data["errores"]], [5])
        self.assertIn("Fila 5:", respuesta.data["errores"][0]["motivo"])
        self.assertEqual(Pregunta.objects.count(), 1)
        self.assertEqual(Categoria.objects.count(), 1)
        self.assertEqual(Importacion.objects.count(), 0)
        self.assertEqual(
            respuesta.data["validas"][0]["categoria"]["estado"],
            "se creará automáticamente",
        )

    def test_confirmacion_importa_validas_omite_invalidas_y_relaciona_duplicadas(self):
        categoria = Categoria.objects.create(nombre="Ya existe")
        existente = Pregunta.objects.create(
            categoria=categoria,
            enunciado="Pregunta duplicada del banco",
            creado_por=self.usuario,
        )
        OpcionRespuesta.objects.create(
            pregunta=existente,
            texto_opcion="A",
            es_correcta=True,
        )
        OpcionRespuesta.objects.create(
            pregunta=existente,
            texto_opcion="B",
            es_correcta=False,
        )
        archivo = self.crear_libro(
            [
                self.fila("Nueva", "Pregunta importada"),
                self.fila("Nueva", "Pregunta importada"),
                self.fila("Ya existe", "Pregunta duplicada del banco"),
                self.fila("Nueva", "Sin correcta", respuesta_correcta="D"),
            ]
        )
        respuesta = self.client.post(
            "/api/importaciones/confirmar/",
            self.datos_post(archivo),
            format="multipart",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(Pregunta.objects.count(), 2)
        self.assertTrue(
            Pregunta.objects.filter(enunciado="Pregunta importada").exists()
        )
        self.assertEqual(
            CuestionarioPregunta.objects.filter(
                cuestionario=self.cuestionario
            ).count(),
            2,
        )
        relaciones = list(
            CuestionarioPregunta.objects.filter(
                cuestionario=self.cuestionario
            ).order_by("orden")
        )
        self.assertEqual([item.orden for item in relaciones], [1, 2])
        importacion = Importacion.objects.get()
        self.assertEqual(importacion.total_registros, 4)
        self.assertEqual(importacion.registros_exitosos, 1)
        self.assertEqual(importacion.registros_fallidos, 3)
        self.assertEqual(importacion.estado_resultado, "Parcial")
        self.assertEqual(len(respuesta.data["errores"]), 1)

    def test_rechaza_extension_y_cuestionario_que_ya_tiene_intentos(self):
        archivo_invalido = self.crear_libro([], nombre="preguntas.csv")
        respuesta_extension = self.client.post(
            "/api/importaciones/previsualizar/",
            self.datos_post(archivo_invalido),
            format="multipart",
        )
        self.assertEqual(respuesta_extension.status_code, 400)

        from apps.attempts.models import Intento

        Intento.objects.create(
            cuestionario=self.cuestionario,
            usuario=self.usuario,
            numero_intento=1,
        )
        respuesta_intentos = self.client.post(
            "/api/importaciones/confirmar/",
            self.datos_post(self.crear_libro([self.fila("Nueva", "Pregunta")])),
            format="multipart",
        )
        self.assertEqual(respuesta_intentos.status_code, 403)

    def test_estudiante_no_puede_previsualizar_ni_confirmar(self):
        estudiante = Usuario.objects.create_user(
            "IMPORT-STUDENT",
            "Student-Import-123!",
            nombre="Estudiante importación",
            correo="import-student@test.local",
            rol=Rol.objects.get(nombre="Estudiante"),
        )
        self.client.force_authenticate(estudiante)
        respuesta = self.client.post(
            "/api/importaciones/previsualizar/",
            self.datos_post(self.crear_libro([self.fila("Nueva", "Pregunta")])),
            format="multipart",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Pregunta.objects.count(), 0)
