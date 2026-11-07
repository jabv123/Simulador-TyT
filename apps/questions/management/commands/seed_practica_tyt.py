"""Carga preguntas y resultados ficticios para prácticas tecnológicas TyT."""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import CursoAcademico, Estado, Grupo, Rol, Usuario
from apps.attempts.models import EstadoIntento, Intento, RespuestaIntento
from apps.questions.models import (
    Categoria,
    EstadoContenido,
    OpcionRespuesta,
    Pregunta,
    TipoPregunta,
)
from apps.questions.services import normalizar_texto
from apps.quizzes.models import (
    Cuestionario,
    CuestionarioPregunta,
    EstadoCuestionario,
)


PUNTAJE_PREGUNTA = Decimal("0.50")
CALIFICACION_MAXIMA = Decimal("5.00")
CALIFICACION_APROBACION = Decimal("3.00")

PREGUNTAS = {
    "Lectura crítica": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Un instituto instaló puntos de acceso inalámbrico en sus "
                "edificios. El informe indica que la conexión mejoró en las "
                "aulas, aunque algunos laboratorios siguen teniendo zonas sin "
                "cobertura."
            ),
            "enunciado": "¿Cuál conclusión está respaldada por el informe?",
            "opciones": [
                ("La conexión mejoró en las aulas, pero persisten problemas localizados.", True),
                ("Todos los espacios del instituto tienen cobertura completa.", False),
                ("La instalación redujo el número de edificios del instituto.", False),
                ("Los laboratorios ya no necesitan conexión inalámbrica.", False),
            ],
            "retroalimentacion": (
                "El texto informa una mejora en las aulas y señala que aún hay "
                "zonas sin cobertura en algunos laboratorios."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Una guía digital para resolver fallas frecuentes se publicó "
                "en el portal estudiantil. El mes siguiente disminuyeron los "
                "tickets de soporte, pero la encuesta solo incluyó a quienes "
                "consultaron la guía."
            ),
            "enunciado": "¿Qué limitación debe tenerse en cuenta al interpretar el resultado?",
            "opciones": [
                ("La encuesta puede no representar a quienes no consultaron la guía.", True),
                ("La disminución de tickets demuestra que toda falla fue resuelta.", False),
                ("La guía necesariamente causó la reducción observada.", False),
                ("Los tickets de soporte no sirven para describir incidencias.", False),
            ],
            "retroalimentacion": (
                "La muestra incluye solo usuarios de la guía y puede no "
                "representar a toda la comunidad."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Un equipo comparó dos propuestas para renovar la sala de "
                "cómputo. Una mejora la seguridad de los equipos y otra "
                "facilita el acceso a las herramientas."
            ),
            "enunciado": "¿Qué planteamiento integra mejor las dos propuestas?",
            "opciones": [
                ("La renovación debe combinar seguridad y facilidad de acceso.", True),
                ("La seguridad vuelve innecesario facilitar el acceso.", False),
                ("El acceso sencillo garantiza por sí solo la seguridad.", False),
                ("Las dos propuestas no pueden aplicarse en una misma sala.", False),
            ],
            "retroalimentacion": (
                "La información presenta seguridad y facilidad de acceso como "
                "objetivos complementarios."
            ),
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "texto_base": (
                "Después de una campaña de mantenimiento se reportaron menos "
                "incidentes en la red."
            ),
            "enunciado": "La coincidencia temporal, por sí sola, demuestra que la campaña causó la reducción.",
            "opciones": [
                ("Verdadero", False),
                ("Falso", True),
            ],
            "retroalimentacion": (
                "La coincidencia temporal no prueba causalidad; también deben "
                "considerarse otros factores y evidencia."
            ),
        },
    ],
    "Razonamiento cuantitativo": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Un archivo de instalación ocupa 240 megabytes. Una conexión "
                "transfiere datos a 60 megabits por segundo. Ignora la "
                "sobrecarga de red y usa 8 bits por byte."
            ),
            "enunciado": "¿Cuánto tardaría aproximadamente la descarga?",
            "opciones": [
                ("32 segundos", True),
                ("4 segundos", False),
                ("8 segundos", False),
                ("240 segundos", False),
            ],
            "retroalimentacion": (
                "60 megabits por segundo equivalen a 7,5 megabytes por "
                "segundo; 240 dividido entre 7,5 es 32."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Una plataforma recibió 600 solicitudes de servicio durante "
                "una semana. El equipo resolvió 480 dentro del plazo acordado."
            ),
            "enunciado": "¿Qué porcentaje de las solicitudes se resolvió dentro del plazo?",
            "opciones": [
                ("80 %", True),
                ("20 %", False),
                ("60 %", False),
                ("125 %", False),
            ],
            "retroalimentacion": (
                "480 dividido entre 600 es 0,8; expresado como porcentaje "
                "corresponde a 80 %."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Tres laboratorios comparten 45 computadores en partes "
                "iguales. Se conservará la misma proporción al habilitar "
                "otros laboratorios."
            ),
            "enunciado": "¿Cuántos computadores se requieren para seis laboratorios?",
            "opciones": [
                ("90 computadores", True),
                ("60 computadores", False),
                ("75 computadores", False),
                ("135 computadores", False),
            ],
            "retroalimentacion": (
                "Cada laboratorio recibe 15 computadores; seis laboratorios "
                "requieren 6 × 15 = 90."
            ),
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "texto_base": (
                "El precio de una licencia educativa es de 200.000 pesos y "
                "recibe un descuento del 15 %."
            ),
            "enunciado": "Después del descuento, el precio de la licencia es 170.000 pesos.",
            "opciones": [
                ("Verdadero", True),
                ("Falso", False),
            ],
            "retroalimentacion": (
                "El 15 % de 200.000 es 30.000; el precio final es 170.000."
            ),
        },
    ],
    "Competencias ciudadanas": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Un grupo estudiantil desarrolla una aplicación para coordinar "
                "actividades. La aplicación almacena datos de contacto y "
                "documentos de trabajo."
            ),
            "enunciado": "¿Qué decisión aplica mejor el principio de acceso mínimo necesario?",
            "opciones": [
                ("Dar a cada integrante solo los permisos que necesita para su tarea.", True),
                ("Compartir la contraseña de administración con todo el grupo.", False),
                ("Publicar los documentos para evitar solicitudes de acceso.", False),
                ("Mantener todas las cuentas activas aunque ya no se usen.", False),
            ],
            "retroalimentacion": (
                "Limitar permisos a las necesidades de cada función reduce "
                "riesgos y protege la información."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "En un foro universitario se discute la instalación de cámaras "
                "en zonas comunes. Hay opiniones distintas sobre seguridad y "
                "privacidad."
            ),
            "enunciado": "¿Cuál es la forma más constructiva de participar en el debate?",
            "opciones": [
                ("Presentar razones verificables y considerar los derechos involucrados.", True),
                ("Descalificar a quienes sostienen una opinión diferente.", False),
                ("Difundir rumores para convencer a los demás.", False),
                ("Impedir que las personas afectadas expresen su posición.", False),
            ],
            "retroalimentacion": (
                "La deliberación democrática requiere argumentos, respeto y "
                "consideración de los derechos de las personas."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Una institución publica materiales de formación en una "
                "plataforma virtual usada desde computadores y teléfonos."
            ),
            "enunciado": "¿Qué mejora favorece más la participación de personas con distintas necesidades de acceso?",
            "opciones": [
                ("Incluir navegación por teclado, subtítulos y textos alternativos.", True),
                ("Usar instrucciones que dependan solo de colores.", False),
                ("Publicar los contenidos únicamente como imágenes escaneadas.", False),
                ("Reducir el contraste para que todas las páginas se vean iguales.", False),
            ],
            "retroalimentacion": (
                "Las alternativas de navegación y representación hacen los "
                "materiales más accesibles a distintas personas."
            ),
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "texto_base": (
                "Una estudiante encuentra una falla y quiere enviar un reporte "
                "al equipo de soporte."
            ),
            "enunciado": "Adjuntar capturas con datos privados visibles es una práctica adecuada de protección de datos.",
            "opciones": [
                ("Verdadero", False),
                ("Falso", True),
            ],
            "retroalimentacion": (
                "Antes de compartir capturas deben ocultarse los datos "
                "personales o sensibles que no sean necesarios."
            ),
        },
    ],
    "Inglés": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "A technician describes the lab's routine maintenance schedule."
            ),
            "enunciado": "Choose the correct option: “The lab ___ new routers every semester.”",
            "opciones": [
                ("installs", True),
                ("install", False),
                ("installing", False),
                ("installed every", False),
            ],
            "retroalimentacion": (
                "The singular subject “The lab” takes “installs” in the simple present."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "A message appears before a computer system update."
            ),
            "enunciado": "What does “Please back up your files before the update” mean?",
            "opciones": [
                ("Save a copy of the files before updating.", True),
                ("Delete the files after the update.", False),
                ("Send the files to every user.", False),
                ("Turn off the computer permanently.", False),
            ],
            "retroalimentacion": (
                "“Back up” means to make a copy so the files can be recovered."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Maya checked the network logs, found repeated login failures "
                "for one account, and asked the administrator to reset it."
            ),
            "enunciado": "Why did Maya ask the administrator to reset the account?",
            "opciones": [
                ("Because the logs showed repeated login failures.", True),
                ("Because the network had no users.", False),
                ("Because she wanted to delete the logs.", False),
                ("Because the computer was being replaced.", False),
            ],
            "retroalimentacion": (
                "The passage directly connects the reset request with repeated "
                "login failures."
            ),
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "texto_base": (
                "A student has completed a report and submitted it to the "
                "course platform."
            ),
            "enunciado": "In “The students have submitted the report,” the action is complete and relevant now.",
            "opciones": [
                ("Verdadero", True),
                ("Falso", False),
            ],
            "retroalimentacion": (
                "The present perfect describes a completed action with "
                "relevance to the present."
            ),
        },
    ],
    "Comunicación escrita": [
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Un estudiante necesita informar a soporte que no puede "
                "ingresar al aula virtual desde su computador."
            ),
            "enunciado": "¿Cuál mensaje facilita mejor la atención de la solicitud?",
            "opciones": [
                ("Indicar el error observado, el momento y el navegador utilizado.", True),
                ("Escribir solamente “no funciona” sin más detalles.", False),
                ("Enviar la contraseña para que soporte pruebe el acceso.", False),
                ("Reenviar el mensaje a toda la institución sin contexto.", False),
            ],
            "retroalimentacion": (
                "Un reporte claro aporta detalles útiles y evita divulgar "
                "credenciales."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Una estudiante describe que el servidor perdió conexión y "
                "luego explica qué hizo el equipo técnico."
            ),
            "enunciado": "¿Qué conector expresa mejor que la segunda acción fue consecuencia de la falla?",
            "opciones": [
                ("Por lo tanto", True),
                ("A pesar de", False),
                ("En cambio", False),
                ("Por ejemplo", False),
            ],
            "retroalimentacion": (
                "“Por lo tanto” introduce una consecuencia derivada de la "
                "situación descrita."
            ),
        },
        {
            "tipo": TipoPregunta.MULTIPLE,
            "texto_base": (
                "Un informe técnico explica con palabras propias una idea "
                "consultada en un artículo especializado."
            ),
            "enunciado": "¿Qué debe hacer quien redacta el informe para reconocer la fuente?",
            "opciones": [
                ("Citar la fuente aunque haya expresado la idea con otras palabras.", True),
                ("Omitir la referencia porque no usó una cita textual.", False),
                ("Presentar la idea como resultado de su propio experimento.", False),
                ("Agregar una fuente que no haya consultado.", False),
            ],
            "retroalimentacion": (
                "La paráfrasis también requiere reconocer la fuente de la idea."
            ),
        },
        {
            "tipo": TipoPregunta.VERDADERO_FALSO,
            "texto_base": (
                "Una guía explica cómo reportar una falla en una plataforma "
                "académica."
            ),
            "enunciado": "Identificar con claridad quién realiza cada paso puede evitar instrucciones ambiguas.",
            "opciones": [
                ("Verdadero", True),
                ("Falso", False),
            ],
            "retroalimentacion": (
                "Los sujetos explícitos ayudan a comprender quién debe "
                "realizar cada acción."
            ),
        },
    ],
}

SEMESTRES = (
    {
        "nombre": "Práctica tecnológica TyT - Semestre I 2026",
        "fecha_apertura": datetime(2026, 3, 10, 9, 0),
        "fecha_cierre": datetime(2026, 6, 30, 18, 0),
        "estado": EstadoCuestionario.CERRADO,
        "fechas_intento": (datetime(2026, 4, 12, 10, 0), datetime(2026, 5, 8, 11, 0)),
        "aciertos": (8, 5),
    },
    {
        "nombre": "Práctica tecnológica TyT - Semestre II 2026",
        "fecha_apertura": datetime(2026, 9, 10, 9, 0),
        "fecha_cierre": datetime(2026, 12, 20, 18, 0),
        "estado": EstadoCuestionario.DISPONIBLE,
        "fechas_intento": (datetime(2026, 10, 12, 10, 0), datetime(2026, 10, 20, 11, 0)),
        "aciertos": (7, 10),
    },
)

ESTUDIANTES = (
    {
        "codigo": "PRACTICA-TYT-01",
        "correo": "practica.tyt.01@example.test",
        "nombre": "Practicante TyT Uno",
        "grupo": "Práctica tecnológica A",
    },
    {
        "codigo": "PRACTICA-TYT-02",
        "correo": "practica.tyt.02@example.test",
        "nombre": "Practicante TyT Dos",
        "grupo": "Práctica tecnológica B",
    },
)


def _verificar_base_local():
    if connection.vendor == "sqlite":
        nombre = connection.settings_dict["NAME"]
        if nombre != ":memory:" and not nombre.startswith("file:memorydb"):
            raise CommandError("Este comando solo puede ejecutarse en una base local o de pruebas en memoria.")
        return
    if connection.vendor != "mysql" or connection.settings_dict.get("HOST", "").lower() not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise CommandError("Este comando solo puede ejecutarse contra MariaDB/MySQL local.")


def _obtener_categoria(nombre):
    normalizado = normalizar_texto(nombre)
    for categoria in Categoria.objects.all():
        if normalizar_texto(categoria.nombre) == normalizado:
            return categoria
    return None


def _obtener_administrador():
    return (
        Usuario.objects.filter(
            estado=Estado.ACTIVO,
            rol__estado=Estado.ACTIVO,
            rol__nombre__iexact="Administrador",
        )
        .select_related("rol")
        .order_by("id")
        .first()
    )


def _obtener_o_crear_estudiantes(curso):
    rol, _ = Rol.objects.get_or_create(
        nombre="Estudiante",
        defaults={"estado": Estado.ACTIVO},
    )
    if rol.estado != Estado.ACTIVO:
        raise CommandError("El rol Estudiante está inactivo; no se crearán cuentas de práctica.")

    estudiantes = []
    for datos in ESTUDIANTES:
        usuario = Usuario.objects.filter(codigo=datos["codigo"]).first()
        if usuario is None:
            grupo, _ = Grupo.objects.get_or_create(
                curso=curso,
                nombre=datos["grupo"],
                defaults={"estado": Estado.ACTIVO},
            )
            if grupo.estado != Estado.ACTIVO:
                raise CommandError(
                    f"El grupo {grupo.nombre!r} existe inactivo; no se modificó."
                )
            usuario = Usuario(
                codigo=datos["codigo"],
                correo=datos["correo"],
                nombre=datos["nombre"],
                rol=rol,
                grupo=grupo,
                estado=Estado.ACTIVO,
            )
            usuario.set_unusable_password()
            usuario.save()
        else:
            usuario = Usuario.objects.select_related("grupo__curso").get(
                pk=usuario.pk
            )
            if (
                usuario.rol_id != rol.pk
                or usuario.estado != Estado.ACTIVO
                or usuario.nombre != datos["nombre"]
                or usuario.correo != datos["correo"]
                or usuario.grupo is None
                or usuario.grupo.nombre != datos["grupo"]
                or usuario.grupo.curso_id != curso.pk
                or usuario.grupo.estado != Estado.ACTIVO
            ):
                raise CommandError(
                    f"El código {datos['codigo']} ya existe para una cuenta incompatible; "
                    "no se modificó."
                )
        estudiantes.append(usuario)
    return estudiantes


def _crear_preguntas(administrador, omitidas):
    preguntas_por_categoria = defaultdict(list)
    creadas = 0

    for nombre_categoria, plantillas in PREGUNTAS.items():
        categoria = _obtener_categoria(nombre_categoria)
        if categoria is None:
            categoria = Categoria.objects.create(
                nombre=nombre_categoria,
                estado=EstadoContenido.ACTIVO,
            )
        elif categoria.estado != EstadoContenido.ACTIVO:
            raise CommandError(
                f"La categoría {categoria.nombre!r} está inactiva; no se modificó."
            )

        existentes = {
            normalizar_texto(texto): pregunta
            for pregunta, texto in Pregunta.objects.filter(
                categoria=categoria
            ).values_list("id", "enunciado")
        }
        for plantilla in plantillas:
            clave = normalizar_texto(plantilla["enunciado"])
            existente_id = existentes.get(clave)
            if existente_id is not None:
                pregunta = Pregunta.objects.get(pk=existente_id)
                omitidas["preguntas"] += 1
                if pregunta.estado == EstadoContenido.ACTIVO:
                    preguntas_por_categoria[nombre_categoria].append(pregunta)
                continue

            pregunta = Pregunta.objects.create(
                categoria=categoria,
                tipo=plantilla["tipo"],
                texto_base=plantilla["texto_base"],
                enunciado=plantilla["enunciado"],
                retroalimentacion=plantilla["retroalimentacion"],
                puntaje=PUNTAJE_PREGUNTA,
                estado=EstadoContenido.ACTIVO,
                creado_por=administrador,
            )
            OpcionRespuesta.objects.bulk_create(
                [
                    OpcionRespuesta(
                        pregunta=pregunta,
                        texto_opcion=texto,
                        es_correcta=es_correcta,
                        retroalimentacion=(
                            plantilla["retroalimentacion"] if es_correcta else None
                        ),
                    )
                    for texto, es_correcta in plantilla["opciones"]
                ]
            )
            existentes[clave] = pregunta.pk
            preguntas_por_categoria[nombre_categoria].append(pregunta)
            creadas += 1

    if any(len(preguntas) != 4 for preguntas in preguntas_por_categoria.values()):
        raise CommandError(
            "No se encontraron cuatro preguntas activas por cada categoría; "
            "no se crearán cuestionarios incompletos."
        )
    return preguntas_por_categoria, creadas


def _crear_cuestionario(semestre, preguntas, docente, omitidas):
    cuestionario = Cuestionario.objects.filter(nombre=semestre["nombre"]).first()
    creado = cuestionario is None
    if creado:
        cuestionario = Cuestionario.objects.create(
            docente=docente,
            nombre=semestre["nombre"],
            descripcion=(
                "Evaluación ficticia de práctica para competencias tecnológicas "
                "de lectura, razonamiento, ciudadanía, inglés y comunicación."
            ),
            fecha_apertura=timezone.make_aware(semestre["fecha_apertura"]),
            fecha_cierre=timezone.make_aware(semestre["fecha_cierre"]),
            tiempo_limite_minutos=60,
            intentos_permitidos=1,
            calificacion_maxima=CALIFICACION_MAXIMA,
            calificacion_aprobacion=CALIFICACION_APROBACION,
            mezclar_preguntas=False,
            mezclar_respuestas=False,
            permitir_revision=True,
            estado=semestre["estado"],
        )
        CuestionarioPregunta.objects.bulk_create(
            [
                CuestionarioPregunta(
                    cuestionario=cuestionario,
                    pregunta=pregunta,
                    orden=orden,
                    puntaje=PUNTAJE_PREGUNTA,
                )
                for orden, pregunta in enumerate(preguntas, start=1)
            ]
        )
    else:
        esperadas = set(preguntas)
        existentes = set(cuestionario.preguntas.all())
        if existentes != esperadas:
            raise CommandError(
                f"Ya existe {semestre['nombre']!r} con preguntas diferentes; "
                "no se modificó."
            )
        omitidas["cuestionarios"] += 1
    return cuestionario, creado


def _crear_intentos(cuestionario, semestre, preguntas, estudiantes, omitidas):
    creados = 0
    preguntas = list(preguntas)
    total_puntos = PUNTAJE_PREGUNTA * len(preguntas)

    for indice_estudiante, (estudiante, aciertos) in enumerate(
        zip(estudiantes, semestre["aciertos"])
    ):
        intento, creado = Intento.objects.get_or_create(
            cuestionario=cuestionario,
            usuario=estudiante,
            numero_intento=1,
            defaults={
                "grupo_snapshot": estudiante.grupo,
                "curso_nombre_snapshot": estudiante.grupo.curso.nombre,
                "grupo_nombre_snapshot": estudiante.grupo.nombre,
                "fecha_fin": timezone.make_aware(
                    semestre["fechas_intento"][indice_estudiante]
                ),
                "duracion_segundos": 1800,
                "puntaje_obtenido": PUNTAJE_PREGUNTA * aciertos,
                "calificacion_final": (
                    PUNTAJE_PREGUNTA
                    * aciertos
                    / total_puntos
                    * CALIFICACION_MAXIMA
                ),
                "estado": EstadoIntento.FINALIZADO,
            },
        )
        if not creado:
            omitidas["intentos"] += 1
            continue

        fecha_inicio = timezone.make_aware(
            semestre["fechas_intento"][indice_estudiante]
        )
        fecha_fin = fecha_inicio + timedelta(minutes=30)
        Intento.objects.filter(pk=intento.pk).update(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        for indice_pregunta, pregunta in enumerate(preguntas):
            opciones = list(pregunta.opciones.all())
            correcta = next(opcion for opcion in opciones if opcion.es_correcta)
            seleccionada = (
                correcta
                if indice_pregunta < aciertos
                else next(opcion for opcion in opciones if not opcion.es_correcta)
            )
            RespuestaIntento.objects.create(
                intento=intento,
                pregunta=pregunta,
                opcion_seleccionada=seleccionada,
                es_correcta=seleccionada.es_correcta,
                puntaje_obtenido=(
                    PUNTAJE_PREGUNTA
                    if seleccionada.es_correcta
                    else Decimal("0.00")
                ),
            )
        creados += 1
    return creados


class Command(BaseCommand):
    help = "Carga 20 preguntas tecnológicas de práctica TyT y dos cuestionarios semestrales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra el alcance de la carga sin guardar cambios.",
        )

    def handle(self, *args, **options):
        _verificar_base_local()
        if options["dry_run"]:
            self.stdout.write(
                "Dry run: se evaluarían 20 preguntas, 2 cuestionarios y "
                "4 intentos con cuentas ficticias sin contraseña utilizable."
            )
            return

        omitidas = defaultdict(int)
        with transaction.atomic():
            administrador = _obtener_administrador()
            curso, curso_creado = CursoAcademico.objects.get_or_create(
                nombre="Tecnología aplicada 2026",
                defaults={"estado": Estado.ACTIVO},
            )
            if curso.estado != Estado.ACTIVO:
                raise CommandError(
                    "El curso académico de práctica existe inactivo; no se modificó."
                )

            estudiantes = _obtener_o_crear_estudiantes(curso)
            preguntas_por_categoria, preguntas_creadas = _crear_preguntas(
                administrador,
                omitidas,
            )
            listas_cuestionario = [
                preguntas_por_categoria[nombre][:2]
                for nombre in PREGUNTAS
            ]
            listas_cuestionario = [
                pregunta for lista in listas_cuestionario for pregunta in lista
            ], [
                pregunta
                for nombre in PREGUNTAS
                for pregunta in preguntas_por_categoria[nombre][2:]
            ]

            cuestionarios_creados = 0
            intentos_creados = 0
            for semestre, preguntas in zip(SEMESTRES, listas_cuestionario):
                cuestionario, creado = _crear_cuestionario(
                    semestre,
                    preguntas,
                    administrador,
                    omitidas,
                )
                cuestionarios_creados += int(creado)
                intentos_creados += _crear_intentos(
                    cuestionario,
                    semestre,
                    preguntas,
                    estudiantes,
                    omitidas,
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Carga completada: "
                f"preguntas creadas={preguntas_creadas}, "
                f"preguntas omitidas={omitidas['preguntas']}, "
                f"cuestionarios creados={cuestionarios_creados}, "
                f"cuestionarios omitidos={omitidas['cuestionarios']}, "
                f"intentos creados={intentos_creados}, "
                f"intentos omitidos={omitidas['intentos']}, "
                f"curso académico {'creado' if curso_creado else 'existente'}."
            )
        )
