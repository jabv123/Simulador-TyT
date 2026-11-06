from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Rol, Usuario
from apps.attempts.models import EstadoIntento, Intento
from apps.quizzes.models import Cuestionario


class ReportesApiTests(APITestCase):
    def setUp(self):
        self.rol_admin, _ = Rol.objects.get_or_create(nombre="Administrador")
        self.admin = Usuario.objects.create_user(
            "REPORT-ADMIN",
            "P@ssword123!",
            nombre="Admin reportes",
            correo="reportes@test.local",
            rol=self.rol_admin,
        )
        self.client.force_authenticate(self.admin)

        self.cuestionario = Cuestionario.objects.create(
            docente=self.admin,
            nombre="Prueba de reportes",
            descripcion="Reporte",
            fecha_apertura="2026-01-01T08:00:00Z",
            fecha_cierre="2026-12-31T20:00:00Z",
            tiempo_limite_minutos=60,
            intentos_permitidos=5,
            calificacion_maxima=Decimal("5.00"),
            calificacion_aprobacion=Decimal("3.00"),
            mezclar_preguntas=False,
            mezclar_respuestas=False,
            permitir_revision=True,
            estado="DISPONIBLE",
        )

        self.estudiante = Usuario.objects.create_user(
            "EST-REPORT-1",
            "P@ssword123!",
            nombre="Estudiante reporte",
            correo="estudiante-report@test.local",
            rol=Rol.objects.get(nombre="Estudiante"),
        )

        Intento.objects.create(
            cuestionario=self.cuestionario,
            usuario=self.estudiante,
            numero_intento=1,
            fecha_fin="2026-01-10T09:00:00Z",
            calificacion_final=Decimal("4.00"),
            estado=EstadoIntento.FINALIZADO,
        )
        Intento.objects.create(
            cuestionario=self.cuestionario,
            usuario=self.estudiante,
            numero_intento=2,
            fecha_fin="2026-02-10T09:00:00Z",
            calificacion_final=Decimal("2.00"),
            estado=EstadoIntento.FINALIZADO,
        )

    def test_api_reporte_requiere_permiso_reportes(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("reports:api"))
        self.assertEqual(response.status_code, 401)

        estudiante = Usuario.objects.get(codigo="EST-REPORT-1")
        self.client.force_authenticate(estudiante)
        response = self.client.get(reverse("reports:api"))
        self.assertEqual(response.status_code, 403)

    def test_api_reporte_devuelve_kpis_y_resultados(self):
        response = self.client.get(reverse("reports:api"))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("indicadores", response.data)
        self.assertEqual(response.data["indicadores"]["estudiantes_distintos"], 1)
        self.assertEqual(response.data["indicadores"]["aprobados"], 1)
        self.assertEqual(response.data["indicadores"]["no_aprobados"], 1)

    def test_filtros_jerarquicos_respetan_herencia(self):
        periodos = self.client.get("/reportes/api/periodos/?anio=2026")
        self.assertEqual(periodos.status_code, 200)
        self.assertTrue(any(item["value"] == "1" for item in periodos.json()))

        cursos = self.client.get("/reportes/api/cursos/?anio=2026&periodo=1")
        self.assertEqual(cursos.status_code, 200)
        self.assertEqual(len(cursos.json()), 1)
        self.assertEqual(cursos.json()[0]["id"], self.cuestionario.pk)

        estudiantes = self.client.get(f"/reportes/api/estudiantes/?curso={self.cuestionario.pk}")
        self.assertEqual(estudiantes.status_code, 200)
        self.assertEqual(estudiantes.json()[0]["id"], self.estudiante.pk)

    def test_api_reporte_soporta_paginacion_y_orden(self):
        otro_estudiante = Usuario.objects.create_user(
            "EST-REPORT-2",
            "P@ssword123!",
            nombre="Estudiante reporte dos",
            correo="estudiante-report-2@test.local",
            rol=Rol.objects.get(nombre="Estudiante"),
        )
        Intento.objects.create(
            cuestionario=self.cuestionario,
            usuario=otro_estudiante,
            numero_intento=1,
            fecha_fin="2026-01-11T09:00:00Z",
            calificacion_final=Decimal("1.00"),
            estado=EstadoIntento.FINALIZADO,
        )

        response = self.client.get(
            reverse("reports:api"),
            {"orden": "nota", "direccion": "asc", "page": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("paginacion", response.data)
        self.assertEqual(response.data["paginacion"]["total"], 3)
        notas = [float(item["nota"]) for item in response.data["resultados"]]
        self.assertEqual(notas, sorted(notas))

    def test_api_reporte_incluye_resumen_agrupado_por_tipo(self):
        response = self.client.get(reverse("reports:api"), {"tipo": "curso"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tipo"], "curso")
        self.assertIn("resumen", response.data)
        self.assertGreater(len(response.data["resumen"]), 0)
        self.assertEqual(response.data["resumen"][0]["id"], self.cuestionario.pk)
