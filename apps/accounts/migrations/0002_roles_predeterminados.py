from django.db import migrations


def crear_roles_predeterminados(apps, schema_editor):
    Rol = apps.get_model("accounts", "Rol")
    base_datos = schema_editor.connection.alias

    Rol.objects.using(base_datos).get_or_create(
        nombre="Administrador",
        defaults={
            "descripcion": "Rol administrador del sistema.",
            "estado": "ACTIVO",
        },
    )
    Rol.objects.using(base_datos).get_or_create(
        nombre="Estudiante",
        defaults={
            "descripcion": "Rol estudiante del sistema.",
            "estado": "ACTIVO",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            crear_roles_predeterminados,
            migrations.RunPython.noop,
        ),
    ]
