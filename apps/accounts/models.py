"""Modelos de usuarios, roles y permisos del sistema."""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q


class Estado(models.TextChoices):
    ACTIVO = "ACTIVO", "Activo"
    INACTIVO = "INACTIVO", "Inactivo"


class AlcancePermiso(models.TextChoices):
    TODOS = "TODOS", "Todos"
    A_SU_CARGO = "A_SU_CARGO", "A su cargo"
    PROPIOS = "PROPIOS", "Propios"


class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )

    class Meta:
        db_table = "roles"
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=Estado.values),
                name="ck_roles_estado",
            ),
        ]
        indexes = [
            models.Index(fields=["estado"], name="idx_roles_estado"),
        ]

    def __str__(self):
        return self.nombre


class CursoAcademico(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )

    class Meta:
        db_table = "cursos_academicos"
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=Estado.values),
                name="ck_cursos_acad_estado",
            ),
        ]
        indexes = [models.Index(fields=["estado"], name="idx_cursos_acad_estado")]

    def __str__(self):
        return self.nombre


class Grupo(models.Model):
    curso = models.ForeignKey(
        CursoAcademico,
        on_delete=models.PROTECT,
        related_name="grupos",
    )
    nombre = models.CharField(max_length=50)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )

    class Meta:
        db_table = "grupos_academicos"
        ordering = ["curso__nombre", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["curso", "nombre"],
                name="uq_grupo_curso_nombre",
            ),
            models.CheckConstraint(
                condition=Q(estado__in=Estado.values),
                name="ck_grupos_acad_estado",
            ),
        ]
        indexes = [models.Index(fields=["curso", "estado"], name="idx_grupo_curso_estado")]

    def __str__(self):
        return f"{self.curso.nombre} - {self.nombre}"


class Permiso(models.Model):
    modulo = models.CharField(max_length=50)
    accion = models.CharField(max_length=50)
    descripcion = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "permisos"
        ordering = ["modulo", "accion"]
        constraints = [
            models.UniqueConstraint(
                fields=["modulo", "accion"],
                name="uq_permisos_modulo_accion",
            ),
        ]
        indexes = [
            models.Index(fields=["modulo"], name="idx_permisos_modulo"),
        ]

    def __str__(self):
        return f"{self.modulo}: {self.accion}"


class RolPermiso(models.Model):
    rol = models.ForeignKey(
        Rol,
        on_delete=models.CASCADE,
        db_column="rol_id",
        related_name="permisos_configurados",
    )
    permiso = models.ForeignKey(
        Permiso,
        on_delete=models.CASCADE,
        db_column="permiso_id",
        related_name="roles_configurados",
    )
    alcance = models.CharField(
        max_length=20,
        choices=AlcancePermiso.choices,
        default=AlcancePermiso.TODOS,
    )
    pk = models.CompositePrimaryKey("rol", "permiso")

    class Meta:
        db_table = "rol_permisos"
        constraints = [
            models.CheckConstraint(
                condition=Q(alcance__in=AlcancePermiso.values),
                name="ck_rp_alcance",
            ),
        ]

    def __str__(self):
        return f"{self.rol}: {self.permiso} ({self.alcance})"


class UsuarioManager(BaseUserManager):
    """Crea usuarios almacenando contraseñas con los hashers de Django."""

    use_in_migrations = True

    def create_user(self, codigo, password=None, **extra_fields):
        correo = extra_fields.get("correo")
        if not codigo:
            raise ValueError("El código de usuario es obligatorio.")
        if not correo:
            raise ValueError("El correo electrónico es obligatorio.")
        if not extra_fields.get("nombre"):
            raise ValueError("El nombre es obligatorio.")
        if not extra_fields.get("rol"):
            raise ValueError("El rol es obligatorio.")

        extra_fields["correo"] = self.normalize_email(correo)
        usuario = self.model(codigo=codigo, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, codigo, password=None, **extra_fields):
        if not password:
            raise ValueError("La contraseña del administrador es obligatoria.")
        rol = extra_fields.get("rol")
        if rol is None:
            rol, _ = Rol.objects.get_or_create(
                nombre="Administrador",
                defaults={"descripcion": "Rol administrador del sistema."},
            )
            extra_fields["rol"] = rol
        elif rol.nombre.casefold() not in {"administrador", "admin"}:
            raise ValueError("El superusuario debe tener el rol Administrador.")

        extra_fields["estado"] = Estado.ACTIVO
        return self.create_user(codigo, password, **extra_fields)


class Usuario(AbstractBaseUser):
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column="rol_id",
        related_name="usuarios",
    )
    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.SET_NULL,
        db_column="grupo_id",
        related_name="integrantes",
        null=True,
        blank=True,
    )
    nombre = models.CharField(max_length=150)
    codigo = models.CharField(max_length=30, unique=True)
    correo = models.EmailField(max_length=150, unique=True)
    password = models.CharField(max_length=255, db_column="contrasena_hash")
    foto = models.CharField(max_length=255, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    # El esquema acordado no contiene la columna last_login de Django.
    last_login = None

    objects = UsuarioManager()

    USERNAME_FIELD = "codigo"
    REQUIRED_FIELDS = ["correo", "nombre"]

    class Meta:
        db_table = "usuarios"
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=Estado.values),
                name="ck_usuarios_estado",
            ),
        ]
        indexes = [
            models.Index(fields=["estado", "rol"], name="idx_usuarios_estado_rol"),
            models.Index(fields=["nombre"], name="idx_usuarios_nombre"),
        ]

    def __str__(self):
        return self.nombre

    @property
    def is_active(self):
        return self.estado == Estado.ACTIVO

    @property
    def is_staff(self):
        return self._es_administrador()

    @property
    def is_superuser(self):
        return self._es_administrador()

    def _es_administrador(self):
        return (
            self.is_active
            and self.rol_id is not None
            and self.rol.estado == Estado.ACTIVO
            and self.rol.nombre.casefold() in {"administrador", "admin"}
        )

    def has_perm(self, perm, obj=None):
        if (
            not self.is_active
            or not self.rol_id
            or self.rol.estado != Estado.ACTIVO
        ):
            return False
        if self._es_administrador():
            return True
        if obj is not None or not self.rol_id:
            return False

        modulo, separator, accion = perm.partition(".")
        if not separator:
            return False
        return self.rol.permisos_configurados.filter(
            permiso__modulo__iexact=modulo,
            permiso__accion__iexact=accion,
        ).exists()

    def has_module_perms(self, app_label):
        if (
            not self.is_active
            or not self.rol_id
            or self.rol.estado != Estado.ACTIVO
        ):
            return False
        if self._es_administrador():
            return True
        return self.rol.permisos_configurados.filter(
            permiso__modulo__iexact=app_label,
        ).exists()
