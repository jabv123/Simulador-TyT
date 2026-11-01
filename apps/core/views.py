"""Consulta pública y administración de la configuración general."""

from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import NotFound
from django.views.generic import TemplateView

from apps.accounts.permissions import HasModulePermission

from .models import ConfiguracionSistema
from .serializers import ConfiguracionSistemaSerializer


class InicioView(TemplateView):
    template_name = "index.html"


class AccesoDenegadoView(TemplateView):
    template_name = "acceso_denegado.html"


class ConfiguracionPublicaView(generics.RetrieveAPIView):
    serializer_class = ConfiguracionSistemaSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        configuracion = ConfiguracionSistema.objects.first()
        if configuracion is None:
            raise NotFound("La configuración institucional aún no está definida.")
        return configuracion


class ConfiguracionAdministracionView(generics.RetrieveUpdateAPIView):
    serializer_class = ConfiguracionSistemaSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "retrieve": ("configuracion", "editar"),
        "update": ("configuracion", "editar"),
    }

    def get_object(self):
        configuracion = ConfiguracionSistema.objects.first()
        if configuracion is None:
            raise NotFound("La configuración institucional aún no está definida.")
        return configuracion
