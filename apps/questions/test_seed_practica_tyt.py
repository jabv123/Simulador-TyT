from collections import Counter
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.attempts.models import EstadoIntento, Intento, RespuestaIntento
from apps.questions.models import OpcionRespuesta, Pregunta, TipoPregunta
from apps.quizzes.models import Cuestionario, CuestionarioPregunta
from apps.reports.selectors import (
    get_cursos_disponibles,
    get_ejes_disponibles,
    get_periodos_disponibles,
)
from apps.reports.services import obtener_kpis


class CargaPracticaTytTests(TestCase):
    def test_crea_datos_validos_y_la_segunda_ejecucion_es_idempotente(self):
        salida = StringIO()
        call_command("seed_practica_tyt", stdout=salida)

        cuestionarios = Cuestionario.objects.filter(
            nombre__startswith="Práctica tecnológica TyT - Semestre"
        )
        self.assertEqual(cuestionarios.count(), 2)
        preguntas = Pregunta.objects.filter(
            cuestionarios__in=cuestionarios
        ).distinct()
        self.assertEqual(preguntas.count(), 20)
        self.assertEqual(
            preguntas.filter(tipo=TipoPregunta.MULTIPLE).count(),
            15,
        )
        self.assertEqual(
            preguntas.filter(tipo=TipoPregunta.VERDADERO_FALSO).count(),
            5,
        )
        self.assertEqual(
            dict(Counter(preguntas.values_list("categoria__nombre", flat=True))),
            {
                "Lectura crítica": 4,
                "Razonamiento cuantitativo": 4,
                "Competencias ciudadanas": 4,
                "Inglés": 4,
                "Comunicación escrita": 4,
            },
        )
        self.assertEqual(
            CuestionarioPregunta.objects.filter(
                cuestionario__in=cuestionarios
            ).count(),
            20,
        )
        self.assertEqual(
            Intento.objects.filter(
                cuestionario__in=cuestionarios,
                estado=EstadoIntento.FINALIZADO,
            ).count(),
            4,
        )
        self.assertEqual(
            RespuestaIntento.objects.filter(
                intento__cuestionario__in=cuestionarios
            ).count(),
            40,
        )

        for pregunta in preguntas:
            opciones = list(pregunta.opciones.all())
            self.assertGreater(pregunta.puntaje, 0)
            self.assertTrue(pregunta.retroalimentacion)
            self.assertEqual(sum(opcion.es_correcta for opcion in opciones), 1)
            if pregunta.tipo == TipoPregunta.MULTIPLE:
                self.assertIn(len(opciones), (2, 3, 4))
            else:
                self.assertEqual(
                    {opcion.texto_opcion for opcion in opciones},
                    {"Verdadero", "Falso"},
                )

        for cuestionario in cuestionarios:
            self.assertEqual(cuestionario.puntaje_total_posible, 5)

        self.assertEqual(
            get_periodos_disponibles(2026),
            [
                {"value": "1", "label": "1° semestre"},
                {"value": "2", "label": "2° semestre"},
            ],
        )
        for periodo, nombre in (
            ("1", "Práctica tecnológica TyT - Semestre I 2026"),
            ("2", "Práctica tecnológica TyT - Semestre II 2026"),
        ):
            cursos = get_cursos_disponibles(2026, periodo)
            cuestionario = next(
                item for item in cuestionarios if item.nombre == nombre
            )
            self.assertTrue(any(curso["nombre"] == nombre for curso in cursos))
            self.assertEqual(
                len(get_ejes_disponibles(2026, periodo, cuestionario.pk)),
                5,
            )

        indicadores = obtener_kpis(
            Intento.objects.filter(cuestionario__in=cuestionarios)
        )
        self.assertEqual(indicadores["estudiantes_distintos"], 2)
        self.assertEqual(indicadores["intentos_finalizados"], 4)
        self.assertEqual(indicadores["promedio"], 3.75)
        self.assertEqual(indicadores["porcentaje_aprobacion"], 75)

        estudiantes = Intento.objects.filter(
            cuestionario__in=cuestionarios
        ).values_list("usuario__nombre", "usuario__codigo").distinct()
        for nombre, codigo in estudiantes:
            self.assertIn("Practicante TyT", nombre)
            self.assertTrue(codigo.startswith("PRACTICA-TYT-"))
        for estudiante in Intento.objects.filter(
            cuestionario__in=cuestionarios
        ).values_list("usuario", flat=True).distinct():
            self.assertFalse(Usuario.objects.get(pk=estudiante).has_usable_password())

        conteos_antes = (
            Pregunta.objects.count(),
            OpcionRespuesta.objects.count(),
            Cuestionario.objects.count(),
            Intento.objects.count(),
            RespuestaIntento.objects.count(),
        )
        segunda_salida = StringIO()
        call_command("seed_practica_tyt", stdout=segunda_salida)
        conteos_despues = (
            Pregunta.objects.count(),
            OpcionRespuesta.objects.count(),
            Cuestionario.objects.count(),
            Intento.objects.count(),
            RespuestaIntento.objects.count(),
        )
        self.assertEqual(conteos_despues, conteos_antes)
        self.assertIn("preguntas creadas=0", segunda_salida.getvalue())

    def test_dry_run_no_escribe_datos(self):
        conteos_antes = (
            Pregunta.objects.count(),
            Cuestionario.objects.count(),
            Intento.objects.count(),
        )

        call_command("seed_practica_tyt", dry_run=True, stdout=StringIO())

        self.assertEqual(
            (
                Pregunta.objects.count(),
                Cuestionario.objects.count(),
                Intento.objects.count(),
            ),
            conteos_antes,
        )
