from django.db import migrations


PERMISOS_BASE = [
    ("USUARIOS", "GESTIONAR", "Crear, editar y desactivar usuarios"),
    ("ROLES", "GESTIONAR", "Administrar roles y permisos"),
    ("CONFIGURACION", "EDITAR", "Modificar la configuración general"),
    ("CATEGORIAS", "GESTIONAR", "Administrar categorías"),
    ("PREGUNTAS", "GESTIONAR", "Gestionar el banco de preguntas"),
    ("IMPORTACION", "IMPORTAR", "Importar preguntas desde Excel"),
    ("CUESTIONARIOS", "GESTIONAR", "Crear y configurar cuestionarios"),
    ("CUESTIONARIOS", "PRESENTAR", "Presentar cuestionarios disponibles"),
    ("RESULTADOS", "VER", "Consultar resultados"),
    ("PERFIL", "EDITAR", "Editar el perfil personal"),
]


def crear_catalogo_permisos(apps, schema_editor):
    Permiso = apps.get_model("accounts", "Permiso")
    Rol = apps.get_model("accounts", "Rol")
    RolPermiso = apps.get_model("accounts", "RolPermiso")
    db = schema_editor.connection.alias

    catalogo = {}
    for modulo, accion, descripcion in PERMISOS_BASE:
        permiso, _ = Permiso.objects.using(db).get_or_create(
            modulo=modulo,
            accion=accion,
            defaults={"descripcion": descripcion},
        )
        catalogo[(modulo, accion)] = permiso

    asignaciones = {
        "Administrador": [
            ((modulo, accion), "TODOS")
            for modulo, accion, _ in PERMISOS_BASE
        ],
        "Estudiante": [
            (("CUESTIONARIOS", "PRESENTAR"), "PROPIOS"),
            (("RESULTADOS", "VER"), "PROPIOS"),
            (("PERFIL", "EDITAR"), "PROPIOS"),
        ],
        "Docente": [
            (("CATEGORIAS", "GESTIONAR"), "TODOS"),
            (("PREGUNTAS", "GESTIONAR"), "TODOS"),
            (("IMPORTACION", "IMPORTAR"), "TODOS"),
            (("CUESTIONARIOS", "GESTIONAR"), "A_SU_CARGO"),
            (("RESULTADOS", "VER"), "A_SU_CARGO"),
            (("PERFIL", "EDITAR"), "PROPIOS"),
        ],
    }

    for nombre_rol, permisos in asignaciones.items():
        rol = Rol.objects.using(db).filter(nombre__iexact=nombre_rol).first()
        if rol is None:
            continue
        for clave, alcance in permisos:
            permiso = catalogo[clave]
            filtro = {"rol_id": rol.pk, "permiso_id": permiso.pk}
            if not RolPermiso.objects.using(db).filter(**filtro).exists():
                RolPermiso.objects.using(db).create(
                    **filtro,
                    alcance=alcance,
                )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_roles_predeterminados"),
    ]

    operations = [
        migrations.RunPython(
            crear_catalogo_permisos,
            migrations.RunPython.noop,
        ),
    ]
