from django.db import migrations


PERMISOS = {
    "USUARIOS": {
        "VER": "Consultar usuarios",
        "CREAR": "Crear usuarios",
        "EDITAR": "Editar usuarios",
        "DESACTIVAR": "Desactivar o activar usuarios",
        "GESTIONAR": "Administrar usuarios",
    },
    "ROLES": {
        "VER": "Consultar roles y permisos",
        "CREAR": "Crear roles",
        "EDITAR": "Editar roles",
        "DESACTIVAR": "Desactivar roles",
        "ASIGNAR_PERMISOS": "Asignar permisos a los roles",
        "GESTIONAR": "Administrar roles y permisos",
    },
    "PREGUNTAS": {
        "VER": "Consultar el banco de preguntas",
        "CREAR": "Crear preguntas",
        "EDITAR": "Editar preguntas",
        "DESACTIVAR": "Desactivar o activar preguntas",
        "GESTIONAR": "Gestionar el banco de preguntas",
    },
    "CATEGORIAS": {
        "VER": "Consultar categorías",
        "CREAR": "Crear categorías",
        "EDITAR": "Editar categorías",
        "DESACTIVAR": "Desactivar o activar categorías",
        "GESTIONAR": "Administrar categorías",
    },
    "CUESTIONARIOS": {
        "VER": "Consultar cuestionarios propios o asignados",
        "CREAR": "Crear cuestionarios",
        "EDITAR": "Editar cuestionarios",
        "DESACTIVAR": "Cerrar o desactivar cuestionarios",
        "VER_DISPONIBLES": "Consultar cuestionarios disponibles",
        "PRESENTAR": "Presentar cuestionarios",
        "GESTIONAR": "Crear y configurar cuestionarios",
    },
    "IMPORTACIONES": {
        "VER": "Consultar el historial de importaciones",
        "IMPORTAR": "Importar preguntas desde Excel",
    },
    "RESULTADOS": {
        "VER": "Consultar resultados",
        "VER_PROPIA_NOTA": "Consultar la nota propia",
    },
    "INTENTOS": {
        "VER": "Consultar intentos",
        "CREAR": "Crear intentos",
        "EDITAR": "Editar respuestas de un intento",
        "DESACTIVAR": "Cancelar intentos",
        "INICIAR": "Iniciar un intento",
        "RESPONDER": "Guardar respuestas de un intento",
        "FINALIZAR": "Finalizar un intento",
        "VER_NOTA_PROPIA": "Consultar la nota propia del intento",
    },
    "CONFIGURACION": {
        "EDITAR": "Modificar la configuración general",
    },
    "PERFIL": {
        "EDITAR": "Editar el perfil personal",
    },
    "IMPORTACION": {
        "IMPORTAR": "Importar preguntas desde Excel (compatibilidad)",
    },
}

PERMISOS_ESTUDIANTE = {
    ("CUESTIONARIOS", "VER_DISPONIBLES"),
    ("INTENTOS", "INICIAR"),
    ("INTENTOS", "RESPONDER"),
    ("INTENTOS", "FINALIZAR"),
    ("INTENTOS", "VER_NOTA_PROPIA"),
    ("RESULTADOS", "VER_PROPIA_NOTA"),
}

PERMISOS_DOCENTE = {
    ("CATEGORIAS", accion)
    for accion in ("VER", "CREAR", "EDITAR", "DESACTIVAR", "GESTIONAR")
} | {
    ("PREGUNTAS", accion)
    for accion in ("VER", "CREAR", "EDITAR", "DESACTIVAR", "GESTIONAR")
} | {
    ("IMPORTACIONES", "VER"),
    ("IMPORTACIONES", "IMPORTAR"),
    ("IMPORTACION", "IMPORTAR"),
    ("CUESTIONARIOS", "VER"),
    ("CUESTIONARIOS", "CREAR"),
    ("CUESTIONARIOS", "EDITAR"),
    ("CUESTIONARIOS", "GESTIONAR"),
    ("RESULTADOS", "VER"),
    ("PERFIL", "EDITAR"),
}


def crear_catalogo_y_asignaciones(apps, schema_editor):
    Rol = apps.get_model("accounts", "Rol")
    Permiso = apps.get_model("accounts", "Permiso")
    RolPermiso = apps.get_model("accounts", "RolPermiso")
    db = schema_editor.connection.alias

    catalogo = {}
    for modulo, acciones in PERMISOS.items():
        for accion, descripcion in acciones.items():
            permiso, _ = Permiso.objects.using(db).get_or_create(
                modulo=modulo,
                accion=accion,
                defaults={"descripcion": descripcion},
            )
            catalogo[(modulo, accion)] = permiso

    rol_admin = Rol.objects.using(db).filter(
        nombre__iexact="Administrador"
    ).first()
    rol_estudiante = Rol.objects.using(db).filter(
        nombre__iexact="Estudiante"
    ).first()
    rol_docente = Rol.objects.using(db).filter(
        nombre__iexact="Docente"
    ).first()

    if rol_admin:
        for permiso in catalogo.values():
            RolPermiso.objects.using(db).update_or_create(
                rol_id=rol_admin.pk,
                permiso_id=permiso.pk,
                defaults={"alcance": "TODOS"},
            )

    if rol_estudiante:
        permitidos = [
            catalogo[clave]
            for clave in PERMISOS_ESTUDIANTE
        ]
        RolPermiso.objects.using(db).filter(
            rol_id=rol_estudiante.pk
        ).exclude(
            permiso_id__in=[permiso.pk for permiso in permitidos]
        ).delete()
        for permiso in permitidos:
            RolPermiso.objects.using(db).update_or_create(
                rol_id=rol_estudiante.pk,
                permiso_id=permiso.pk,
                defaults={"alcance": "PROPIOS"},
            )

    if rol_docente:
        for clave in PERMISOS_DOCENTE:
            permiso = catalogo[clave]
            alcance = (
                "A_SU_CARGO"
                if clave[0] in {"CUESTIONARIOS", "RESULTADOS"}
                else "TODOS"
            )
            RolPermiso.objects.using(db).update_or_create(
                rol_id=rol_docente.pk,
                permiso_id=permiso.pk,
                defaults={"alcance": alcance},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_catalogo_permisos"),
    ]

    operations = [
        migrations.RunPython(
            crear_catalogo_y_asignaciones,
            migrations.RunPython.noop,
        ),
    ]
