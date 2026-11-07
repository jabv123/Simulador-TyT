from decimal import Decimal
from io import BytesIO

from django.urls import reverse
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from apps.accounts.models import Permiso, Rol, RolPermiso, Usuario
from apps.accounts.models import CursoAcademico, Grupo
from apps.attempts.models import EstadoIntento, Intento, RespuestaIntento
from apps.questions.models import Categoria, OpcionRespuesta, Pregunta
from apps.quizzes.models import Cuestionario, CuestionarioPregunta


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
        self.curso_academico = CursoAcademico.objects.create(nombre="Ingeniería")
        self.grupo = Grupo.objects.create(
            curso=self.curso_academico,
            nombre="6A",
        )
        self.estudiante.grupo = self.grupo
        self.estudiante.save(update_fields=["grupo"])

        self.eje = Categoria.objects.create(nombre="Lectura crítica")
        self.pregunta_1 = Pregunta.objects.create(
            categoria=self.eje,
            enunciado="Pregunta uno",
        )
        self.pregunta_2 = Pregunta.objects.create(
            categoria=self.eje,
            enunciado="Pregunta dos",
        )
        for pregunta in (self.pregunta_1, self.pregunta_2):
            CuestionarioPregunta.objects.create(
                cuestionario=self.cuestionario,
                pregunta=pregunta,
                orden=pregunta.pk,
                puntaje=Decimal("1.00"),
            )
        self.opcion_correcta_1 = OpcionRespuesta.objects.create(
            pregunta=self.pregunta_1,
            texto_opcion="Correcta 1",
            es_correcta=True,
        )
        self.opcion_incorrecta_1 = OpcionRespuesta.objects.create(
            pregunta=self.pregunta_1,
            texto_opcion="Incorrecta 1",
        )
        self.opcion_correcta_2 = OpcionRespuesta.objects.create(
            pregunta=self.pregunta_2,
            texto_opcion="Correcta 2",
            es_correcta=True,
        )
        self.opcion_incorrecta_2 = OpcionRespuesta.objects.create(
            pregunta=self.pregunta_2,
            texto_opcion="Incorrecta 2",
        )

        self.intento_1 = Intento.objects.create(
            cuestionario=self.cuestionario,
            usuario=self.estudiante,
            grupo_snapshot=self.grupo,
            curso_nombre_snapshot=self.curso_academico.nombre,
            grupo_nombre_snapshot=self.grupo.nombre,
            numero_intento=1,
            fecha_fin="2026-01-10T09:00:00Z",
            calificacion_final=Decimal("4.00"),
            estado=EstadoIntento.FINALIZADO,
        )
        self.intento_2 = Intento.objects.create(
            cuestionario=self.cuestionario,
            usuario=self.estudiante,
            grupo_snapshot=self.grupo,
            curso_nombre_snapshot=self.curso_academico.nombre,
            grupo_nombre_snapshot=self.grupo.nombre,
            numero_intento=2,
            fecha_fin="2026-02-10T09:00:00Z",
            calificacion_final=Decimal("2.00"),
            estado=EstadoIntento.FINALIZADO,
        )
        RespuestaIntento.objects.create(
            intento=self.intento_1,
            pregunta=self.pregunta_1,
            opcion_seleccionada=self.opcion_correcta_1,
            es_correcta=True,
            puntaje_obtenido=Decimal("1.00"),
        )
        RespuestaIntento.objects.create(
            intento=self.intento_1,
            pregunta=self.pregunta_2,
            opcion_seleccionada=self.opcion_incorrecta_2,
        )
        RespuestaIntento.objects.create(
            intento=self.intento_2,
            pregunta=self.pregunta_1,
            opcion_seleccionada=self.opcion_incorrecta_1,
        )
        RespuestaIntento.objects.create(
            intento=self.intento_2,
            pregunta=self.pregunta_2,
            opcion_seleccionada=self.opcion_incorrecta_2,
        )

    def test_api_reporte_requiere_permiso_reportes(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("reports:api"))
        self.assertEqual(response.status_code, 401)
        exportacion = self.client.get(reverse("reports:exportar"))
        self.assertEqual(exportacion.status_code, 401)

        estudiante = Usuario.objects.get(codigo="EST-REPORT-1")
        self.client.force_authenticate(estudiante)
        response = self.client.get(reverse("reports:api"))
        self.assertEqual(response.status_code, 403)
        exportacion = self.client.get(reverse("reports:exportar"))
        self.assertEqual(exportacion.status_code, 403)

    def test_api_reporte_devuelve_kpis_y_resultados(self):
        response = self.client.get(reverse("reports:api"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("indicadores", response.data)
        self.assertEqual(response.data["indicadores"]["estudiantes_distintos"], 1)
        self.assertEqual(response.data["indicadores"]["aprobados"], 1)
        self.assertEqual(response.data["indicadores"]["no_aprobados"], 1)
        self.assertLessEqual(
            response.data["indicadores"]["porcentaje_aprobacion"],
            Decimal("100"),
        )

    def test_porcentaje_aprobacion_se_muestra_sin_decimales(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("reports:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>50%</strong>", html=True)
        self.assertNotContains(response, "50,00%")

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

    def test_comparacion_por_anio_y_periodo(self):
        evaluacion_segundo_semestre = Cuestionario.objects.create(
            docente=self.admin,
            nombre="Prueba de segundo semestre",
            descripcion="Comparación de período",
            fecha_apertura="2026-08-01T08:00:00Z",
            fecha_cierre="2026-12-01T20:00:00Z",
            tiempo_limite_minutos=60,
            intentos_permitidos=2,
            calificacion_maxima=Decimal("5.00"),
            calificacion_aprobacion=Decimal("3.00"),
            estado="DISPONIBLE",
        )
        Intento.objects.create(
            cuestionario=evaluacion_segundo_semestre,
            usuario=self.estudiante,
            grupo_snapshot=self.grupo,
            curso_nombre_snapshot=self.curso_academico.nombre,
            grupo_nombre_snapshot=self.grupo.nombre,
            numero_intento=1,
            fecha_fin="2026-08-10T09:00:00Z",
            calificacion_final=Decimal("4.00"),
            estado=EstadoIntento.FINALIZADO,
        )
        response = self.client.get(reverse("reports:api"), {"tipo": "periodo"})

        self.assertEqual(response.status_code, 200, response.data)
        periodos = {item["periodo"]: item for item in response.data["resumen"]}
        primer_semestre = periodos[1]
        segundo_semestre = periodos[2]
        self.assertEqual(primer_semestre["anio"], 2026)
        self.assertEqual(primer_semestre["evaluaciones"], 1)
        self.assertEqual(primer_semestre["intentos"], 2)
        self.assertEqual(primer_semestre["promedio"], Decimal("3"))
        self.assertEqual(segundo_semestre["evaluaciones"], 1)
        self.assertEqual(segundo_semestre["intentos"], 1)
        self.assertEqual(segundo_semestre["promedio"], Decimal("4"))

    def test_resultados_por_curso_y_grupo_incluyen_rango_de_notas(self):
        response = self.client.get(
            reverse("reports:api"),
            {"tipo": "curso_grupo"},
        )

        self.assertEqual(response.status_code, 200, response.data)
        grupo = response.data["resumen"][0]
        self.assertEqual(grupo["curso"], "Ingeniería")
        self.assertEqual(grupo["grupo"], "6A")
        self.assertEqual(grupo["estudiantes"], 1)
        self.assertEqual(grupo["intentos"], 2)
        self.assertEqual(grupo["promedio"], Decimal("3"))
        self.assertEqual(grupo["nota_minima"], Decimal("2"))
        self.assertEqual(grupo["nota_maxima"], Decimal("4"))

    def test_desempeno_por_eje_incluye_aciertos_y_nota_ponderada(self):
        response = self.client.get(reverse("reports:api"), {"tipo": "eje"})

        self.assertEqual(response.status_code, 200, response.data)
        eje = response.data["resumen"][0]
        self.assertEqual(eje["preguntas"], 2)
        self.assertEqual(eje["preguntas_respondidas"], 4)
        self.assertEqual(eje["respuestas_correctas"], 1)
        self.assertEqual(eje["porcentaje_aciertos"], Decimal("25"))
        self.assertEqual(eje["nota"], Decimal("1.25"))

    def test_filtro_por_eje_limita_tabla_y_metricas_al_eje_seleccionado(self):
        otro_eje = Categoria.objects.create(nombre="Razonamiento cuantitativo")
        pregunta = Pregunta.objects.create(
            categoria=otro_eje,
            enunciado="Pregunta de otro eje",
        )
        CuestionarioPregunta.objects.create(
            cuestionario=self.cuestionario,
            pregunta=pregunta,
            orden=3,
            puntaje=Decimal("1.00"),
        )
        opcion_correcta = OpcionRespuesta.objects.create(
            pregunta=pregunta,
            texto_opcion="Correcta",
            es_correcta=True,
        )
        RespuestaIntento.objects.create(
            intento=self.intento_1,
            pregunta=pregunta,
            opcion_seleccionada=opcion_correcta,
            es_correcta=True,
            puntaje_obtenido=Decimal("1.00"),
        )

        response = self.client.get(
            reverse("reports:api"),
            {"tipo": "eje", "eje": self.eje.pk},
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["paginacion"]["total"], 2)
        self.assertEqual(
            [item["id"] for item in response.data["resumen"]],
            [self.eje.pk],
        )
        self.assertEqual(
            response.data["resumen"][0]["preguntas_respondidas"],
            4,
        )

    def test_usuario_sin_permiso_de_gestion_no_recibe_identificacion(self):
        rol = Rol.objects.create(nombre="Analista de reportes")
        for accion in ("VER", "EXPORTAR"):
            permiso = Permiso.objects.get(modulo="REPORTES", accion=accion)
            RolPermiso.objects.create(rol=rol, permiso=permiso)
        analista = Usuario.objects.create_user(
            "ANALISTA-1",
            "P@ssword123!",
            nombre="Analista",
            correo="analista@test.local",
            rol=rol,
        )
        self.client.force_authenticate(analista)

        response = self.client.get(reverse("reports:api"))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["resultados"][0]["identificacion"], "")

        exportacion = self.client.get(reverse("reports:exportar"))
        self.assertEqual(exportacion.status_code, 200)
        libro = load_workbook(BytesIO(exportacion.content), read_only=True)
        hoja = libro["Reporte A - Consolidado"]
        self.assertNotIn("Identificación", [cell.value for cell in hoja[1]])
        estudiantes = self.client.get("/reportes/api/estudiantes/")
        self.assertEqual(estudiantes.status_code, 200)
        self.assertNotIn("codigo", estudiantes.data[0])

        self.client.force_login(analista)
        pantalla = self.client.get(reverse("reports:home"))
        self.assertNotContains(pantalla, "<th>Identificación</th>", html=False)
        self.assertNotContains(pantalla, f"({self.estudiante.codigo})")

    def test_pantalla_reportes_conecta_descargas_excel_autenticadas(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("reports:home"))

        self.assertEqual(response.status_code, 200)
        for reporte in ("all", "A", "B", "C"):
            self.assertContains(response, f'data-report-export="{reporte}"')
        self.assertContains(response, "js/reportes.js")

    def test_resultado_individual_usa_nota_sobre_cinco_y_curso_historico(self):
        response = self.client.get(
            reverse("reports:api"),
            {"estudiante": self.estudiante.pk},
        )

        self.assertEqual(response.status_code, 200, response.data)
        resultado = response.data["resultados"][0]
        self.assertEqual(resultado["curso"], "Ingeniería")
        self.assertEqual(resultado["grupo"], "6A")
        self.assertEqual(resultado["simulacro"], self.cuestionario.nombre)
        self.assertEqual(resultado["nota"], Decimal("2.00"))
        self.assertEqual(resultado["estado"], "No aprobado")
        self.assertEqual(len(response.data["historial"]), 2)
        self.assertEqual(response.data["historial"][0]["nota"], Decimal("4.00"))
        self.assertEqual(response.data["historial"][1]["cambio"], Decimal("-2.00"))

    def test_notas_de_cuestionarios_con_escalas_distintas_se_normalizan_a_cinco(self):
        cuestionario = Cuestionario.objects.create(
            docente=self.admin,
            nombre="Escala de diez",
            descripcion="Validación de escala",
            fecha_apertura="2026-03-01T08:00:00Z",
            fecha_cierre="2026-03-30T20:00:00Z",
            tiempo_limite_minutos=60,
            intentos_permitidos=2,
            calificacion_maxima=Decimal("10.00"),
            calificacion_aprobacion=Decimal("6.00"),
            estado="DISPONIBLE",
        )
        Intento.objects.create(
            cuestionario=cuestionario,
            usuario=self.estudiante,
            grupo_snapshot=self.grupo,
            curso_nombre_snapshot=self.curso_academico.nombre,
            grupo_nombre_snapshot=self.grupo.nombre,
            numero_intento=1,
            fecha_fin="2026-03-10T09:00:00Z",
            calificacion_final=Decimal("8.00"),
            estado=EstadoIntento.FINALIZADO,
        )

        response = self.client.get(
            reverse("reports:api"),
            {"curso": cuestionario.pk, "orden": "nota", "direccion": "desc"},
        )

        self.assertEqual(response.status_code, 200, response.data)
        resultado = response.data["resultados"][0]
        self.assertEqual(resultado["nota"], Decimal("4.00"))
        self.assertEqual(resultado["calificacion_maxima"], Decimal("10.00"))
        self.assertEqual(resultado["estado"], "Aprobado")

    def test_preguntas_dificiles_ordenan_por_aciertos_y_cuentan_errores(self):
        response = self.client.get(
            reverse("reports:api"),
            {"tipo": "dificultad"},
        )

        self.assertEqual(response.status_code, 200, response.data)
        pregunta = response.data["resumen"][0]
        self.assertEqual(pregunta["id"], self.pregunta_2.pk)
        self.assertEqual(pregunta["total_respuestas"], 2)
        self.assertEqual(pregunta["errores"], 2)
        self.assertEqual(pregunta["porcentaje_aciertos"], Decimal("0"))

    def test_filtros_de_curso_academico_y_grupo(self):
        response = self.client.get(
            reverse("reports:api"),
            {
                "curso_academico": self.curso_academico.pk,
                "grupo": self.grupo.pk,
            },
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["paginacion"]["total"], 2)
        self.assertEqual(
            self.client.get("/reportes/api/grupos/").status_code,
            200,
        )

    def test_api_administrativa_crea_curso_grupo_y_asigna_estudiante(self):
        curso_response = self.client.post(
            reverse("cursos-academicos"),
            {"nombre": "Administración"},
            format="json",
        )
        self.assertEqual(curso_response.status_code, 201, curso_response.data)
        grupo_response = self.client.post(
            reverse("grupos"),
            {"curso": curso_response.data["id"], "nombre": "6C"},
            format="json",
        )
        self.assertEqual(grupo_response.status_code, 201, grupo_response.data)
        asignacion = self.client.patch(
            reverse("accounts:usuario-detalle", args=[self.estudiante.pk]),
            {"grupo": grupo_response.data["id"]},
            format="json",
        )
        self.assertEqual(asignacion.status_code, 200, asignacion.data)
        self.assertEqual(asignacion.data["grupo_nombre"], "6C")
        self.assertEqual(asignacion.data["curso_academico_nombre"], "Administración")

    def test_pantalla_y_excel_exponen_historial_y_todos_los_reportes(self):
        self.client.force_login(self.admin)
        pantalla = self.client.get(
            reverse("reports:home"),
            {"estudiante": self.estudiante.pk, "tipo": "dificultad"},
        )
        self.assertEqual(pantalla.status_code, 200)
        self.assertContains(pantalla, "Historial individual")
        self.assertContains(pantalla, "Preguntas de mayor dificultad")
        self.assertNotContains(pantalla, "2,000000")
        self.assertNotContains(pantalla, "4,000000")
        for filtro in (
            "Año",
            "Período",
            "Curso académico",
            "Eje temático",
            "Estudiante",
        ):
            self.assertContains(pantalla, filtro)
        for reporte in ("A", "B", "C"):
            self.assertContains(
                pantalla,
                f"reporte={reporte}",
            )

        exportacion = self.client.get(
            reverse("reports:exportar"),
            {"estudiante": self.estudiante.pk},
        )
        self.assertEqual(exportacion.status_code, 200)
        self.assertIn("reporte_academico_", exportacion["Content-Disposition"])
        libro = load_workbook(BytesIO(exportacion.content), read_only=True)
        self.assertTrue(
            {
                "Año y período",
                "Cursos y grupos",
                "Desempeño por eje",
                "Preguntas difíciles",
                "Reporte A - Consolidado",
                "Reporte C - Historial",
            }.issubset(libro.sheetnames)
        )
        resumen = libro["Resumen ejecutivo"]
        resumen_metadata = {
            resumen.cell(row=row, column=1).value: resumen.cell(row=row, column=2).value
            for row in range(1, resumen.max_row + 1)
        }
        self.assertEqual(
            resumen_metadata["Filtro aplicado"],
            f"Estudiante: {self.estudiante.nombre}",
        )
        self.assertTrue(resumen_metadata["Fecha de generación"])

        consolidado = libro["Reporte A - Consolidado"]
        self.assertEqual(
            [cell.value for cell in consolidado[1]][:6],
            ["Año", "Período", "Curso", "Grupo", "Simulacro", "Estudiante"],
        )
        self.assertEqual(consolidado.max_row, 3)

        ejes = libro["Desempeño por eje"]
        self.assertEqual(
            [cell.value for cell in ejes[1]],
            [
                "Año",
                "Período",
                "Curso",
                "Eje",
                "Respuestas registradas",
                "Aciertos",
                "Errores",
                "Porcentaje de aciertos",
                "Nota promedio / 5,0",
            ],
        )
        self.assertEqual(
            [cell.value for cell in ejes[2]],
            [
                2026,
                "1° semestre",
                "Ingeniería",
                "Lectura crítica",
                4,
                1,
                3,
                25,
                1.25,
            ],
        )

        historial = libro["Reporte C - Historial"]
        self.assertEqual(
            [cell.value for cell in historial[1]],
            [
                "Año",
                "Estudiante",
                "Curso",
                "Período",
                "Simulacro",
                "Fecha",
                "Preguntas respondidas",
                "Aciertos",
                "Errores",
                "Nota final / 5,0",
            ],
        )
        self.assertEqual(historial.max_row, 3)
        self.assertEqual(historial.cell(row=2, column=7).value, 2)
        self.assertEqual(historial.cell(row=2, column=8).value, 1)
        self.assertEqual(historial.cell(row=2, column=9).value, 1)
        self.assertLess(historial.cell(row=2, column=6).value, historial.cell(row=3, column=6).value)

    def test_interfaz_muestra_paginacion_cuando_hay_mas_de_diez_resultados(self):
        for numero in range(3, 12):
            Intento.objects.create(
                cuestionario=self.cuestionario,
                usuario=self.estudiante,
                grupo_snapshot=self.grupo,
                curso_nombre_snapshot=self.curso_academico.nombre,
                grupo_nombre_snapshot=self.grupo.nombre,
                numero_intento=numero,
                fecha_fin=f"2026-03-{numero:02d}T09:00:00Z",
                calificacion_final=Decimal("4.00"),
                estado=EstadoIntento.FINALIZADO,
            )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Página 1 de 2")
        self.assertContains(response, "Siguiente")

    def test_descarga_tres_archivos_excel_independientes_con_filtros(self):
        hojas = {
            "A": "Reporte A - Consolidado",
            "B": "Desempeño por eje",
            "C": "Reporte C - Historial",
        }
        for reporte, hoja_esperada in hojas.items():
            with self.subTest(reporte=reporte):
                response = self.client.get(
                    reverse("reports:exportar"),
                    {
                        "estudiante": self.estudiante.pk,
                        "reporte": reporte,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"_{reporte.lower()}_", response["Content-Disposition"])
                libro = load_workbook(BytesIO(response.content), read_only=True)
                self.assertEqual(
                    libro.sheetnames,
                    ["Resumen ejecutivo", hoja_esperada],
                )
                metadata = {
                    libro["Resumen ejecutivo"].cell(row=row, column=1).value:
                    libro["Resumen ejecutivo"].cell(row=row, column=2).value
                    for row in range(
                        1,
                        libro["Resumen ejecutivo"].max_row + 1,
                    )
                }
                self.assertEqual(
                    metadata["Filtro aplicado"],
                    f"Estudiante: {self.estudiante.nombre}",
                )
                self.assertTrue(metadata["Fecha de generación"])

        invalid = self.client.get(
            reverse("reports:exportar"),
            {"reporte": "D"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_exportacion_no_aplica_paginacion_a_las_filas_descargadas(self):
        for numero in range(3, 13):
            Intento.objects.create(
                cuestionario=self.cuestionario,
                usuario=self.estudiante,
                grupo_snapshot=self.grupo,
                curso_nombre_snapshot=self.curso_academico.nombre,
                grupo_nombre_snapshot=self.grupo.nombre,
                numero_intento=numero,
                fecha_fin=f"2026-03-{numero:02d}T09:00:00Z",
                calificacion_final=Decimal("4.00"),
                estado=EstadoIntento.FINALIZADO,
            )

        api_response = self.client.get(reverse("reports:api"), {"page": 1})
        self.assertEqual(api_response.data["paginacion"]["total"], 12)
        self.assertEqual(len(api_response.data["resultados"]), 10)

        exportacion = self.client.get(reverse("reports:exportar"))
        libro = load_workbook(BytesIO(exportacion.content), read_only=True)
        self.assertEqual(libro["Reporte A - Consolidado"].max_row, 13)
        self.assertEqual(libro["Reporte C - Historial"].max_row, 13)
        fechas = [
            libro["Reporte C - Historial"].cell(row=row, column=6).value
            for row in range(2, 14)
        ]
        self.assertEqual(fechas, sorted(fechas))

    def test_flujo_academico_filtra_eje_historial_y_exporta_sin_mezclar_estudiantes(self):
        otro_eje = Categoria.objects.create(nombre="Razonamiento cuantitativo")
        pregunta_otro_eje = Pregunta.objects.create(
            categoria=otro_eje,
            enunciado="Pregunta cuantitativa",
        )
        CuestionarioPregunta.objects.create(
            cuestionario=self.cuestionario,
            pregunta=pregunta_otro_eje,
            orden=3,
            puntaje=Decimal("1.00"),
        )
        correcta_otro_eje = OpcionRespuesta.objects.create(
            pregunta=pregunta_otro_eje,
            texto_opcion="Correcta cuantitativa",
            es_correcta=True,
        )
        RespuestaIntento.objects.create(
            intento=self.intento_1,
            pregunta=pregunta_otro_eje,
            opcion_seleccionada=correcta_otro_eje,
            es_correcta=True,
            puntaje_obtenido=Decimal("1.00"),
        )

        otro_estudiante = Usuario.objects.create_user(
            "EST-REPORT-3",
            "P@ssword123!",
            nombre="Otra estudiante",
            correo="otra-estudiante@test.local",
            rol=Rol.objects.get(nombre="Estudiante"),
            grupo=self.grupo,
        )
        intento_otro_estudiante = Intento.objects.create(
            cuestionario=self.cuestionario,
            usuario=otro_estudiante,
            grupo_snapshot=self.grupo,
            curso_nombre_snapshot=self.curso_academico.nombre,
            grupo_nombre_snapshot=self.grupo.nombre,
            numero_intento=1,
            fecha_fin="2026-03-01T09:00:00Z",
            calificacion_final=Decimal("3.00"),
            estado=EstadoIntento.FINALIZADO,
        )
        RespuestaIntento.objects.create(
            intento=intento_otro_estudiante,
            pregunta=self.pregunta_1,
            opcion_seleccionada=self.opcion_correcta_1,
            es_correcta=True,
            puntaje_obtenido=Decimal("1.00"),
        )
        RespuestaIntento.objects.create(
            intento=intento_otro_estudiante,
            pregunta=pregunta_otro_eje,
            opcion_seleccionada=correcta_otro_eje,
            es_correcta=False,
        )

        filtros = {
            "curso_academico": self.curso_academico.pk,
            "eje": self.eje.pk,
            "tipo": "eje",
        }
        consulta = self.client.get(reverse("reports:api"), filtros)
        self.assertEqual(consulta.status_code, 200, consulta.data)
        self.assertEqual(consulta.data["paginacion"]["total"], 3)
        self.assertEqual(consulta.data["indicadores"]["estudiantes_distintos"], 2)
        self.assertEqual(len(consulta.data["resumen"]), 1)
        metricas_eje = consulta.data["resumen"][0]
        self.assertEqual(metricas_eje["id"], self.eje.pk)
        self.assertEqual(metricas_eje["preguntas_respondidas"], 5)
        self.assertEqual(metricas_eje["respuestas_correctas"], 2)

        historial_individual = self.client.get(
            reverse("reports:api"),
            {**filtros, "estudiante": otro_estudiante.pk},
        )
        self.assertEqual(historial_individual.status_code, 200)
        self.assertEqual(len(historial_individual.data["historial"]), 1)
        self.assertEqual(
            historial_individual.data["historial"][0]["estudiante"],
            otro_estudiante.nombre,
        )

        exportacion = self.client.get(reverse("reports:exportar"), filtros)
        self.assertEqual(exportacion.status_code, 200)
        libro = load_workbook(BytesIO(exportacion.content), read_only=True)
        consolidado = libro["Reporte A - Consolidado"]
        self.assertEqual(consolidado.max_row, len(consulta.data["resultados"]) + 1)
        excel_filas = list(consolidado.iter_rows(min_row=2, values_only=True))
        excel_estudiantes = {fila[5] for fila in excel_filas}
        api_estudiantes = {item["usuario"] for item in consulta.data["resultados"]}
        self.assertEqual(excel_estudiantes, api_estudiantes)
        for fila, resultado in zip(excel_filas, consulta.data["resultados"]):
            self.assertEqual(fila[2], resultado["curso"])
            self.assertEqual(fila[4], resultado["simulacro"])
            self.assertEqual(fila[5], resultado["usuario"])
            self.assertEqual(fila[8], float(resultado["nota"]))
            self.assertEqual(fila[11], resultado["estado"])
        self.assertEqual(libro["Desempeño por eje"].max_row, 2)
        self.assertEqual(libro["Reporte C - Historial"].max_row, 4)
