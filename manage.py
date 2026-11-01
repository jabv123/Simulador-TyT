#!/usr/bin/env python
"""Utilidad de línea de comandos de Django."""

import os
import sys


def main():
    """Ejecuta los comandos administrativos."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saber_tyt.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. Verifica que las dependencias estén "
            "instaladas y que el entorno virtual esté activado."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
