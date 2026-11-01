from django.db import migrations


def crear_configuracion_inicial(apps, schema_editor):
    ConfiguracionSistema = apps.get_model("core", "ConfiguracionSistema")
    db = schema_editor.connection.alias
    if not ConfiguracionSistema.objects.using(db).exists():
        ConfiguracionSistema.objects.using(db).create(
            nombre_sistema="Simulador de Pruebas Saber TyT",
            institucion="Institución educativa",
            zona_horaria="America/Bogota",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            crear_configuracion_inicial,
            migrations.RunPython.noop,
        ),
    ]
