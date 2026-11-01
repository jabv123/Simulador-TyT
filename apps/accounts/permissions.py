"""Permisos de API basados en la configuración de cada rol."""

from rest_framework.permissions import BasePermission

from .models import AlcancePermiso, Estado, RolPermiso


def _permisos_cacheados(request):
    """Carga una vez por petición los permisos y alcances del rol actual."""
    if hasattr(request, "_permisos_rol_cache"):
        return request._permisos_rol_cache

    usuario = request.user
    permisos = {}
    if (
        usuario
        and usuario.is_authenticated
        and usuario.is_active
        and usuario.rol_id
        and usuario.rol.estado == Estado.ACTIVO
    ):
        permisos = {
            (modulo.lower(), accion.lower()): alcance
            for modulo, accion, alcance in RolPermiso.objects.filter(
                rol_id=usuario.rol_id
            ).values_list(
                "permiso__modulo",
                "permiso__accion",
                "alcance",
            )
        }
    request._permisos_rol_cache = permisos
    return permisos


def tiene_permiso(request, modulo, accion):
    """Verifica permiso y estado actual del rol consultando el caché de petición."""
    usuario = request.user
    if (
        not usuario
        or not usuario.is_authenticated
        or not usuario.is_active
        or not usuario.rol_id
        or usuario.rol.estado != Estado.ACTIVO
    ):
        return False
    return (modulo.lower(), accion.lower()) in _permisos_cacheados(request)


def obtener_alcance(usuario, permiso, request=None):
    """Obtiene el alcance asociado al permiso del usuario autenticado."""
    if request is not None:
        modulo, accion = permiso.split(".", 1)
        return _permisos_cacheados(request).get((modulo.lower(), accion.lower()))
    if usuario._es_administrador():
        return AlcancePermiso.TODOS
    modulo, accion = permiso.split(".", 1)
    asignacion = usuario.rol.permisos_configurados.filter(
        permiso__modulo__iexact=modulo,
        permiso__accion__iexact=accion,
    ).only("alcance").first()
    return asignacion.alcance if asignacion else None


def filtrar_por_alcance(queryset, usuario, permiso, campo_propietario, request=None):
    alcance = obtener_alcance(usuario, permiso, request=request)
    if alcance == AlcancePermiso.TODOS:
        return queryset
    if alcance in {AlcancePermiso.PROPIOS, AlcancePermiso.A_SU_CARGO}:
        if not campo_propietario:
            return queryset.none()
        return queryset.filter(**{campo_propietario: usuario})
    return queryset.none()


class HasModulePermission(BasePermission):
    """Valida el permiso por módulo/acción configurado para el método de la vista."""

    message = "No tienes el permiso necesario para realizar esta acción."

    metodo_accion = {
        "GET": "list",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "destroy",
        "HEAD": "list",
        "OPTIONS": "list",
    }

    def _action(self, request, view):
        action = getattr(view, "action", None)
        if action:
            return action
        configurados = getattr(view, "required_permissions", {})
        metodo = request.method.lower()
        if metodo in configurados:
            return metodo
        action = self.metodo_accion.get(request.method.upper(), request.method.lower())
        lookup = getattr(view, "lookup_url_kwarg", None) or getattr(
            view, "lookup_field", "pk"
        )
        if action == "list" and view.kwargs.get(lookup) is not None:
            return "retrieve"
        return action

    @staticmethod
    def _normalizar_requisitos(requisito):
        if (
            isinstance(requisito, (tuple, list))
            and len(requisito) == 2
            and all(isinstance(valor, str) for valor in requisito)
        ):
            return [requisito]
        if isinstance(requisito, (tuple, list)):
            return [
                par
                for par in requisito
                if isinstance(par, (tuple, list)) and len(par) == 2
            ]
        return []

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        requisitos_por_accion = getattr(view, "required_permissions", {})
        accion = self._action(request, view)
        requisitos = self._normalizar_requisitos(
            requisitos_por_accion.get(accion)
        )
        if not requisitos:
            permiso_legacy = getattr(view, "permiso_requerido", None)
            if permiso_legacy and "." in permiso_legacy:
                requisitos = [permiso_legacy.split(".", 1)]
            else:
                self.message = (
                    "La vista protegida no tiene permisos configurados "
                    "para esta acción."
                )
                return False

        for modulo, nombre_accion in requisitos:
            if tiene_permiso(request, modulo, nombre_accion):
                return True
        etiquetas = " o ".join(
            f"{modulo}.{nombre_accion}" for modulo, nombre_accion in requisitos
        )
        self.message = f"No tienes el permiso requerido: {etiquetas}."
        return False


class TienePermisoConfigurado(HasModulePermission):
    """Compatibilidad con vistas que todavía declaran permiso_requerido."""


class PuedeConsultarCategorias(HasModulePermission):
    """Permite consultar categorías con el permiso de categorías o preguntas."""

    message = "No tienes permiso para consultar o administrar categorías."


class PuedeVerResultados(HasModulePermission):
    """Permite consultar resultados completos o la nota propia."""

    message = "No tienes permiso para consultar estos resultados."

    def has_permission(self, request, view):
        view.required_permissions = {
            **getattr(view, "required_permissions", {}),
            "list": [("resultados", "ver"), ("resultados", "ver_propia_nota")],
            "retrieve": [
                ("resultados", "ver"),
                ("resultados", "ver_propia_nota"),
            ],
        }
        return super().has_permission(request, view)


def permiso_requerido(view, accion):
    """Obtiene el par módulo/acción que habilita la acción de una vista."""
    requerido = getattr(view, "required_permissions", {}).get(accion)
    requisitos = HasModulePermission._normalizar_requisitos(requerido)
    return requisitos[0] if requisitos else None


def permiso_de_vista(request, view):
    """Resuelve el permiso principal declarado para la acción HTTP actual."""
    accion = HasModulePermission()._action(request, view)
    permiso = permiso_requerido(view, accion)
    if permiso:
        return ".".join(permiso)
    return getattr(view, "permiso_requerido", None)


def exigir_permiso(request, modulo, accion, mensaje=None):
    """Lanza una respuesta 403 coherente si falta un permiso dinámico."""
    from rest_framework.exceptions import PermissionDenied

    if not tiene_permiso(request, modulo, accion):
        raise PermissionDenied(
            mensaje or f"No tienes el permiso requerido: {modulo}.{accion}."
        )
