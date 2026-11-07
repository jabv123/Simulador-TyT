from __future__ import annotations

from django import forms

from apps.accounts.models import CursoAcademico, Grupo, Usuario
from apps.questions.models import Categoria
from apps.quizzes.models import Cuestionario

from .selectors import (
    PERIODO_SEMESTRES,
    get_anios_disponibles,
    get_cursos_academicos_disponibles,
    get_cursos_disponibles,
    get_ejes_disponibles,
    get_estudiantes_disponibles,
    get_grupos_academicos_disponibles,
    get_periodos_disponibles,
    normalizar_periodo,
    periodo_a_mes_rango,
    periodo_a_rango_fechas,
)


class ReportFilterForm(forms.Form):
    TIPOS_RESUMEN = [
        ("general", "General"),
        ("curso", "Curso"),
        ("curso_grupo", "Curso / grupo"),
        ("estudiante", "Estudiante"),
        ("eje", "Eje temático"),
        ("periodo", "Año y período"),
        ("dificultad", "Preguntas de mayor dificultad"),
    ]

    anio = forms.IntegerField(required=False)
    periodo = forms.CharField(required=False, max_length=20)
    curso = forms.IntegerField(required=False)
    curso_academico = forms.IntegerField(required=False)
    grupo = forms.IntegerField(required=False)
    eje = forms.IntegerField(required=False)
    estudiante = forms.IntegerField(required=False)
    tipo = forms.ChoiceField(required=False, choices=TIPOS_RESUMEN)
    query = forms.CharField(required=False, max_length=80)

    def clean_anio(self):
        valor = self.cleaned_data.get("anio")
        if valor is not None and valor < 2000:
            raise forms.ValidationError("El año debe ser válido.")
        return valor

    def clean_periodo(self):
        valor = normalizar_periodo(self.cleaned_data.get("periodo"))
        if valor and valor not in PERIODO_SEMESTRES:
            raise forms.ValidationError("El período debe ser 1° o 2° semestre.")
        return valor

    def clean_curso(self):
        valor = self.cleaned_data.get("curso")
        if valor is not None and valor <= 0:
            raise forms.ValidationError("El curso es inválido.")
        return valor

    def clean_estudiante(self):
        valor = self.cleaned_data.get("estudiante")
        if valor is not None and valor <= 0:
            raise forms.ValidationError("El estudiante es inválido.")
        return valor

    def clean_curso_academico(self):
        valor = self.cleaned_data.get("curso_academico")
        if valor is not None and not CursoAcademico.objects.filter(pk=valor).exists():
            raise forms.ValidationError("El curso académico no existe.")
        return valor

    def clean_grupo(self):
        valor = self.cleaned_data.get("grupo")
        if valor is not None and not Grupo.objects.filter(pk=valor).exists():
            raise forms.ValidationError("El grupo académico no existe.")
        return valor

    def clean(self):
        cleaned = super().clean()
        anio = cleaned.get("anio")
        periodo = cleaned.get("periodo")
        curso = cleaned.get("curso")
        curso_academico = cleaned.get("curso_academico")
        grupo = cleaned.get("grupo")
        eje = cleaned.get("eje")
        estudiante = cleaned.get("estudiante")

        if grupo:
            grupo_curso_id = Grupo.objects.filter(pk=grupo).values_list(
                "curso_id", flat=True
            ).first()
            if curso_academico and curso_academico != grupo_curso_id:
                self.add_error("grupo", "El grupo no pertenece al curso académico seleccionado.")
            elif not curso_academico:
                cleaned["curso_academico"] = grupo_curso_id

        if anio and curso:
            if not Cuestionario.objects.filter(pk=curso, fecha_apertura__year=anio).exists():
                cleaned["curso"] = None

        if periodo and curso:
            rango = periodo_a_mes_rango(periodo)
            if rango is not None:
                cuestionario = Cuestionario.objects.filter(pk=curso).first()
                es_valido = False
                if cuestionario and cuestionario.fecha_apertura is not None:
                    mes = cuestionario.fecha_apertura.month
                    if (anio is None or cuestionario.fecha_apertura.year == anio) and rango[0] <= mes <= rango[1]:
                        es_valido = True
                if not es_valido:
                    cleaned["curso"] = None
                    cleaned["periodo"] = ""

        if estudiante and curso:
            if not Usuario.objects.filter(pk=estudiante, intentos__cuestionario_id=curso).exists():
                cleaned["estudiante"] = None

        if eje and curso:
            if not Cuestionario.objects.filter(pk=curso, preguntas__categoria_id=eje).exists():
                cleaned["eje"] = None

        return cleaned

    def get_filters(self):
        data = {}
        for campo in [
            "anio",
            "periodo",
            "curso",
            "curso_academico",
            "grupo",
            "eje",
            "estudiante",
            "tipo",
            "query",
        ]:
            valor = self.cleaned_data.get(campo)
            if valor not in (None, "", False):
                data[campo] = valor
        return data


def obtener_anios_disponibles():
    return get_anios_disponibles()


def obtener_periodos_disponibles(anio=None):
    return get_periodos_disponibles(anio)


def obtener_cursos_disponibles(anio=None, periodo=None):
    return get_cursos_disponibles(anio, periodo)


def obtener_cursos_academicos_disponibles():
    return get_cursos_academicos_disponibles()


def obtener_grupos_academicos_disponibles(curso_academico=None):
    return get_grupos_academicos_disponibles(curso_academico)


def obtener_ejes_disponibles(anio=None, periodo=None, curso=None):
    return get_ejes_disponibles(anio, periodo, curso)


def obtener_estudiantes_disponibles(
    curso=None,
    texto=None,
    anio=None,
    periodo=None,
    curso_academico=None,
    grupo=None,
    include_identificacion=True,
):
    return get_estudiantes_disponibles(
        curso,
        texto,
        anio,
        periodo,
        curso_academico,
        grupo,
        include_identificacion,
    )
