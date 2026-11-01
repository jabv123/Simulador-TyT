"""Rutas de autenticación y perfil."""

from django.urls import path

from .views import (
    CambiarContrasenaView,
    CerrarSesionView,
    PerfilUsuarioView,
    TokenAccesoView,
)
from .views_admin import (
    DetalleRolView,
    DetalleUsuarioView,
    EstadoUsuarioView,
    ListaPermisosView,
    ListaRolesView,
    ListaUsuariosView,
    RestablecerContrasenaView,
)
from .serializers import TokenRenovarSerializer
from rest_framework_simplejwt.views import TokenRefreshView

app_name = "accounts"

urlpatterns = [
    path("login/", TokenAccesoView.as_view(), name="login"),
    path("token/", TokenAccesoView.as_view(), name="token"),
    path(
        "refresh/",
        TokenRefreshView.as_view(serializer_class=TokenRenovarSerializer),
        name="refresh",
    ),
    path(
        "token/renovar/",
        TokenRefreshView.as_view(serializer_class=TokenRenovarSerializer),
        name="token-renovar",
    ),
    path("logout/", CerrarSesionView.as_view(), name="logout"),
    path("me/", PerfilUsuarioView.as_view(), name="me"),
    path("perfil/", PerfilUsuarioView.as_view(), name="perfil"),
    path("change-password/", CambiarContrasenaView.as_view(), name="change-password"),
    path("usuarios/", ListaUsuariosView.as_view(), name="usuarios"),
    path(
        "usuarios/<int:pk>/estado/",
        EstadoUsuarioView.as_view(),
        name="usuario-estado",
    ),
    path(
        "usuarios/<int:pk>/restablecer-contrasena/",
        RestablecerContrasenaView.as_view(),
        name="usuario-restablecer-contrasena",
    ),
    path("usuarios/<int:pk>/", DetalleUsuarioView.as_view(), name="usuario-detalle"),
    path("roles/", ListaRolesView.as_view(), name="roles"),
    path("roles/<int:pk>/", DetalleRolView.as_view(), name="rol-detalle"),
    path("permisos/", ListaPermisosView.as_view(), name="permisos"),
]
