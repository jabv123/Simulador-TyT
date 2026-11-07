from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import Estado, Rol, Usuario
from apps.questions.models import Categoria, EstadoContenido, OpcionRespuesta, Pregunta, TipoPregunta


class SeedPreguntasDemoTests(TestCase):
    def setUp(self):
        rol, _ = Rol.objects.get_or_create(nombre="Administrador", defaults={"estado": Estado.ACTIVO})
        self.admin, created = Usuario.objects.get_or_create(
            codigo="ADMIN-1",
            defaults={
                "password": "dummy",
                "nombre": "Administrador",
                "correo": "admin@test.local",
                "rol": rol,
                "estado": Estado.ACTIVO,
            },
        )
        if created:
            self.admin.set_password("Admin-password-123")
            self.admin.save(update_fields=["password"])
        else:
            self.admin.estado = Estado.ACTIVO
            self.admin.rol = rol
            self.admin.save(update_fields=["estado", "rol"])

    def test_seed_preguntas_demo_crea_20_y_es_idempotente(self):
        call_command("seed_preguntas_demo", cantidad=20, verbosity=0)

        self.assertEqual(Pregunta.objects.count(), 20)
        self.assertEqual(Pregunta.objects.filter(estado=EstadoContenido.ACTIVO).count(), 20)
        self.assertEqual(Pregunta.objects.filter(creado_por=self.admin).count(), 20)
        self.assertEqual(Categoria.objects.count(), 5)
        self.assertEqual(OpcionRespuesta.objects.count(), 70)

        call_command("seed_preguntas_demo", cantidad=20, verbosity=0)
        self.assertEqual(Pregunta.objects.count(), 20)

    def test_seed_preguntas_demo_dry_run_no_escribe_y_muestra_20(self):
        call_command("seed_preguntas_demo", cantidad=20, dry_run=True, verbosity=0)
        self.assertEqual(Pregunta.objects.count(), 0)
        self.assertEqual(Categoria.objects.count(), 0)

    def test_seed_preguntas_demo_cantidad_3_reparte_equilibradamente(self):
        call_command("seed_preguntas_demo", cantidad=3, verbosity=0)

        self.assertEqual(Pregunta.objects.count(), 3)
        self.assertEqual(Pregunta.objects.values_list("categoria__nombre", flat=True).distinct().count(), 3)
        self.assertEqual(Pregunta.objects.filter(tipo=TipoPregunta.VERDADERO_FALSO).count(), 0)

    def test_seed_preguntas_demo_rechaza_cantidad_invalida(self):
        with self.assertRaisesMessage(CommandError, "--cantidad debe ser un entero mayor que cero."):
            call_command("seed_preguntas_demo", cantidad=0, verbosity=0)
