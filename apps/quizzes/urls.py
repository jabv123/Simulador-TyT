"""Rutas de cuestionarios."""

from django.urls import path

from .views import (
    CuestionariosDisponiblesView,
    CuestionarioPreguntaDetalleView,
    CuestionarioPreguntasView,
    DesactivarCuestionarioView,
    DetalleCuestionarioView,
    ListaCuestionariosView,
    PublicarCuestionarioView,
)

app_name = "quizzes"

urlpatterns = [
    path("", ListaCuestionariosView.as_view(), name="cuestionarios"),
    path("disponibles/", CuestionariosDisponiblesView.as_view(), name="disponibles"),
    path(
        "<int:pk>/preguntas/",
        CuestionarioPreguntasView.as_view(),
        name="cuestionario-preguntas",
    ),
    path(
        "<int:pk>/preguntas/<int:pregunta_id>/",
        CuestionarioPreguntaDetalleView.as_view(),
        name="cuestionario-pregunta-detalle",
    ),
    path(
        "<int:pk>/publicar/",
        PublicarCuestionarioView.as_view(),
        name="cuestionario-publicar",
    ),
    path(
        "<int:pk>/desactivar/",
        DesactivarCuestionarioView.as_view(),
        name="cuestionario-desactivar",
    ),
    path("<int:pk>/", DetalleCuestionarioView.as_view(), name="cuestionario-detalle"),
]
