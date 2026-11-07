from django.urls import path

from .views import (
    ApiFiltrosView,
    ExportarReporteView,
    ReportesApiView,
    ReportesTemplateView,
)

app_name = "reports"

urlpatterns = [
    path("", ReportesTemplateView.as_view(), name="home"),
    path("api/", ReportesApiView.as_view(), name="api"),
    path("api/periodos/", ApiFiltrosView.as_view(), {"tipo": "periodos"}, name="periodos"),
    path("api/cursos/", ApiFiltrosView.as_view(), {"tipo": "cursos"}, name="cursos"),
    path(
        "api/cursos-academicos/",
        ApiFiltrosView.as_view(),
        {"tipo": "cursos-academicos"},
        name="cursos-academicos",
    ),
    path("api/grupos/", ApiFiltrosView.as_view(), {"tipo": "grupos"}, name="grupos"),
    path("api/ejes/", ApiFiltrosView.as_view(), {"tipo": "ejes"}, name="ejes"),
    path("api/estudiantes/", ApiFiltrosView.as_view(), {"tipo": "estudiantes"}, name="estudiantes"),
    path("exportar/", ExportarReporteView.as_view(), name="exportar"),
]
