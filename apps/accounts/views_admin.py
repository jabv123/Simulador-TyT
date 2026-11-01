"""Endpoints para la administración segura de cuentas y roles."""

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.filters import SearchFilter
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Estado, Permiso, Rol, Usuario
from .pagination import PaginacionUsuarios
from .permissions import (
    HasModulePermission,
    exigir_permiso,
    filtrar_por_alcance,
)
from .serializers_admin import (
    AsignacionPermisoSerializer,
    EstadoUsuarioSerializer,
    PermisoSerializer,
    RestablecerContrasenaSerializer,
    RolAdministracionSerializer,
    UsuarioAdministracionSerializer,
)
from .services import reemplazar_permisos_rol


class ListaUsuariosView(generics.ListCreateAPIView):
    serializer_class = UsuarioAdministracionSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    filter_backends = [SearchFilter]
    search_fields = ["nombre", "codigo", "correo", "telefono"]
    pagination_class = PaginacionUsuarios
    required_permissions = {
        "list": ("usuarios", "ver"),
        "create": ("usuarios", "crear"),
    }
    permiso_requerido = "USUARIOS.GESTIONAR"

    def get_queryset(self):
        queryset = filtrar_por_alcance(
            Usuario.objects.select_related("rol"),
            self.request.user,
            "USUARIOS.VER",
            None,
            request=self.request,
        )
        rol_id = self.request.query_params.get("rol")
        estado = self.request.query_params.get("estado")
        if rol_id:
            if not rol_id.isdecimal():
                raise ValidationError(
                    {"rol": "El filtro rol debe ser un identificador numérico."}
                )
            queryset = queryset.filter(rol_id=rol_id)
        if estado:
            if estado.upper() not in Estado.values:
                raise ValidationError(
                    {"estado": "El filtro estado debe ser ACTIVO o INACTIVO."}
                )
            queryset = queryset.filter(estado=estado.upper())
        return queryset


class DetalleUsuarioView(generics.RetrieveUpdateAPIView):
    serializer_class = UsuarioAdministracionSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "retrieve": ("usuarios", "ver"),
        "update": ("usuarios", "editar"),
    }
    permiso_requerido = "USUARIOS.GESTIONAR"

    def get_queryset(self):
        permiso = "USUARIOS.VER"
        return filtrar_por_alcance(
            Usuario.objects.select_related("rol"),
            self.request.user,
            permiso,
            None,
            request=self.request,
        )

    def perform_update(self, serializer):
        usuario = serializer.instance
        nuevo_rol = serializer.validated_data.get("rol", usuario.rol)
        if (
            usuario.pk == self.request.user.pk
            and usuario._es_administrador()
            and nuevo_rol.nombre.casefold() not in {"administrador", "admin"}
        ):
            raise ValidationError(
                {"rol": "No puedes quitarte tu propio rol de administrador."}
            )
        if (
            usuario._es_administrador()
            and nuevo_rol.nombre.casefold() not in {"administrador", "admin"}
            and not Usuario.objects.filter(
                rol__nombre__iexact="Administrador",
                estado=Estado.ACTIVO,
            ).exclude(pk=usuario.pk).exists()
        ):
            raise ValidationError(
                {"rol": "No puedes cambiar el rol del último administrador activo."}
            )
        if (
            usuario._es_administrador()
            and serializer.validated_data.get("estado", usuario.estado)
            != Estado.ACTIVO
        ):
            raise ValidationError(
                {"estado": "No se puede desactivar la cuenta administradora."}
            )
        serializer.save()


class EstadoUsuarioView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"patch": ("usuarios", "desactivar")}

    def patch(self, request, pk):
        usuario = get_object_or_404(Usuario.objects.select_related("rol"), pk=pk)
        entrada = EstadoUsuarioSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        nuevo_estado = entrada.validated_data["estado"]
        if (
            usuario.pk == request.user.pk
            and usuario._es_administrador()
            and nuevo_estado == Estado.INACTIVO
        ):
            raise ValidationError(
                {"estado": "No puedes desactivar tu propia cuenta administradora."}
            )
        if (
            usuario._es_administrador()
            and nuevo_estado == Estado.INACTIVO
            and not Usuario.objects.filter(
                rol__nombre__iexact="Administrador",
                rol__estado=Estado.ACTIVO,
                estado=Estado.ACTIVO,
            ).exclude(pk=usuario.pk).exists()
        ):
            raise ValidationError(
                {"estado": "No puedes desactivar al último administrador activo."}
            )
        usuario.estado = nuevo_estado
        usuario.save(update_fields=["estado"])
        return Response(UsuarioAdministracionSerializer(usuario).data)


class RestablecerContrasenaView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"post": ("usuarios", "editar")}

    def post(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        entrada = RestablecerContrasenaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        usuario.set_password(entrada.validated_data["password"])
        usuario.save(update_fields=["password"])
        return Response({"detail": "Contraseña restablecida correctamente."})


class ListaRolesView(generics.ListCreateAPIView):
    queryset = Rol.objects.prefetch_related("permisos_configurados__permiso")
    serializer_class = RolAdministracionSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "list": ("roles", "ver"),
        "create": ("roles", "crear"),
    }
    permiso_requerido = "ROLES.GESTIONAR"


class DetalleRolView(generics.RetrieveUpdateAPIView):
    queryset = Rol.objects.prefetch_related("permisos_configurados__permiso")
    serializer_class = RolAdministracionSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "retrieve": ("roles", "ver"),
        "update": ("roles", "editar"),
        "destroy": ("roles", "desactivar"),
    }
    permiso_requerido = "ROLES.GESTIONAR"

    def perform_update(self, serializer):
        nuevo_estado = serializer.validated_data.get(
            "estado",
            serializer.instance.estado,
        )
        if nuevo_estado != serializer.instance.estado:
            exigir_permiso(
                self.request,
                "ROLES",
                "DESACTIVAR",
                "No tienes permiso para activar o desactivar roles.",
            )
        serializer.save()

    def delete(self, _request, *_args, **_kwargs):
        rol = self.get_object()
        if rol.nombre.casefold() in {"administrador", "estudiante"}:
            raise ValidationError(
                "No se pueden eliminar los roles predeterminados."
            )
        if rol.usuarios.exists():
            raise ValidationError(
                "El rol tiene usuarios asignados; desactívalo en lugar de eliminarlo."
            )
        rol.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListaPermisosView(generics.ListAPIView):
    queryset = Permiso.objects.all()
    serializer_class = PermisoSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"list": ("roles", "ver")}


class PermisosAgrupadosView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {"get": ("roles", "ver")}

    def get(self, _request):
        agrupados = {}
        for permiso in Permiso.objects.all():
            agrupados.setdefault(permiso.modulo, []).append(
                {
                    "id": permiso.pk,
                    "accion": permiso.accion,
                    "descripcion": permiso.descripcion,
                }
            )
        return Response(
            [
                {"modulo": modulo, "permisos": permisos}
                for modulo, permisos in agrupados.items()
            ]
        )


class PermisosRolView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]
    required_permissions = {
        "put": ("roles", "asignar_permisos"),
    }

    def put(self, request, pk):
        rol = get_object_or_404(Rol, pk=pk)
        serializer = AsignacionPermisoSerializer(
            data=request.data,
            many=True,
        )
        serializer.is_valid(raise_exception=True)
        reemplazar_permisos_rol(rol, serializer.validated_data)
        rol = Rol.objects.prefetch_related(
            "permisos_configurados__permiso"
        ).get(pk=rol.pk)
        return Response(RolAdministracionSerializer(rol).data)
