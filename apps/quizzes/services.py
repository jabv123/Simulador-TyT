"""Reglas de negocio para configurar cuestionarios."""

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.questions.models import EstadoContenido, Pregunta

from .models import Cuestionario, CuestionarioPregunta, EstadoCuestionario


def sincronizar_estado(cuestionario, ahora):
    estado_actual = cuestionario.estado
    nuevo_estado = cuestionario.estado_efectivo(ahora)
    if nuevo_estado != estado_actual:
        cuestionario.estado = nuevo_estado
        cuestionario.save(update_fields=["estado"])
    return cuestionario


def validar_preguntas(preguntas):
    if not isinstance(preguntas, list) or not preguntas:
        raise ValidationError(
            {"preguntas": "El cuestionario debe incluir al menos una pregunta."}
        )
    ids = [item["pregunta"].pk for item in preguntas]
    if len(ids) != len(set(ids)):
        raise ValidationError(
            {"preguntas": "No puedes agregar la misma pregunta más de una vez."}
        )
    if Pregunta.objects.filter(
        pk__in=ids,
        estado=EstadoContenido.ACTIVO,
    ).count() != len(ids):
        raise ValidationError(
            {"preguntas": "Todas las preguntas deben existir y estar activas."}
        )
    ordenes = [item.get("orden", indice) for indice, item in enumerate(preguntas, 1)]
    if any(orden <= 0 for orden in ordenes):
        raise ValidationError(
            {"preguntas": "El orden de cada pregunta debe ser mayor que cero."}
        )
    if len(ordenes) != len(set(ordenes)):
        raise ValidationError(
            {"preguntas": "No puedes repetir el orden de una pregunta."}
        )
    if any(item["puntaje"] <= 0 for item in preguntas):
        raise ValidationError(
            {"preguntas": "El puntaje por pregunta debe ser mayor que cero."}
        )


def validar_datos_cuestionario(datos):
    apertura = datos.get("fecha_apertura")
    cierre = datos.get("fecha_cierre")
    if apertura is not None and cierre is not None and cierre <= apertura:
        raise ValidationError(
            {"fecha_cierre": "La fecha de cierre debe ser posterior a la apertura."}
        )

    maximo = datos.get("calificacion_maxima")
    aprobacion = datos.get("calificacion_aprobacion")
    if maximo is not None and maximo <= 0:
        raise ValidationError(
            {"calificacion_maxima": "La calificación máxima debe ser mayor que cero."}
        )
    if aprobacion is not None and aprobacion < 0:
        raise ValidationError(
            {"calificacion_aprobacion": "La nota de aprobación no puede ser negativa."}
        )
    if maximo is not None and aprobacion is not None and aprobacion > maximo:
        raise ValidationError(
            {
                "calificacion_aprobacion": (
                    "La nota de aprobación no puede superar la máxima."
                )
            }
        )
    for campo, etiqueta in (
        ("tiempo_limite_minutos", "El tiempo límite"),
        ("intentos_permitidos", "La cantidad de intentos"),
    ):
        valor = datos.get(campo)
        if valor is not None and valor <= 0:
            raise ValidationError({campo: f"{etiqueta} debe ser mayor que cero."})


def _validar_modelo(cuestionario):
    try:
        cuestionario.full_clean()
    except DjangoValidationError as error:
        raise ValidationError(error.message_dict) from error


@transaction.atomic
def crear_cuestionario(*, datos, preguntas=None, docente):
    validar_datos_cuestionario(datos)
    preguntas = preguntas or []
    if preguntas:
        validar_preguntas(preguntas)
    cuestionario = Cuestionario(docente=docente, **datos)
    if cuestionario.estado != EstadoCuestionario.BORRADOR and not preguntas:
        raise ValidationError(
            {"preguntas": "Agrega al menos una pregunta antes de publicar."}
        )
    _validar_modelo(cuestionario)
    cuestionario.save()
    if preguntas:
        CuestionarioPregunta.objects.bulk_create(
            [
                CuestionarioPregunta(
                    cuestionario=cuestionario,
                    pregunta=item["pregunta"],
                    orden=item.get("orden", indice),
                    puntaje=item["puntaje"],
                )
                for indice, item in enumerate(preguntas, start=1)
            ]
        )
    sincronizar_estado(cuestionario, timezone.now())
    return cuestionario


@transaction.atomic
def actualizar_cuestionario(*, cuestionario, datos, preguntas=None):
    validar_datos_cuestionario(datos)
    if cuestionario.intentos.exists():
        if preguntas is not None or datos != {
            "estado": EstadoCuestionario.CERRADO
        }:
            raise ValidationError(
                "Un cuestionario con intentos solo puede cerrarse; no se permite "
                "editar sus datos, preguntas ni puntajes."
            )
    if preguntas is not None:
        if preguntas:
            validar_preguntas(preguntas)
        elif cuestionario.estado != EstadoCuestionario.BORRADOR:
            raise ValidationError(
                {"preguntas": "Desactiva el cuestionario antes de quitar todas sus preguntas."}
            )

    for campo, valor in datos.items():
        setattr(cuestionario, campo, valor)
    preguntas_actuales = (
        preguntas
        if preguntas is not None
        else list(cuestionario.preguntas_configuradas.all())
    )
    if (
        cuestionario.estado
        in {EstadoCuestionario.PROGRAMADO, EstadoCuestionario.DISPONIBLE}
        and not preguntas_actuales
    ):
        raise ValidationError(
            {"preguntas": "Agrega al menos una pregunta antes de publicar."}
        )
    _validar_modelo(cuestionario)
    cuestionario.save()
    if preguntas is not None:
        cuestionario.preguntas_configuradas.all().delete()
        CuestionarioPregunta.objects.bulk_create(
            [
                CuestionarioPregunta(
                    cuestionario=cuestionario,
                    pregunta=item["pregunta"],
                    orden=item.get("orden", indice),
                    puntaje=item["puntaje"],
                )
                for indice, item in enumerate(preguntas, start=1)
            ]
        )
    sincronizar_estado(cuestionario, timezone.now())
    return cuestionario


def _validar_sin_intentos(cuestionario):
    if cuestionario.intentos.exists():
        raise ValidationError(
            "No se pueden modificar las preguntas ni los puntajes "
            "después de iniciar un intento."
        )


@transaction.atomic
def agregar_pregunta(*, cuestionario, pregunta, puntaje, orden=None):
    cuestionario = Cuestionario.objects.select_for_update().get(pk=cuestionario.pk)
    _validar_sin_intentos(cuestionario)
    if orden is None:
        mayor_orden = cuestionario.preguntas_configuradas.order_by(
            "-orden"
        ).values_list("orden", flat=True).first()
        orden = (mayor_orden or 0) + 1
    validar_preguntas(
        [{"pregunta": pregunta, "puntaje": puntaje, "orden": orden}]
    )
    if cuestionario.preguntas_configuradas.filter(pregunta=pregunta).exists():
        raise ValidationError(
            {"pregunta": "Esta pregunta ya pertenece al cuestionario."}
        )
    if cuestionario.preguntas_configuradas.filter(orden=orden).exists():
        raise ValidationError(
            {"orden": "No puedes repetir el orden de otra pregunta."}
        )
    return CuestionarioPregunta.objects.create(
        cuestionario=cuestionario,
        pregunta=pregunta,
        puntaje=puntaje,
        orden=orden,
    )


@transaction.atomic
def reemplazar_preguntas(*, cuestionario, preguntas):
    cuestionario = Cuestionario.objects.select_for_update().get(pk=cuestionario.pk)
    _validar_sin_intentos(cuestionario)
    if preguntas:
        validar_preguntas(preguntas)
    elif cuestionario.estado != EstadoCuestionario.BORRADOR:
        raise ValidationError(
            {"preguntas": "Desactiva el cuestionario antes de quitar todas sus preguntas."}
        )
    cuestionario.preguntas_configuradas.all().delete()
    CuestionarioPregunta.objects.bulk_create(
        [
            CuestionarioPregunta(
                cuestionario=cuestionario,
                pregunta=item["pregunta"],
                orden=item.get("orden", indice),
                puntaje=item["puntaje"],
            )
            for indice, item in enumerate(preguntas, start=1)
        ]
    )
    return cuestionario


@transaction.atomic
def actualizar_pregunta(*, cuestionario, pregunta_id, datos):
    cuestionario = Cuestionario.objects.select_for_update().get(pk=cuestionario.pk)
    _validar_sin_intentos(cuestionario)
    relacion = cuestionario.preguntas_configuradas.filter(
        pregunta_id=pregunta_id
    ).first()
    if relacion is None:
        raise ValidationError("La pregunta no pertenece a este cuestionario.")
    puntaje = datos.get("puntaje", relacion.puntaje)
    orden = datos.get("orden", relacion.orden)
    otros = [
        item.orden
        for item in cuestionario.preguntas_configuradas.exclude(
            pk=relacion.pk
        )
    ]
    if orden in otros:
        raise ValidationError(
            {"orden": "No puedes repetir el orden de otra pregunta."}
        )
    if puntaje <= 0 or orden <= 0:
        raise ValidationError(
            "El orden y el puntaje de la pregunta deben ser mayores que cero."
        )
    relacion.puntaje = puntaje
    relacion.orden = orden
    relacion.save(update_fields=["puntaje", "orden"])
    return relacion


@transaction.atomic
def quitar_pregunta(*, cuestionario, pregunta_id):
    cuestionario = Cuestionario.objects.select_for_update().get(pk=cuestionario.pk)
    _validar_sin_intentos(cuestionario)
    relacion = cuestionario.preguntas_configuradas.filter(
        pregunta_id=pregunta_id
    ).first()
    if relacion is None:
        raise ValidationError("La pregunta no pertenece a este cuestionario.")
    if (
        cuestionario.estado != EstadoCuestionario.BORRADOR
        and cuestionario.preguntas_configuradas.count() == 1
    ):
        raise ValidationError(
            "Desactiva el cuestionario antes de quitar su última pregunta."
        )
    relacion.delete()


@transaction.atomic
def publicar_cuestionario(cuestionario):
    cuestionario = Cuestionario.objects.select_for_update().get(pk=cuestionario.pk)
    if not cuestionario.preguntas_configuradas.exists():
        raise ValidationError(
            {"preguntas": "No se puede publicar un cuestionario sin preguntas."}
        )
    ahora = timezone.now()
    if ahora > cuestionario.fecha_cierre:
        raise ValidationError(
            "No se puede publicar un cuestionario cuyo período ya finalizó."
        )
    cuestionario.estado = (
        EstadoCuestionario.PROGRAMADO
        if ahora < cuestionario.fecha_apertura
        else EstadoCuestionario.DISPONIBLE
    )
    cuestionario.save()
    return cuestionario


@transaction.atomic
def desactivar_cuestionario(cuestionario):
    cuestionario = Cuestionario.objects.select_for_update().get(pk=cuestionario.pk)
    cuestionario.estado = (
        EstadoCuestionario.CERRADO
        if cuestionario.intentos.exists()
        else EstadoCuestionario.BORRADOR
    )
    cuestionario.save()
    return cuestionario


def cuestionario_puede_iniciarse(cuestionario, ahora):
    sincronizar_estado(cuestionario, ahora)
    return (
        cuestionario.estado == EstadoCuestionario.DISPONIBLE
        and cuestionario.fecha_apertura <= ahora <= cuestionario.fecha_cierre
    )
