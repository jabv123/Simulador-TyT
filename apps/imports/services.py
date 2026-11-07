"""Importación fila a fila y con reporte de errores del libro Excel."""

import json
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile
from decimal import Decimal, InvalidOperation
from pathlib import PurePath

from django.db import transaction
from django.db import DataError, IntegrityError
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from rest_framework.exceptions import ValidationError

from apps.questions.models import (
    Categoria,
    EstadoContenido,
    OpcionRespuesta,
    Pregunta,
    TipoPregunta,
)
from apps.questions.services import normalizar_texto
from apps.quizzes.models import CuestionarioPregunta

from .models import Importacion


TAMANO_MAXIMO_ARCHIVO = 10 * 1024 * 1024
ENCABEZADOS_OBLIGATORIOS = {
    "categoria",
    "tipo",
    "enunciado",
    "opcion_1",
    "opcion_2",
    "respuesta_correcta",
    "puntaje",
}
ENCABEZADOS_PLANTILLA = (
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
)


def _normalizar_encabezado(valor):
    texto = str(valor or "").strip().casefold().replace(" ", "_")
    alias = {
        "pregunta": "enunciado",
        "opcion_a": "opcion_1",
        "opcion_b": "opcion_2",
        "opcion_c": "opcion_3",
        "opcion_d": "opcion_4",
    }
    return alias.get(texto, texto)


def _buscar_categoria(nombre):
    normalizado = normalizar_texto(nombre)
    return next(
        (
            categoria
            for categoria in Categoria.objects.all()
            if normalizar_texto(categoria.nombre) == normalizado
        ),
        None,
    )


def _abrir_libro(archivo):
    if PurePath(archivo.name).suffix.casefold() != ".xlsx":
        raise ValidationError("El archivo debe tener formato .xlsx.")
    if archivo.size > TAMANO_MAXIMO_ARCHIVO:
        raise ValidationError("El archivo no puede superar los 10 MB.")
    try:
        archivo.seek(0)
        return load_workbook(archivo, read_only=True, data_only=True)
    except (
        InvalidFileException,
        BadZipFile,
        OSError,
        ValueError,
        KeyError,
        ParseError,
    ) as error:
        raise ValidationError(
            "No se pudo leer el Excel. Verifica que sea un archivo .xlsx válido."
        ) from error


def _validar_fila_importacion(fila):
    categoria = str(fila.get("categoria") or "").strip()
    tipo_original = str(fila.get("tipo") or "").strip()
    enunciado = str(fila.get("enunciado") or "").strip()
    if not categoria:
        raise ValueError("falta la categoría")
    if not tipo_original:
        raise ValueError("falta el tipo")
    if not enunciado:
        raise ValueError("falta la pregunta")
    tipo = _normalizar_tipo(tipo_original)
    texto_correcto = str(fila.get("respuesta_correcta") or "").strip().upper()
    if texto_correcto not in {"A", "B", "C", "D"}:
        raise ValueError("la respuesta correcta debe indicar A, B, C o D")
    numero_correcto = ord(texto_correcto) - ord("A") + 1
    opciones = []
    for numero in range(1, 5):
        texto = fila.get(f"opcion_{numero}")
        texto = str(texto or "").strip()
        if texto:
            opciones.append(
                {
                    "numero": numero,
                    "texto_opcion": texto,
                    "es_correcta": numero == numero_correcto,
                    "retroalimentacion": None,
                }
            )
    if tipo == TipoPregunta.MULTIPLE and not 2 <= len(opciones) <= 4:
        raise ValueError("MULTIPLE requiere entre 2 y 4 opciones")
    if tipo == TipoPregunta.VERDADERO_FALSO and len(opciones) != 2:
        raise ValueError("VERDADERO_FALSO requiere exactamente dos opciones")
    if numero_correcto not in {opcion["numero"] for opcion in opciones}:
        raise ValueError("la respuesta correcta apunta a una opción vacía")
    indices = [opcion["numero"] for opcion in opciones]
    if indices != list(range(1, len(indices) + 1)):
        raise ValueError("las opciones deben estar completas y en orden desde la opción A")
    if tipo == TipoPregunta.VERDADERO_FALSO and {
        normalizar_texto(opcion["texto_opcion"]) for opcion in opciones
    } != {"verdadero", "falso"}:
        raise ValueError("VERDADERO_FALSO requiere las opciones Verdadero y Falso")
    for opcion in opciones:
        opcion.pop("numero")

    try:
        puntaje = Decimal(str(fila.get("puntaje") or "").strip())
    except (InvalidOperation, ValueError) as error:
        raise ValueError("el puntaje debe ser numérico") from error
    if not puntaje.is_finite() or puntaje <= 0:
        raise ValueError("el puntaje debe ser mayor que cero")
    if puntaje > Decimal("999.99") or puntaje != puntaje.quantize(Decimal("0.01")):
        raise ValueError("el puntaje no puede superar 999.99 ni tener más de 2 decimales")

    opciones_texto = [
        str(fila.get(f"opcion_{numero}") or "").strip()
        for numero in range(1, 5)
    ]
    indices = [indice for indice, valor in enumerate(opciones_texto) if valor]
    if indices != list(range(len(indices))):
        raise ValueError("las opciones deben estar completas y en orden desde la opción A")
    return {
        "categoria": categoria,
        "tipo": tipo,
        "texto_base": str(fila.get("texto_base") or "").strip() or None,
        "enunciado": enunciado,
        "retroalimentacion": str(fila.get("retroalimentacion") or "").strip() or None,
        "puntaje": str(puntaje.quantize(Decimal("0.01"))),
        "opciones": opciones,
    }


def previsualizar_preguntas_excel(archivo):
    """Clasifica filas del Excel sin crear categorías, preguntas ni importaciones."""
    libro = _abrir_libro(archivo)
    try:
        hoja = libro.active
        if hoja is None:
            raise ValidationError("El archivo no contiene una hoja de cálculo activa.")
        iterador = hoja.iter_rows(values_only=True)
        encabezados_originales = next(iterador, None)
        if not encabezados_originales:
            raise ValidationError("El archivo no contiene una fila de encabezados.")
        encabezados = [_normalizar_encabezado(valor) for valor in encabezados_originales]
        requeridos = {
            "categoria",
            "tipo",
            "enunciado",
            "opcion_1",
            "opcion_2",
            "respuesta_correcta",
            "puntaje",
        }
        faltantes = requeridos - set(encabezados)
        if faltantes:
            raise ValidationError(
                {
                    "archivo": (
                        "Faltan columnas obligatorias: "
                        + ", ".join(sorted(faltantes))
                    )
                }
            )

        validas = []
        duplicadas = []
        errores = []
        claves_archivo = set()
        for numero_fila, valores in enumerate(iterador, start=2):
            if not any(valor is not None and str(valor).strip() for valor in valores):
                continue
            fila = dict(zip(encabezados, valores))
            try:
                datos = _validar_fila_importacion(fila)
                categoria_existente = _buscar_categoria(datos["categoria"])
                if categoria_existente and categoria_existente.estado != EstadoContenido.ACTIVO:
                    raise ValueError("la categoría existente está inactiva")

                clave = (
                    normalizar_texto(datos["categoria"]),
                    normalizar_texto(datos["enunciado"]),
                )
                motivo_duplicado = None
                pregunta_existente = None
                if clave in claves_archivo:
                    motivo_duplicado = (
                        f"Fila {numero_fila}: pregunta duplicada dentro del archivo"
                    )
                else:
                    claves_archivo.add(clave)
                    if categoria_existente:
                        candidatas = Pregunta.objects.filter(
                            categoria_id=categoria_existente.pk
                        ).values_list("id", "enunciado", "estado")
                        pregunta_existente = next(
                            (
                                (pk, estado)
                                for pk, enunciado, estado in candidatas
                                if normalizar_texto(enunciado)
                                == normalizar_texto(datos["enunciado"])
                            ),
                            None,
                        )
                        if pregunta_existente:
                            motivo_duplicado = (
                                f"Fila {numero_fila}: la pregunta ya existe en el banco"
                            )
                resultado = {
                    "fila": numero_fila,
                    "motivo": motivo_duplicado,
                    "datos": datos,
                    "categoria": {
                        "nombre": datos["categoria"],
                        "estado": (
                            "existente"
                            if categoria_existente
                            else "se creará automáticamente"
                        ),
                    },
                    "pregunta_existente_id": (
                        pregunta_existente[0] if pregunta_existente else None
                    ),
                    "pregunta_existente_activa": (
                        pregunta_existente[1] == EstadoContenido.ACTIVO
                        if pregunta_existente
                        else None
                    ),
                }
                if motivo_duplicado:
                    duplicadas.append(resultado)
                else:
                    validas.append(resultado)
            except (ValueError, TypeError, InvalidOperation) as error:
                errores.append(
                    {
                        "fila": numero_fila,
                        "motivo": f"Fila {numero_fila}: {error}",
                    }
                )
        return {
            "total_registros": len(validas) + len(duplicadas) + len(errores),
            "validas": validas,
            "duplicadas": duplicadas,
            "errores": errores,
        }
    finally:
        libro.close()


@transaction.atomic
def confirmar_importacion_excel(*, archivo, usuario, cuestionario):
    """Revalida el archivo y guarda sus filas aceptables en una transacción."""
    previsualizacion = previsualizar_preguntas_excel(archivo)
    if cuestionario and cuestionario.intentos.exists():
        raise ValidationError(
            "No se pueden importar preguntas a un cuestionario que ya tiene intentos."
        )

    nuevas_por_clave = {}
    errores = list(previsualizacion["errores"])
    exitosos = 0
    elementos_aplicados = 0
    preguntas_agregadas_cuestionario = 0
    validas_aplicadas = []
    relacionadas = set()
    if cuestionario:
        relacionadas = set(
            CuestionarioPregunta.objects.filter(
                cuestionario=cuestionario
            ).values_list("pregunta_id", flat=True)
        )
        puntaje_actual = sum(
            CuestionarioPregunta.objects.filter(
                cuestionario=cuestionario
            ).values_list("puntaje", flat=True),
            Decimal("0"),
        )
    else:
        puntaje_actual = Decimal("0")

    filas_guardables = [
        *previsualizacion["validas"],
        *previsualizacion["duplicadas"],
    ]
    filas_guardables.sort(key=lambda item: item["fila"])
    ultimo_orden = (
        CuestionarioPregunta.objects.filter(cuestionario=cuestionario)
        .order_by("-orden")
        .values_list("orden", flat=True)
        .first()
        or 0
    ) if cuestionario else 0

    for item in filas_guardables:
        datos = item["datos"]
        puntaje = Decimal(datos["puntaje"])
        if (
            cuestionario
            and not (
                item["pregunta_existente_id"]
                and item["pregunta_existente_id"] in relacionadas
            )
            and puntaje_actual + puntaje > Decimal("999.99")
        ):
            errores.append(
                {
                    "fila": item["fila"],
                    "motivo": (
                        f"Fila {item['fila']}: el puntaje total del cuestionario "
                        "superaría 999.99"
                    ),
                }
            )
            continue
        if item["pregunta_existente_id"]:
            pregunta = Pregunta.objects.get(pk=item["pregunta_existente_id"])
            clave = (
                normalizar_texto(datos["categoria"]),
                normalizar_texto(datos["enunciado"]),
            )
            nuevas_por_clave[clave] = pregunta
        else:
            clave = (
                normalizar_texto(datos["categoria"]),
                normalizar_texto(datos["enunciado"]),
            )
            pregunta = nuevas_por_clave.get(clave)
            if pregunta is None:
                categoria = _buscar_categoria(datos["categoria"])
                if categoria is None:
                    categoria = Categoria.objects.create(
                        nombre=datos["categoria"],
                        estado=EstadoContenido.ACTIVO,
                    )
                pregunta = Pregunta.objects.create(
                    categoria=categoria,
                    tipo=datos["tipo"],
                    texto_base=datos["texto_base"],
                    enunciado=datos["enunciado"],
                    retroalimentacion=datos["retroalimentacion"],
                    puntaje=Decimal(datos["puntaje"]),
                    creado_por=usuario,
                )
                OpcionRespuesta.objects.bulk_create(
                    [
                        OpcionRespuesta(pregunta=pregunta, **opcion)
                        for opcion in datos["opciones"]
                    ]
                )
                nuevas_por_clave[clave] = pregunta
                exitosos += 1
                elementos_aplicados += 1
            else:
                nuevas_por_clave[clave] = pregunta

        if not cuestionario or pregunta.pk in relacionadas:
            if not item.get("motivo"):
                validas_aplicadas.append(
                    {
                        "fila": item["fila"],
                        "categoria": datos["categoria"],
                        "pregunta": datos["enunciado"],
                    }
                )
            continue
        if pregunta.estado != EstadoContenido.ACTIVO:
            if item.get("pregunta_existente_id"):
                errores.append(
                    {
                        "fila": item["fila"],
                        "motivo": (
                            f"Fila {item['fila']}: la pregunta duplicada está inactiva "
                            "y no se puede agregar al cuestionario"
                        ),
                    }
                )
            continue
        ultimo_orden += 1
        CuestionarioPregunta.objects.create(
            cuestionario=cuestionario,
            pregunta=pregunta,
            orden=ultimo_orden,
            puntaje=puntaje,
        )
        puntaje_actual += puntaje
        relacionadas.add(pregunta.pk)
        elementos_aplicados += 1
        preguntas_agregadas_cuestionario += 1
        if not item.get("motivo"):
            validas_aplicadas.append(
                {
                    "fila": item["fila"],
                    "categoria": datos["categoria"],
                    "pregunta": datos["enunciado"],
                }
            )

    filas_fallidas = {
        item["fila"] for item in errores
    } | {
        item["fila"] for item in previsualizacion["duplicadas"]
    }
    fallidos = len(filas_fallidas)
    if elementos_aplicados and errores:
        resultado = "Parcial"
    elif elementos_aplicados:
        resultado = "Exitoso"
    elif previsualizacion["duplicadas"] and not errores:
        resultado = "Sin cambios"
    elif errores:
        resultado = "Fallido"
    else:
        resultado = "Sin cambios"
    importacion = Importacion.objects.create(
        usuario=usuario,
        cuestionario=cuestionario,
        nombre_archivo=PurePath(archivo.name).name[:255],
        total_registros=previsualizacion["total_registros"],
        registros_exitosos=exitosos,
        registros_fallidos=fallidos,
        detalles_error=json.dumps(
            {
                "validas": validas_aplicadas,
                "duplicadas": [
                    {
                        "fila": item["fila"],
                        "motivo": item["motivo"],
                        "categoria": item["datos"]["categoria"],
                        "pregunta": item["datos"]["enunciado"],
                    }
                    for item in previsualizacion["duplicadas"]
                ],
                "errores": errores,
            },
            ensure_ascii=False,
        ),
        estado_resultado=resultado,
    )
    previsualizacion["errores"] = errores
    previsualizacion["preguntas_agregadas_cuestionario"] = (
        preguntas_agregadas_cuestionario
    )
    return importacion, previsualizacion


def _normalizar_tipo(valor):
    texto = str(valor or "").strip().casefold()
    if texto in {"multiple", "multiple option", "seleccion multiple", "selección múltiple"}:
        return TipoPregunta.MULTIPLE
    if texto in {
        "verdadero_falso",
        "verdadero/falso",
        "verdadero o falso",
        "true/false",
    }:
        return TipoPregunta.VERDADERO_FALSO
    raise ValueError("tipo debe ser MULTIPLE o VERDADERO_FALSO")


def _leer_opciones(fila, tipo):
    opciones = []
    for numero in range(1, 5):
        texto = fila.get(f"opcion_{numero}")
        if texto is not None and str(texto).strip():
            opciones.append((numero, str(texto).strip()))
    if len(opciones) < 2:
        raise ValueError("se requieren al menos dos opciones")
    if tipo == TipoPregunta.VERDADERO_FALSO and len(opciones) != 2:
        raise ValueError("verdadero/falso requiere exactamente dos opciones")

    valor_correcto = fila.get("respuesta_correcta")
    correcta = str(valor_correcto or "").strip()
    if (
        isinstance(valor_correcto, (int, float))
        and not isinstance(valor_correcto, bool)
        and float(valor_correcto).is_integer()
    ):
        numero_correcto = int(valor_correcto)
    elif correcta.isdigit():
        numero_correcto = int(correcta)
    else:
        numero_correcto = None
    if numero_correcto is not None:
        if numero_correcto not in {numero for numero, _ in opciones}:
            raise ValueError("respuesta_correcta debe indicar una opción existente")
    else:
        coincidencias = [
            numero
            for numero, texto in opciones
            if texto.casefold() == correcta.casefold()
        ]
        if len(coincidencias) != 1:
            raise ValueError(
                "respuesta_correcta debe ser el número de opción o su texto exacto"
            )
        numero_correcto = coincidencias[0]

    return [
        {
            "texto_opcion": texto,
            "es_correcta": numero == numero_correcto,
            "retroalimentacion": None,
        }
        for numero, texto in opciones
    ]


def _crear_fila(fila, usuario, cuestionario=None):
    categoria_nombre = str(fila.get("categoria") or "").strip()
    enunciado = str(fila.get("enunciado") or "").strip()
    if not categoria_nombre:
        raise ValueError("categoria es obligatoria")
    if not enunciado:
        raise ValueError("enunciado es obligatorio")
    tipo = _normalizar_tipo(fila.get("tipo"))
    try:
        puntaje = Decimal(str(fila.get("puntaje") or "1"))
    except InvalidOperation as error:
        raise ValueError("puntaje debe ser un número decimal") from error
    try:
        precision_valida = puntaje == puntaje.quantize(Decimal("0.01"))
    except InvalidOperation:
        precision_valida = False
    if (
        not puntaje.is_finite()
        or puntaje <= 0
        or puntaje > Decimal("999.99")
        or not precision_valida
    ):
        raise ValueError("puntaje debe ser mayor que 0 y no superar 999.99")
    if len(categoria_nombre) > 100:
        raise ValueError("categoria no puede superar 100 caracteres")

    opciones = _leer_opciones(fila, tipo)
    with transaction.atomic():
        categoria = Categoria.objects.filter(
            nombre__iexact=categoria_nombre
        ).first()
        if categoria is None:
            categoria = Categoria.objects.create(
                nombre=categoria_nombre,
                estado=EstadoContenido.ACTIVO,
            )
        if categoria.estado != EstadoContenido.ACTIVO:
            raise ValueError("la categoría indicada está inactiva")
        pregunta = Pregunta.objects.create(
            categoria=categoria,
            tipo=tipo,
            texto_base=str(fila.get("texto_base") or "").strip() or None,
            enunciado=enunciado,
            retroalimentacion=str(
                fila.get("retroalimentacion") or ""
            ).strip()
            or None,
            puntaje=puntaje,
            creado_por=usuario,
        )
        OpcionRespuesta.objects.bulk_create(
            [OpcionRespuesta(pregunta=pregunta, **opcion) for opcion in opciones]
        )
        if cuestionario is not None:
            from apps.quizzes.models import CuestionarioPregunta

            puntaje_actual = sum(
                CuestionarioPregunta.objects.filter(
                    cuestionario=cuestionario
                ).values_list("puntaje", flat=True),
                Decimal("0"),
            )
            if puntaje_actual + puntaje > Decimal("999.99"):
                raise ValueError(
                    "el puntaje total del cuestionario no puede superar 999.99"
                )
            ultimo_orden = (
                CuestionarioPregunta.objects.filter(cuestionario=cuestionario)
                .order_by("-orden")
                .values_list("orden", flat=True)
                .first()
                or 0
            )
            CuestionarioPregunta.objects.create(
                cuestionario=cuestionario,
                pregunta=pregunta,
                orden=ultimo_orden + 1,
                puntaje=puntaje,
            )


def importar_preguntas_excel(*, archivo, usuario, cuestionario=None):
    if PurePath(archivo.name).suffix.casefold() != ".xlsx":
        raise ValidationError("El archivo debe tener formato .xlsx.")
    if archivo.size > TAMANO_MAXIMO_ARCHIVO:
        raise ValidationError("El archivo no puede superar los 10 MB.")
    try:
        libro = load_workbook(archivo, read_only=True, data_only=True)
    except (
        InvalidFileException,
        BadZipFile,
        OSError,
        ValueError,
        KeyError,
        ParseError,
    ) as error:
        raise ValidationError(
            "No se pudo leer el Excel. Verifica que sea un archivo .xlsx válido."
        ) from error

    hoja = libro.active
    if hoja is None:
        libro.close()
        raise ValidationError("El archivo no contiene una hoja de cálculo activa.")
    iterador = hoja.iter_rows(values_only=True)
    encabezados_originales = next(iterador, None)
    if not encabezados_originales:
        libro.close()
        raise ValidationError("El archivo no contiene una fila de encabezados.")
    encabezados = [
        str(valor or "").strip().casefold().replace(" ", "_")
        for valor in encabezados_originales
    ]
    faltantes = ENCABEZADOS_OBLIGATORIOS - set(encabezados)
    if faltantes:
        libro.close()
        raise ValidationError(
            {
                "archivo": (
                    "Faltan columnas obligatorias: "
                    + ", ".join(sorted(faltantes))
                )
            }
        )

    importacion = Importacion.objects.create(
        usuario=usuario,
        cuestionario=cuestionario,
        nombre_archivo=PurePath(archivo.name).name[:255],
        estado_resultado="En proceso",
    )
    errores = []
    exitosos = 0
    total = 0
    try:
        for numero_fila, valores in enumerate(iterador, start=2):
            if not any(valor is not None and str(valor).strip() for valor in valores):
                continue
            total += 1
            fila = dict(zip(encabezados, valores))
            try:
                _crear_fila(fila, usuario, cuestionario)
                exitosos += 1
            except (ValueError, TypeError, DataError, IntegrityError) as error:
                errores.append({"fila": numero_fila, "error": str(error)})
    finally:
        libro.close()

    importacion.total_registros = total
    importacion.registros_exitosos = exitosos
    importacion.registros_fallidos = total - exitosos
    importacion.detalles_error = json.dumps(
        errores,
        ensure_ascii=False,
    ) if errores else None
    importacion.estado_resultado = (
        "Exitoso"
        if not errores
        else "Parcial"
        if exitosos
        else "Fallido"
    )
    importacion.save(
        update_fields=[
            "total_registros",
            "registros_exitosos",
            "registros_fallidos",
            "detalles_error",
            "estado_resultado",
        ]
    )
    return importacion
