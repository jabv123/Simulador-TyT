"""Rutas principales del proyecto."""

from django.contrib import admin
from django.urls import include, path

from apps.core.views import AccesoDenegadoView, InicioView
from apps.accounts.views_admin import (
    DetalleRolView,
    DetalleUsuarioView,
    ListaRolesView,
    ListaUsuariosView,
    PermisosAgrupadosView,
    PermisosRolView,
    EstadoUsuarioView,
    RestablecerContrasenaView,
)

urlpatterns = [
    path("", InicioView.as_view(), name="inicio"),
    path(
        "acceso-denegado/",
        AccesoDenegadoView.as_view(),
        name="acceso-denegado",
    ),
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/usuarios/", ListaUsuariosView.as_view(), name="usuarios"),
    path(
        "api/usuarios/<int:pk>/estado/",
        EstadoUsuarioView.as_view(),
        name="usuario-estado",
    ),
    path(
        "api/usuarios/<int:pk>/restablecer-contrasena/",
        RestablecerContrasenaView.as_view(),
        name="usuario-restablecer-contrasena",
    ),
    path(
        "api/usuarios/<int:pk>/",
        DetalleUsuarioView.as_view(),
        name="usuario-detalle",
    ),
    path("api/roles/permisos/", PermisosAgrupadosView.as_view(), name="roles-permisos"),
    path(
        "api/roles/<int:pk>/permisos/",
        PermisosRolView.as_view(),
        name="rol-permisos",
    ),
    path("api/roles/", ListaRolesView.as_view(), name="roles"),
    path("api/roles/<int:pk>/", DetalleRolView.as_view(), name="rol-detalle"),
    path("api/", include("apps.questions.urls")),
    path("api/cuestionarios/", include("apps.quizzes.urls")),
    path("api/", include("apps.attempts.urls")),
    path("api/importaciones/", include("apps.imports.urls")),
    path("api/configuracion/", include("apps.core.urls")),
]
