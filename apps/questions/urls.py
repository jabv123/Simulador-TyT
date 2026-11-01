"""Rutas del banco de preguntas."""

from django.urls import path

from .views import (
    DetalleCategoriaView,
    DetallePreguntaView,
    ListaCategoriasView,
    ListaPreguntasView,
)

app_name = "questions"

urlpatterns = [
    path("categorias/", ListaCategoriasView.as_view(), name="categorias"),
    path("categorias/<int:pk>/", DetalleCategoriaView.as_view(), name="categoria-detalle"),
    path("preguntas/", ListaPreguntasView.as_view(), name="preguntas"),
    path("preguntas/<int:pk>/", DetallePreguntaView.as_view(), name="pregunta-detalle"),
]
