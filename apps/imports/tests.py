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
        self.assertEqual(respuesta.data["importacion"]["registros_duplicados"], 2)
        self.assertEqual(respuesta.data["importacion"]["registros_con_errores"], 1)
        self.assertEqual(len(respuesta.data["errores"]), 1)
        self.assertEqual(respuesta.data["preguntas_agregadas_cuestionario"], 2)
        detalles = json.loads(respuesta.data["importacion"]["detalles_error"])
        self.assertEqual([item["fila"] for item in detalles["validas"]], [2])
        self.assertEqual(
            [item["fila"] for item in detalles["duplicadas"]],
            [3, 4],
        )

    def test_exporta_el_historial_excel_con_el_filtro_seleccionado(self):
        archivo = self.crear_libro(
            [
                self.fila("Nueva", "Pregunta válida"),
                self.fila("Nueva", "Pregunta válida"),
                self.fila("Nueva", "Pregunta errónea", respuesta_correcta="D"),
            ]
        )
        confirmacion = self.client.post(
            "/api/importaciones/confirmar/",
            self.datos_post(archivo),
            format="multipart",
        )
        self.assertEqual(confirmacion.status_code, 201, confirmacion.data)
        importacion = Importacion.objects.get()
        detalles = json.loads(importacion.detalles_error)
        detalles["validas"][0]["pregunta"] = "=1+1"
        importacion.detalles_error = json.dumps(detalles)
        importacion.save(update_fields=["detalles_error"])

        for tipo, esperado in (
            ("validas", "Válida"),
            ("duplicadas", "Duplicada"),
            ("errores", "Con errores"),
        ):
            with self.subTest(tipo=tipo):
                respuesta = self.client.get(
                    f"/api/importaciones/historial/exportar/?tipo={tipo}"
                )
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    respuesta["Content-Type"],
                )
                libro = load_workbook(BytesIO(respuesta.content), data_only=True)
                filas = list(libro.active.iter_rows(values_only=True))
                self.assertEqual(filas[1][4], esperado)
                if tipo == "validas":
                    self.assertEqual(libro.active["H2"].data_type, "s")
                    self.assertEqual(filas[1][7], "=1+1")

        respuesta_invalida = self.client.get(
            "/api/importaciones/historial/exportar/?tipo=desconocidas"
        )
        self.assertEqual(respuesta_invalida.status_code, 400)
        self.client.force_authenticate(None)
        respuesta_sin_sesion = self.client.get(
            "/api/importaciones/historial/exportar/?tipo=errores"
        )
        self.assertEqual(respuesta_sin_sesion.status_code, 401)

    def test_reimportar_filas_existentes_no_se_reporta_como_fallido(self):
        archivo = self.crear_libro([self.fila("Nueva", "Pregunta idempotente")])
        primera = self.client.post(
            "/api/importaciones/confirmar/",
            self.datos_post(archivo),
            format="multipart",
        )
        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(primera.data["importacion"]["registros_exitosos"], 1)
        self.assertEqual(primera.data["preguntas_agregadas_cuestionario"], 1)

        segunda = self.client.post(
            "/api/importaciones/confirmar/",
            self.datos_post(
                self.crear_libro([self.fila("Nueva", "Pregunta idempotente")])
            ),
            format="multipart",
        )

        self.assertEqual(segunda.status_code, 201, segunda.data)
        importacion = segunda.data["importacion"]
        self.assertEqual(importacion["registros_exitosos"], 0)
        self.assertEqual(importacion["registros_duplicados"], 1)
        self.assertEqual(importacion["registros_con_errores"], 0)
        self.assertEqual(importacion["estado_resultado"], "Sin cambios")
        self.assertEqual(segunda.data["preguntas_agregadas_cuestionario"], 0)
        self.assertEqual(Pregunta.objects.count(), 1)
        historial = self.client.get("/api/importaciones/historial/")
        self.assertEqual(historial.status_code, 200)
        self.assertEqual(historial.data[0]["registros_duplicados"], 1)
        self.assertEqual(historial.data[0]["registros_con_errores"], 0)

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
        respuesta_exportacion = self.client.get(
            "/api/importaciones/historial/exportar/?tipo=validas"
        )
        self.assertEqual(respuesta_exportacion.status_code, 403)
        self.assertEqual(Pregunta.objects.count(), 0)
