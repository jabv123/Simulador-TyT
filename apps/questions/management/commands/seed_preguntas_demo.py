"""Sembrado de preguntas de demostración."""

import os
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Estado, Usuario
from apps.questions.models import (
    Categoria,
    EstadoContenido,
    OpcionRespuesta,
    Pregunta,
    TipoPregunta,
)
from apps.questions.services import normalizar_texto

CATEGORIAS_DEMO = {
    "Lectura crítica": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "En un texto argumentativo, la tesis suele aparecer como la idea central que orienta la evidencia presentada.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Depende del autor", "es_correcta": False},
                {"texto_opcion": "Solo en textos narrativos", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "La inferencia en lectura crítica consiste en deducir información no explícita a partir de pistas del texto.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Es una acción propia del resumen", "es_correcta": False},
                {"texto_opcion": "Solo aplica a textos técnicos", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "Un texto con argumentos sólidos debe evitar contradicciones internas entre sus premisas y conclusiones.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Solo si emplea citas", "es_correcta": False},
                {"texto_opcion": "No es obligatorio en la enseñanza", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "enunciado": "Si un autor presenta evidencia insuficiente, la conclusión puede perder credibilidad.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
            ],
        },
    ],
    "Razonamiento cuantitativo": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "Si una camiseta cuesta 80.000 pesos y tiene un descuento del 25 %, el precio final es 60.000 pesos.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Depende del tipo de descuento", "es_correcta": False},
                {"texto_opcion": "No se puede calcular sin IVA", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "La media aritmética de 12, 15, 18 y 21 es 16.5.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "16", "es_correcta": False},
                {"texto_opcion": "17", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "Si 3 máquinas producen 15 unidades en 2 horas, entonces 5 máquinas producirán 25 unidades en 2 horas.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Solo si trabajan el doble de tiempo", "es_correcta": False},
                {"texto_opcion": "No se puede inferir", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "enunciado": "Una razón es equivalente a una proporción cuando compara dos cantidades mediante una división.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
            ],
        },
    ],
    "Competencias ciudadanas": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "La participación ciudadana es un mecanismo clave para controlar la gestión pública y fortalecer la democracia.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Es opcional en los Estados democráticos", "es_correcta": False},
                {"texto_opcion": "Solo aplica a campañas electorales", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "El principio de igualdad ante la ley exige que todas las personas reciban el mismo trato sin discriminación arbitraria.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Solo para funcionarios públicos", "es_correcta": False},
                {"texto_opcion": "Solo en contextos judiciales", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "Un Estado democrático debe garantizar derechos fundamentales y mecanismos de participación para la ciudadanía.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Solo en periodos electorales", "es_correcta": False},
                {"texto_opcion": "Depende del tamaño del país", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "enunciado": "El conflicto de intereses puede afectar la imparcialidad de la acción pública.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
            ],
        },
    ],
    "Inglés": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "En la oración 'She has finished her assignment', el verbo principal está en presente perfecto.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Está en pasado simple", "es_correcta": False},
                {"texto_opcion": "Es un verbo modal", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "La frase 'I would like to travel next year' expresa un deseo o intención futura.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Expresa una orden", "es_correcta": False},
                {"texto_opcion": "Solo se usa en indicativo", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "El adjetivo 'careful' se utiliza para describir una persona que actúa con atención y precisión.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Describe solo objetos físicos", "es_correcta": False},
                {"texto_opcion": "Es un verbo en gerundio", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "enunciado": "En inglés, 'There are many students in the library' es una oración gramaticalmente correcta.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
            ],
        },
    ],
    "Comunicación escrita": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "La coherencia textual depende de la relación lógica entre las ideas y la continuidad del sentido.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Solo en textos narrativos", "es_correcta": False},
                {"texto_opcion": "No es relevante en la redacción", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "Un párrafo bien estructurado suele incluir una idea principal y argumentos o explicaciones que la desarrollen.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Solo cuando se usa un formato formal", "es_correcta": False},
                {"texto_opcion": "No puede incluir ejemplos", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "enunciado": "En una carta formal, el saludo debe ser claro, respetuoso y acorde con el destinatario.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
                {"texto_opcion": "Solo si el contenido es breve", "es_correcta": False},
                {"texto_opcion": "Depende del color de la carta", "es_correcta": False},
            ],
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "enunciado": "El uso de conectores adecuados facilita la comprensión y la organización del texto.",
            "opciones": [
                {"texto_opcion": "Verdadero", "es_correcta": True},
                {"texto_opcion": "Falso", "es_correcta": False},
            ],
        },
    ],
}

PREGUNTAS_DEMO = []
for indice in range(4):
    for categoria in [
        "Lectura crítica",
        "Razonamiento cuantitativo",
        "Competencias ciudadanas",
        "Inglés",
        "Comunicación escrita",
    ]:
        PREGUNTAS_DEMO.append({"categoria": categoria, **CATEGORIAS_DEMO[categoria][indice]})


def _obtener_categoria(nombre):
    normalizado = normalizar_texto(nombre)
    for categoria in Categoria.objects.all():
        if normalizar_texto(categoria.nombre) == normalizado:
            return categoria
    return None


def _seleccionar_plantillas(cantidad):
    limite = max(0, min(int(cantidad), len(PREGUNTAS_DEMO)))
    return PREGUNTAS_DEMO[:limite]


def _resolver_admin():
    codigo = (os.getenv("SEED_ADMIN_CODIGO") or "").strip()
    if codigo:
        usuario = (
            Usuario.objects.filter(codigo=codigo, estado=Estado.ACTIVO)
            .select_related("rol")
            .first()
        )
        if usuario and usuario.rol and usuario.rol.nombre.casefold() in {"administrador", "admin"}:
            return usuario

    return (
        Usuario.objects.filter(estado=Estado.ACTIVO)
        .filter(rol__nombre__iexact="Administrador")
        .select_related("rol")
        .order_by("id")
        .first()
    )


class Command(BaseCommand):
    help = "Crea un banco de preguntas de demostración con 20 registros válidos y reproducibles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cantidad",
            type=int,
            default=20,
            help="Número de preguntas a sembrar (por defecto 20).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué preguntas se crearían sin escribir en la base de datos.",
        )

    def handle(self, *args, **options):
        cantidad = int(options["cantidad"])
        if cantidad <= 0:
            raise CommandError("--cantidad debe ser un entero mayor que cero.")

        plantillas = _seleccionar_plantillas(cantidad)
        if not plantillas:
            raise CommandError("No hay preguntas de demostración disponibles.")

        admin = _resolver_admin()
        if admin is None:
            self.stdout.write(
                self.style.WARNING(
                    "No existe un usuario administrador activo; se dejará creado_por en null."
                )
            )

        creadas = 0
        omitidas = 0
        errores = 0

        if options["dry_run"]:
            for item in plantillas:
                categoria = _obtener_categoria(item["categoria"])
                if categoria is not None and categoria.estado != EstadoContenido.ACTIVO:
                    errores += 1
                    continue

                if categoria is not None:
                    clave = normalizar_texto(item["enunciado"])
                    ya_existe = any(
                        normalizar_texto(pregunta.enunciado) == clave
                        for pregunta in Pregunta.objects.filter(categoria=categoria)
                    )
                    if ya_existe:
                        omitidas += 1
                        continue

                self.stdout.write(
                    f"- {item['categoria']} | {item['tipo']} | {item['enunciado']}"
                )
                creadas += 1

            self.stdout.write(
                f"Preguntas creadas: {creadas} · omitidas por duplicado: {omitidas} · errores: {errores}"
            )
            return

        with transaction.atomic():
            for item in plantillas:
                categoria = _obtener_categoria(item["categoria"])
                if categoria is None:
                    categoria, _ = Categoria.objects.get_or_create(
                        nombre=item["categoria"],
                        defaults={"descripcion": "Categoría de demostración", "estado": EstadoContenido.ACTIVO},
                    )
                if categoria.estado != EstadoContenido.ACTIVO:
                    errores += 1
                    continue

                existe = any(
                    normalizar_texto(pregunta.enunciado) == normalizar_texto(item["enunciado"])
                    for pregunta in Pregunta.objects.filter(categoria=categoria)
                )
                if existe:
                    omitidas += 1
                    continue

                try:
                    pregunta = Pregunta.objects.create(
                        categoria=categoria,
                        tipo=item["tipo"],
                        enunciado=item["enunciado"],
                        puntaje=Decimal("1.00"),
                        estado=EstadoContenido.ACTIVO,
                        creado_por=admin,
                    )
                    OpcionRespuesta.objects.bulk_create(
                        [
                            OpcionRespuesta(
                                pregunta=pregunta,
                                texto_opcion=opcion["texto_opcion"],
                                es_correcta=bool(opcion["es_correcta"]),
                            )
                            for opcion in item["opciones"]
                        ]
                    )
                    creadas += 1
                except Exception:
                    errores += 1
                    raise

        self.stdout.write(
            f"Preguntas creadas: {creadas} · omitidas por duplicado: {omitidas} · errores: {errores}"
        )
