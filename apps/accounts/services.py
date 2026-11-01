"""Operaciones transaccionales para administrar permisos de roles."""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Rol, RolPermiso


@transaction.atomic
def reemplazar_permisos_rol(rol, asignaciones):
    """Reemplaza el conjunto completo de permisos de un rol."""
    if not isinstance(rol, Rol):
        raise TypeError("El rol debe ser una instancia de Rol.")

    ids = [item["permiso"].pk for item in asignaciones]
    if len(ids) != len(set(ids)):
        raise ValidationError(
            {"permisos": "No repitas el mismo permiso en un rol."}
        )

    rol.permisos_configurados.all().delete()
    RolPermiso.objects.bulk_create(
        [
            RolPermiso(
                rol=rol,
                permiso=item["permiso"],
                alcance=item["alcance"],
            )
            for item in asignaciones
        ]
    )
