"""Crea el administrador inicial usando credenciales locales de .env."""

import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.accounts.models import Estado, Rol, Usuario


class Command(BaseCommand):
    help = "Crea el administrador inicial leyendo las variables SEED_ADMIN_*."

    def handle(self, *args, **options):
        codigo = os.getenv("SEED_ADMIN_CODIGO", "").strip()
        correo = os.getenv("SEED_ADMIN_CORREO", "").strip()
        nombre = os.getenv("SEED_ADMIN_NOMBRE", "").strip()
        password = os.getenv("SEED_ADMIN_PASSWORD", "")
        faltantes = [
            variable
            for variable, valor in (
                ("SEED_ADMIN_CODIGO", codigo),
                ("SEED_ADMIN_CORREO", correo),
                ("SEED_ADMIN_NOMBRE", nombre),
                ("SEED_ADMIN_PASSWORD", password),
            )
            if not valor
        ]
        if faltantes:
            raise CommandError(
                "Configura estas variables en .env antes de ejecutar seed_admin: "
                + ", ".join(faltantes)
            )

        usuario_existente = Usuario.objects.filter(codigo=codigo).first()
        if usuario_existente:
            if usuario_existente.rol.nombre.casefold() not in {
                "administrador",
                "admin",
            }:
                raise CommandError(
                    "El código ya pertenece a una cuenta que no es administradora."
                )
            self.stdout.write(
                self.style.WARNING(
                    "El administrador indicado ya existe; no se cambió su contraseña."
                )
            )
            return

        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError(
                "La contraseña configurada no cumple los requisitos: "
                + " ".join(error.messages)
            ) from error

        try:
            with transaction.atomic():
                rol, _ = Rol.objects.get_or_create(
                    nombre="Administrador",
                    defaults={
                        "descripcion": "Administra el simulador y sus permisos.",
                        "estado": Estado.ACTIVO,
                    },
                )
                if rol.estado != Estado.ACTIVO:
                    raise CommandError(
                        "El rol Administrador está inactivo; actívalo antes de continuar."
                    )
                Usuario.objects.create_superuser(
                    codigo=codigo,
                    password=password,
                    correo=correo,
                    nombre=nombre,
                    rol=rol,
                    estado=Estado.ACTIVO,
                )
        except IntegrityError as error:
            raise CommandError(
                "No se pudo crear el administrador. Verifica que el correo y "
                "el código no estén registrados en otra cuenta."
            ) from error

        self.stdout.write(
            self.style.SUCCESS(
                "Administrador creado. Inicia sesión con el código configurado."
            )
        )
