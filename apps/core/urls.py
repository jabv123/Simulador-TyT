"""Rutas para la configuración del sistema."""

from django.urls import path

from .views import ConfiguracionAdministracionView, ConfiguracionPublicaView

app_name = "core"

urlpatterns = [
    path("publica/", ConfiguracionPublicaView.as_view(), name="configuracion-publica"),
    path(
        "administracion/",
        ConfiguracionAdministracionView.as_view(),
        name="configuracion-administracion",
    ),
]
