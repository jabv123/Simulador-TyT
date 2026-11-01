"""Reglas de negocio para el banco de preguntas."""

import unicodedata

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import OpcionRespuesta, Pregunta, TipoPregunta


def normalizar_texto(valor):
    texto = " ".join(valor.casefold().split())
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )


def validar_enunciado_unico(enunciado, categoria_id, excluir_id=None):
    normalizado = normalizar_texto(enunciado)
    candidatas = Pregunta.objects.filter(categoria_id=categoria_id)
    if excluir_id is not None:
        candidatas = candidatas.exclude(pk=excluir_id)
    if any(
        normalizar_texto(actual) == normalizado
        for actual in candidatas.values_list("enunciado", flat=True)
    ):
        raise ValidationError(
            {
                "enunciado": (
                    "Ya existe una pregunta con el mismo enunciado normalizado "
                    "en esta categoría."
                )
            }
        )


def validar_opciones(tipo, opciones):
    if not isinstance(opciones, list):
        raise ValidationError({"opciones": "Debes enviar una lista de opciones."})
    if tipo == TipoPregunta.MULTIPLE and not 2 <= len(opciones) <= 4:
        raise ValidationError(
            {"opciones": "Una pregunta de selección múltiple debe tener entre 2 y 4 opciones."}
        )
    if tipo == TipoPregunta.VERDADERO_FALSO and len(opciones) != 2:
        raise ValidationError(
            {"opciones": "Una pregunta de verdadero/falso debe tener exactamente dos opciones."}
        )
    if sum(bool(opcion.get("es_correcta")) for opcion in opciones) != 1:
        raise ValidationError(
            {"opciones": "Cada pregunta debe tener exactamente una respuesta correcta."}
        )
    for indice, opcion in enumerate(opciones, start=1):
        texto = opcion.get("texto_opcion")
        if not isinstance(texto, str) or not texto.strip():
            raise ValidationError(
                {"opciones": f"La opción {indice} debe incluir su texto."}
            )
    if tipo == TipoPregunta.VERDADERO_FALSO:
        textos = {
            normalizar_texto(opcion["texto_opcion"])
            for opcion in opciones
        }
        if textos != {"verdadero", "falso"}:
            raise ValidationError(
                {
                    "opciones": (
                        "Las opciones de verdadero/falso deben ser "
                        "'Verdadero' y 'Falso'."
                    )
                }
            )


@transaction.atomic
def crear_pregunta(*, datos, opciones, creado_por):
    validar_opciones(datos["tipo"], opciones)
    validar_enunciado_unico(datos["enunciado"], datos["categoria"].pk)
    pregunta = Pregunta.objects.create(**datos, creado_por=creado_por)
    OpcionRespuesta.objects.bulk_create(
        [
            OpcionRespuesta(pregunta=pregunta, **opcion)
            for opcion in opciones
        ]
    )
    return pregunta


@transaction.atomic
def actualizar_pregunta(*, pregunta, datos, opciones=None):
    campos_de_contenido = set(datos) - {"estado"}
    if pregunta.respuestas_intento.exists() and (
        campos_de_contenido or opciones is not None
    ):
        raise ValidationError(
            "No se puede modificar una pregunta que ya forma parte de un intento."
        )
    nuevo_tipo = datos.get("tipo", pregunta.tipo)
    if opciones is None and nuevo_tipo != pregunta.tipo:
        validar_opciones(
            nuevo_tipo,
            [
                {
                    "texto_opcion": opcion.texto_opcion,
                    "es_correcta": opcion.es_correcta,
                }
                for opcion in pregunta.opciones.all()
            ],
        )
    if opciones is not None:
        validar_opciones(nuevo_tipo, opciones)

    categoria = datos.get("categoria", pregunta.categoria)
    enunciado = datos.get("enunciado", pregunta.enunciado)
    if "categoria" in datos or "enunciado" in datos:
        validar_enunciado_unico(enunciado, categoria.pk, excluir_id=pregunta.pk)

    for campo, valor in datos.items():
        setattr(pregunta, campo, valor)
    pregunta.save()

    if opciones is not None:
        pregunta.opciones.all().delete()
        OpcionRespuesta.objects.bulk_create(
            [
                OpcionRespuesta(pregunta=pregunta, **opcion)
                for opcion in opciones
            ]
        )
    return pregunta
