"""Operaciones transaccionales de presentación y calificación automática."""

import random
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.quizzes.models import CuestionarioPregunta
from apps.quizzes.services import cuestionario_puede_iniciarse

from .models import EstadoIntento, Intento, RespuestaIntento


DOS_DECIMALES = Decimal("0.01")


def _vence_en(intento):
    limite_por_tiempo = intento.fecha_inicio + timedelta(
        minutes=intento.cuestionario.tiempo_limite_minutos
    )
    return min(limite_por_tiempo, intento.cuestionario.fecha_cierre)


def _validar_estudiante(usuario):
    if (
        not usuario.is_authenticated
        or not usuario.is_active
        or usuario.rol.estado != "ACTIVO"
        or usuario.rol.nombre.casefold() != "estudiante"
    ):
        raise PermissionDenied("Solo un estudiante activo puede presentar cuestionarios.")


@transaction.atomic
def iniciar_intento(*, cuestionario, usuario):
    _validar_estudiante(usuario)
    cuestionario = type(cuestionario).objects.select_for_update().get(
        pk=cuestionario.pk
    )
    ahora = timezone.now()
    existentes = Intento.objects.filter(
        cuestionario=cuestionario,
        usuario=usuario,
    )
    en_progreso = existentes.filter(estado=EstadoIntento.EN_PROGRESO).first()
    if en_progreso:
        if ahora >= _vence_en(en_progreso):
            return finalizar_intento(en_progreso, agotado=True)
        return en_progreso

    if not cuestionario_puede_iniciarse(cuestionario, ahora):
        raise ValidationError(
            "El cuestionario no está dentro de su período disponible."
        )

    usados = existentes.count()
    if usados >= cuestionario.intentos_permitidos:
        raise ValidationError("Ya alcanzaste el máximo de intentos permitidos.")

    preguntas = list(
        CuestionarioPregunta.objects.filter(
            cuestionario=cuestionario,
            pregunta__estado="Activo",
        )
    )
    if not preguntas:
        raise ValidationError("El cuestionario todavía no tiene preguntas activas.")

    intento = Intento.objects.create(
        cuestionario=cuestionario,
        usuario=usuario,
        numero_intento=usados + 1,
    )
    RespuestaIntento.objects.bulk_create(
        [
            RespuestaIntento(intento=intento, pregunta=item.pregunta)
            for item in preguntas
        ]
    )
    return intento


@transaction.atomic
def guardar_respuesta(
    *,
    intento_id,
    usuario,
    pregunta_id,
    opcion_id=None,
    marcada_para_revision=None,
    actualizar_opcion=True,
):
    intento = (
        Intento.objects.select_for_update()
        .select_related("cuestionario")
        .filter(pk=intento_id)
        .first()
    )
    if intento is None:
        raise ValidationError("El intento solicitado no existe.")
    if intento.usuario_id != usuario.pk:
        raise PermissionDenied("No puedes responder un intento de otra persona.")
    if intento.estado != EstadoIntento.EN_PROGRESO:
        raise ValidationError("El intento ya está finalizado.")
    if timezone.now() >= _vence_en(intento):
        finalizar_intento(intento, agotado=True)
        return None

    respuesta = (
        intento.respuestas.select_related("pregunta")
        .filter(pregunta_id=pregunta_id)
        .first()
    )
    if respuesta is None:
        raise ValidationError("La pregunta no pertenece a este intento.")

    if actualizar_opcion:
        opcion = None
        if opcion_id is not None:
            opcion = respuesta.pregunta.opciones.filter(pk=opcion_id).first()
            if opcion is None:
                raise ValidationError(
                    "La opción seleccionada no corresponde a la pregunta."
                )

        relacion = intento.cuestionario.preguntas_configuradas.get(
            pregunta_id=pregunta_id
        )
        respuesta.opcion_seleccionada = opcion
        respuesta.es_correcta = bool(opcion and opcion.es_correcta)
        respuesta.puntaje_obtenido = (
            relacion.puntaje if respuesta.es_correcta else Decimal("0")
        )
    if marcada_para_revision is not None:
        respuesta.marcada_para_revision = marcada_para_revision
    campos_actualizar = ["marcada_para_revision", "fecha_respuesta"]
    if actualizar_opcion:
        campos_actualizar.extend([
            "opcion_seleccionada",
            "es_correcta",
            "puntaje_obtenido",
        ])
    respuesta.save(update_fields=campos_actualizar)
    return respuesta


@transaction.atomic
def finalizar_intento(intento, *, agotado=False):
    intento = (
        Intento.objects.select_for_update()
        .select_related("cuestionario")
        .get(pk=intento.pk)
    )
    if intento.estado != EstadoIntento.EN_PROGRESO:
        return intento

    ahora = timezone.now()
    agotado = agotado or ahora >= _vence_en(intento)
    if intento.cuestionario.fecha_cierre <= ahora:
        agotado = True
    relacion = CuestionarioPregunta.objects.filter(
        cuestionario=intento.cuestionario
    )
    puntaje_total = sum((item.puntaje for item in relacion), Decimal("0"))
    if puntaje_total <= 0:
        raise ValidationError("No es posible calificar un cuestionario sin puntaje.")

    relaciones = list(relacion.select_related("pregunta"))
    for item in relaciones:
        RespuestaIntento.objects.get_or_create(
            intento=intento,
            pregunta=item.pregunta,
        )
    respuestas = list(
        RespuestaIntento.objects.filter(intento=intento).select_related(
            "opcion_seleccionada"
        )
    )
    puntajes_por_pregunta = {
        item.pregunta_id: item.puntaje for item in relaciones
    }
    total_obtenido = sum(
        (
            puntajes_por_pregunta.get(item.pregunta_id, Decimal("0"))
            if item.opcion_seleccionada_id
            and item.opcion_seleccionada.es_correcta
            else Decimal("0")
            for item in respuestas
        ),
        Decimal("0"),
    )
    nota = (
        total_obtenido
        / puntaje_total
        * intento.cuestionario.calificacion_maxima
    ).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)
    limite = min(ahora, _vence_en(intento))
    intento.fecha_fin = ahora
    intento.duracion_segundos = max(
        0, int((limite - intento.fecha_inicio).total_seconds())
    )
    intento.puntaje_obtenido = total_obtenido.quantize(
        DOS_DECIMALES, rounding=ROUND_HALF_UP
    )
    intento.calificacion_final = nota
    intento.estado = (
        EstadoIntento.TIEMPO_AGOTADO if agotado else EstadoIntento.FINALIZADO
    )
    intento.save(
        update_fields=[
            "fecha_fin",
            "duracion_segundos",
            "puntaje_obtenido",
            "calificacion_final",
            "estado",
        ]
    )
    return intento


def finalizar_si_vencido(intento, ahora=None):
    """Finaliza automáticamente al alcanzar el límite de tiempo o de cierre."""
    if intento.estado != EstadoIntento.EN_PROGRESO:
        return intento
    intento.cuestionario.refresh_from_db(
        fields=["fecha_cierre", "tiempo_limite_minutos", "estado"]
    )
    ahora = ahora or timezone.now()
    if ahora >= _vence_en(intento):
        return finalizar_intento(intento, agotado=True)
    return intento


def finalizar_vencidos(queryset, ahora=None):
    """Aplica vencimientos antes de exponer intentos en una consulta."""
    ahora = ahora or timezone.now()
    for intento in queryset.filter(estado=EstadoIntento.EN_PROGRESO).select_related(
        "cuestionario"
    ):
        finalizar_si_vencido(intento, ahora)


def obtener_resultado_final(intento):
    """Calcula el estado de aprobación en el servidor para el intento finalizado."""
    return {
        "calificacion_final": intento.calificacion_final,
        "aprobado": (
            intento.calificacion_final
            >= intento.cuestionario.calificacion_aprobacion
        ),
    }


def preguntas_presentacion(intento):
    """Devuelve orden y opciones deterministas por intento sin filtrar la clave."""
    preguntas = list(
        intento.cuestionario.preguntas_configuradas.select_related(
            "pregunta"
        ).prefetch_related("pregunta__opciones")
    )
    semilla = random.Random(intento.pk)
    if intento.cuestionario.mezclar_preguntas:
        semilla.shuffle(preguntas)
    resultado = []
    for relacion in preguntas:
        opciones = list(relacion.pregunta.opciones.all())
        if intento.cuestionario.mezclar_respuestas:
            semilla.shuffle(opciones)
        resultado.append((relacion, opciones))
    return resultado
