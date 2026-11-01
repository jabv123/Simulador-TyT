"""Rutas para presentación de cuestionarios e informes."""

from django.urls import path

from .views import (
    DetalleIntentoView,
    DetalleResultadoView,
    EnviarIntentoView,
    GuardarRespuestaView,
    IniciarIntentoView,
    ListaResultadosView,
    MisResultadosView,
)

app_name = "attempts"

urlpatterns = [
    path(
        "cuestionarios/<int:cuestionario_id>/intentos/iniciar/",
        IniciarIntentoView.as_view(),
        name="iniciar-intento-cuestionario",
    ),
    path(
        "cuestionarios/<int:cuestionario_id>/iniciar/",
        IniciarIntentoView.as_view(),
        name="iniciar",
    ),
    path(
        "intentos/mis-resultados/",
        MisResultadosView.as_view(),
        name="mis-resultados",
    ),
    path("intentos/<int:pk>/", DetalleIntentoView.as_view(), name="intento-detalle"),
    path(
        "intentos/<int:intento_id>/respuestas/",
        GuardarRespuestaView.as_view(),
        name="guardar-respuesta",
    ),
    path(
        "intentos/<int:intento_id>/finalizar/",
        EnviarIntentoView.as_view(),
        name="finalizar-intento",
    ),
    path(
        "intentos/<int:intento_id>/enviar/",
        EnviarIntentoView.as_view(),
        name="enviar-intento",
    ),
    path("resultados/", ListaResultadosView.as_view(), name="resultados"),
    path("resultados/<int:pk>/", DetalleResultadoView.as_view(), name="resultado-detalle"),
]
