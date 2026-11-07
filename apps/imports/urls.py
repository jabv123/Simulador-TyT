"""Rutas de importación de preguntas."""

from django.urls import path

from .views import (
    ConfirmarImportacionView,
    ExportarHistorialImportacionesView,
    ImportarExcelView,
    ListaImportacionesView,
    PlantillaImportacionView,
    PrevisualizarImportacionView,
)

app_name = "imports"

urlpatterns = [
    path("plantilla/", PlantillaImportacionView.as_view(), name="plantilla"),
    path(
        "previsualizar/",
        PrevisualizarImportacionView.as_view(),
        name="previsualizar",
    ),
    path(
        "confirmar/",
        ConfirmarImportacionView.as_view(),
        name="confirmar",
    ),
    path("", ImportarExcelView.as_view(), name="importar"),
    path("historial/", ListaImportacionesView.as_view(), name="historial"),
    path(
        "historial/exportar/",
        ExportarHistorialImportacionesView.as_view(),
        name="historial-exportar",
    ),
]
