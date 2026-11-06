from django.db import migrations


PERMISOS_REPORTE = {
    "REPORTES": {
        "VER": "Consultar consultas y reportes",
        "EXPORTAR": "Exportar reportes a Excel",
    },
}


def crear_permiso_reportes(apps, schema_editor):
    Permiso = apps.get_model("accounts", "Permiso")
    Rol = apps.get_model("accounts", "Rol")
    RolPermiso = apps.get_model("accounts", "RolPermiso")
    db = schema_editor.connection.alias

    catalogo = {}
    for modulo, acciones in PERMISOS_REPORTE.items():
        for accion, descripcion in acciones.items():
            permiso, _ = Permiso.objects.using(db).get_or_create(
                modulo=modulo,
                accion=accion,
                defaults={"descripcion": descripcion},
            )
            catalogo[(modulo, accion)] = permiso

    for nombre_rol in ["Administrador", "Docente"]:
        rol = Rol.objects.using(db).filter(nombre__iexact=nombre_rol).first()
        if rol is None:
            continue
        for modulo, accion in catalogo:
            RolPermiso.objects.using(db).update_or_create(
                rol_id=rol.pk,
                permiso_id=catalogo[(modulo, accion)].pk,
                defaults={"alcance": "TODOS"},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_permiso_idx_permisos_modulo_rol_idx_roles_estado_and_more"),
    ]

    operations = [
        migrations.RunPython(
            crear_permiso_reportes,
            migrations.RunPython.noop,
        ),
    ]
