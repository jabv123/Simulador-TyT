"""Pruebas de autenticación y permisos configurables por rol."""

from datetime import timedelta
from datetime import datetime, timezone
from django.contrib.auth.hashers import check_password
from django.urls import reverse
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from unittest.mock import patch
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.quizzes.models import Cuestionario

from .models import AlcancePermiso, Permiso, Rol, RolPermiso, Usuario


class SeedAdminCommandTests(TestCase):
    def test_seed_admin_es_idempotente_y_usa_codigo(self):
        variables = {
            "SEED_ADMIN_CODIGO": "SEED-ADMIN-1",
            "SEED_ADMIN_CORREO": "seed-admin@test.local",
            "SEED_ADMIN_NOMBRE": "Administrador seed",
            "SEED_ADMIN_PASSWORD": "Seed-Strong-Password-984!",
        }
        with patch.dict("os.environ", variables):
            call_command("seed_admin", verbosity=0)
            administrador = Usuario.objects.get(codigo="SEED-ADMIN-1")
            self.assertTrue(administrador.check_password(variables["SEED_ADMIN_PASSWORD"]))
            self.assertTrue(administrador.is_active)
            self.assertEqual(Usuario.USERNAME_FIELD, "codigo")

            call_command("seed_admin", verbosity=0)
            self.assertEqual(Usuario.objects.filter(codigo="SEED-ADMIN-1").count(), 1)

    def test_seed_admin_reporta_variables_ausentes(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(CommandError):
                call_command("seed_admin", verbosity=0)


class PermisosInicialesTests(TestCase):
    def test_administrador_tiene_todo_y_estudiante_solo_permisos_de_prueba(self):
        administrador = Rol.objects.get(nombre="Administrador")
        estudiante = Rol.objects.get(nombre="Estudiante")
        permisos = set(
            Permiso.objects.values_list("modulo", "accion")
        )
        admin_permisos = set(
            RolPermiso.objects.filter(rol=administrador).values_list(
                "permiso__modulo", "permiso__accion"
            )
        )
        estudiante_permisos = set(
            RolPermiso.objects.filter(rol=estudiante).values_list(
                "permiso__modulo", "permiso__accion"
            )
        )
        esperados = {
            ("CUESTIONARIOS", "VER_DISPONIBLES"),
            ("INTENTOS", "INICIAR"),
            ("INTENTOS", "RESPONDER"),
            ("INTENTOS", "FINALIZAR"),
            ("INTENTOS", "VER_NOTA_PROPIA"),
            ("RESULTADOS", "VER_PROPIA_NOTA"),
        }
        self.assertEqual(admin_permisos, permisos)
        self.assertEqual(estudiante_permisos, esperados)
        self.assertFalse(
            RolPermiso.objects.filter(
                rol=estudiante,
                alcance=AlcancePermiso.TODOS,
            ).exists()
        )


class AccountsApiTests(APITestCase):
    def setUp(self):
        self.rol_admin, _ = Rol.objects.get_or_create(nombre="Administrador")
        self.admin = Usuario.objects.create_user(
            "ADMIN-1",
            "Admin-password-123",
            nombre="Administradora",
            correo="admin@test.local",
            rol=self.rol_admin,
        )
        self.client.force_authenticate(self.admin)

    def test_jwt_login_y_perfil_no_exponen_hash(self):
        self.client.force_authenticate(user=None)
        respuesta = self.client.post(
            reverse("accounts:token"),
            {"codigo": self.admin.codigo, "password": "Admin-password-123"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("access", respuesta.data)
        self.assertIn("refresh", respuesta.data)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {respuesta.data['access']}"
        )
        perfil = self.client.get(reverse("accounts:perfil"))
        self.assertEqual(perfil.status_code, 200)
        self.assertNotIn("password", perfil.data)
        self.assertNotIn("contrasena_hash", perfil.data)
        reportes = self.client.get(reverse("reports:home"))
        self.assertEqual(reportes.status_code, 200)
        self.assertContains(reportes, "Consultas y reportes")

    def test_username_field_es_codigo_y_login_usa_codigo(self):
        self.assertEqual(Usuario.USERNAME_FIELD, "codigo")
        self.client.force_authenticate(user=None)
        respuesta = self.client.post(
            reverse("accounts:token"),
            {"codigo": self.admin.codigo, "password": "Admin-password-123"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_login_acepta_correo_y_devuelve_rol_y_permisos(self):
        self.client.force_authenticate(user=None)
        respuesta = self.client.post(
            reverse("accounts:login"),
            {
                "codigo": "",
                "correo": self.admin.correo,
                "password": "Admin-password-123",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["usuario"]["id"], self.admin.pk)
        self.assertEqual(respuesta.data["usuario"]["rol"], "Administrador")
        self.assertIn("USUARIOS.GESTIONAR", respuesta.data["usuario"]["permisos"])

    def test_login_rechaza_cuenta_inactiva_con_mensaje_claro(self):
        self.admin.estado = "INACTIVO"
        self.admin.save(update_fields=["estado"])
        self.client.force_authenticate(user=None)
        respuesta = self.client.post(
            reverse("accounts:login"),
            {"codigo": self.admin.codigo, "password": "Admin-password-123"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 401)
        self.assertIn("inactiva", respuesta.data["detail"].lower())

    def test_me_sin_token_devuelve_401(self):
        self.client.force_authenticate(user=None)
        respuesta = self.client.get(reverse("accounts:me"))
        self.assertEqual(respuesta.status_code, 401)

    def test_access_token_expirado_no_autentica(self):
        token = AccessToken.for_user(self.admin)
        token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        respuesta = self.client.get(reverse("accounts:me"))
        self.assertEqual(respuesta.status_code, 401)

    def test_access_token_de_cuenta_desactivada_se_rechaza(self):
        self.client.force_authenticate(user=None)
        tokens = self.client.post(
            reverse("accounts:login"),
            {"codigo": self.admin.codigo, "password": "Admin-password-123"},
            format="json",
        )
        self.admin.estado = "INACTIVO"
        self.admin.save(update_fields=["estado"])
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens.data['access']}"
        )
        respuesta = self.client.get(reverse("accounts:me"))
        self.assertEqual(respuesta.status_code, 401)
        self.assertIn("inactiva", respuesta.data["detail"].lower())

    def test_logout_revoca_refresh_y_no_se_puede_reutilizar(self):
        self.client.force_authenticate(user=None)
        tokens = self.client.post(
            reverse("accounts:login"),
            {"codigo": self.admin.codigo, "password": "Admin-password-123"},
            format="json",
        )
        logout = self.client.post(
            reverse("accounts:logout"),
            {"refresh": tokens.data["refresh"]},
            format="json",
        )
        self.assertEqual(logout.status_code, 200, logout.data)
        reportes = self.client.get(reverse("reports:home"))
        self.assertEqual(reportes.status_code, 401)
        renovacion = self.client.post(
            reverse("accounts:refresh"),
            {"refresh": tokens.data["refresh"]},
            format="json",
        )
        self.assertEqual(renovacion.status_code, 401)

    def test_change_password_actualiza_el_hash(self):
        self.client.force_authenticate(user=None)
        tokens = self.client.post(
            reverse("accounts:login"),
            {"codigo": self.admin.codigo, "password": "Admin-password-123"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens.data['access']}"
        )
        respuesta = self.client.post(
            reverse("accounts:change-password"),
            {
                "contrasena_actual": "Admin-password-123",
                "contrasena_nueva": "Nueva-password-456",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.admin.refresh_from_db()
        self.assertTrue(check_password("Nueva-password-456", self.admin.password))

    def test_no_permite_renovar_token_si_se_desactiva_el_rol(self):
        self.client.force_authenticate(user=None)
        tokens = self.client.post(
            reverse("accounts:token"),
            {
                "codigo": self.admin.codigo,
                "correo": "",
                "password": "Admin-password-123",
            },
            format="json",
        )
        self.rol_admin.estado = "INACTIVO"
        self.rol_admin.save(update_fields=["estado"])
        respuesta = self.client.post(
            reverse("accounts:token-renovar"),
            {"refresh": tokens.data["refresh"]},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_rotacion_refresh_invalida_el_token_anterior(self):
        self.client.force_authenticate(user=None)
        tokens = self.client.post(
            reverse("accounts:token"),
            {"codigo": self.admin.codigo, "password": "Admin-password-123"},
            format="json",
        )
        primero = self.client.post(
            reverse("accounts:token-renovar"),
            {"refresh": tokens.data["refresh"]},
            format="json",
        )
        self.assertEqual(primero.status_code, 200, primero.data)
        self.assertIn("refresh", primero.data)

        reutilizacion = self.client.post(
            reverse("accounts:token-renovar"),
            {"refresh": tokens.data["refresh"]},
            format="json",
        )
        self.assertEqual(reutilizacion.status_code, 401)

        segundo = self.client.post(
            reverse("accounts:token-renovar"),
            {"refresh": primero.data["refresh"]},
            format="json",
        )
        self.assertEqual(segundo.status_code, 200, segundo.data)

    def test_admin_configura_permiso_y_el_servidor_lo_aplica(self):
        permisos = self.client.get(reverse("accounts:permisos"))
        permiso_categoria = next(
            permiso
            for permiso in permisos.data
            if permiso["modulo"] == "CATEGORIAS"
            and permiso["accion"] == "CREAR"
        )
        rol_respuesta = self.client.post(
            reverse("accounts:roles"),
            {
                "nombre": "Gestor de categorías",
                "descripcion": "Administra categorías.",
                "estado": "ACTIVO",
                "permisos": [
                    {
                        "permiso_id": permiso_categoria["id"],
                        "alcance": "TODOS",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(rol_respuesta.status_code, 201, rol_respuesta.data)

        usuario_respuesta = self.client.post(
            reverse("accounts:usuarios"),
            {
                "nombre": "Gestor",
                "codigo": "GESTOR-1",
                "correo": "gestor@test.local",
                "password": "Gestor-password-123",
                "rol": rol_respuesta.data["id"],
            },
            format="json",
        )
        self.assertEqual(usuario_respuesta.status_code, 201, usuario_respuesta.data)
        self.assertNotIn("password", usuario_respuesta.data)

        gestor = Usuario.objects.get(correo="gestor@test.local")
        self.client.force_authenticate(gestor)
        creada = self.client.post(
            reverse("questions:categorias"),
            {"nombre": "Gestión autorizada"},
            format="json",
        )
        self.assertEqual(creada.status_code, 201, creada.data)

        self.client.force_authenticate(user=None)
        estudiante_rol = Rol.objects.get(nombre="Estudiante")
        estudiante = Usuario.objects.create_user(
            "EST-1",
            "Student-password-123",
            nombre="Estudiante",
            correo="estudiante@test.local",
            rol=estudiante_rol,
        )
        self.client.force_authenticate(estudiante)
        denegada = self.client.post(
            reverse("questions:categorias"),
            {"nombre": "Gestión no autorizada"},
            format="json",
        )
        self.assertEqual(denegada.status_code, 403)

    def test_rol_docente_evaluador_solo_recibe_permisos_asignados(self):
        rol = Rol.objects.create(
            nombre="Docente Evaluador",
            descripcion="Puede trabajar con preguntas, cuestionarios y resultados.",
        )
        permisos = Permiso.objects.filter(
            modulo__in=["PREGUNTAS", "CUESTIONARIOS", "RESULTADOS"],
            accion__in=["VER", "CREAR", "EDITAR"],
        )
        asignaciones = [
            {
                "permiso_id": permiso.pk,
                "alcance": (
                    "A_SU_CARGO"
                    if permiso.modulo in {"CUESTIONARIOS", "RESULTADOS"}
                    else "TODOS"
                ),
            }
            for permiso in permisos
        ]
        self.client.force_authenticate(self.admin)
        actualizado = self.client.put(
            f"/api/roles/{rol.pk}/permisos/",
            asignaciones,
            format="json",
        )
        self.assertEqual(actualizado.status_code, 200, actualizado.data)
        self.assertEqual(len(actualizado.data["permisos_configurados"]), len(asignaciones))

        docente = Usuario.objects.create_user(
            "EVAL-1",
            "Evaluator-password-123",
            nombre="Docente Evaluador",
            correo="evaluador@test.local",
            rol=rol,
        )
        self.client.force_authenticate(docente)
        preguntas = self.client.get("/api/preguntas/")
        self.assertEqual(preguntas.status_code, 200, preguntas.data)

        usuarios = self.client.get("/api/usuarios/")
        self.assertEqual(usuarios.status_code, 403)
        self.assertIn("usuarios.ver", usuarios.data["detail"].lower())

    def test_alcance_a_su_cargo_filtra_cuestionarios_por_docente(self):
        rol = Rol.objects.create(nombre="Docente con alcance")
        permiso = Permiso.objects.get(
            modulo="CUESTIONARIOS",
            accion="VER",
        )
        RolPermiso.objects.create(
            rol=rol,
            permiso=permiso,
            alcance=AlcancePermiso.A_SU_CARGO,
        )
        docente = Usuario.objects.create_user(
            "DOC-OWN",
            "Teacher-password-123",
            nombre="Docente propio",
            correo="docente-propio@test.local",
            rol=rol,
        )
        otra_persona = Usuario.objects.create_user(
            "DOC-OTHER",
            "Teacher-password-123",
            nombre="Otro docente",
            correo="docente-otro@test.local",
            rol=self.rol_admin,
        )
        ahora = datetime.now(timezone.utc)
        cuestionario_propio = Cuestionario.objects.create(
            docente=docente,
            nombre="Prueba propia",
            fecha_apertura=ahora,
            fecha_cierre=ahora + timedelta(hours=1),
            tiempo_limite_minutos=30,
            intentos_permitidos=1,
            calificacion_maxima=5,
            calificacion_aprobacion=3,
        )
        Cuestionario.objects.create(
            docente=otra_persona,
            nombre="Prueba ajena",
            fecha_apertura=ahora,
            fecha_cierre=ahora + timedelta(hours=1),
            tiempo_limite_minutos=30,
            intentos_permitidos=1,
            calificacion_maxima=5,
            calificacion_aprobacion=3,
        )

        self.client.force_authenticate(docente)
        respuesta = self.client.get("/api/cuestionarios/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(
            [item["id"] for item in respuesta.data],
            [cuestionario_propio.pk],
        )

    def test_rol_desactivado_no_autoriza_a_sus_usuarios(self):
        rol = Rol.objects.create(nombre="Rol temporal")
        permiso = Permiso.objects.get(modulo="PREGUNTAS", accion="VER")
        RolPermiso.objects.create(
            rol=rol,
            permiso=permiso,
            alcance=AlcancePermiso.TODOS,
        )
        usuario = Usuario.objects.create_user(
            "TEMP-1",
            "Temporary-password-123",
            nombre="Usuario temporal",
            correo="temporal@test.local",
            rol=rol,
        )
        rol.estado = "INACTIVO"
        rol.save(update_fields=["estado"])
        self.client.force_authenticate(usuario)

        respuesta = self.client.get("/api/preguntas/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("permiso", respuesta.data["detail"].lower())

    def test_no_se_puede_desactivar_ni_eliminar_roles_predeterminados(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.patch(
            f"/api/roles/{self.rol_admin.pk}/",
            {"estado": "INACTIVO"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.rol_admin.estado, "ACTIVO")

        estudiante = Rol.objects.get(nombre="Estudiante")
        eliminado = self.client.delete(f"/api/roles/{estudiante.pk}/")
        self.assertEqual(eliminado.status_code, 400)

    def test_permisos_agrupados_por_modulo(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.get("/api/roles/permisos/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        preguntas = next(
            modulo for modulo in respuesta.data if modulo["modulo"] == "PREGUNTAS"
        )
        self.assertIn("VER", {item["accion"] for item in preguntas["permisos"]})

    def test_admin_crea_usuario_con_password_hasheado_y_sin_exponerlo(self):
        estudiante = Rol.objects.get(nombre="Estudiante")
        respuesta = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Usuario nuevo",
                "codigo": "NEW-USER-1",
                "correo": "new-user@test.local",
                "password": "Strong-User-123!",
                "telefono": "3001234567",
                "foto": "https://example.test/foto.png",
                "rol": estudiante.pk,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        usuario = Usuario.objects.get(codigo="NEW-USER-1")
        self.assertTrue(usuario.check_password("Strong-User-123!"))
        self.assertNotEqual(usuario.password, "Strong-User-123!")
        self.assertNotIn("password", respuesta.data)
        self.assertNotIn("contrasena_hash", respuesta.data)
        self.assertEqual(respuesta.data["rol"], estudiante.pk)

    def test_estudiante_no_puede_administrar_usuarios(self):
        estudiante = Usuario.objects.create_user(
            "STUDENT-USERS",
            "Student-Strong-123!",
            nombre="Estudiante",
            correo="student-users@test.local",
            rol=Rol.objects.get(nombre="Estudiante"),
        )
        self.client.force_authenticate(estudiante)
        listado = self.client.get("/api/usuarios/")
        creacion = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "No permitido",
                "codigo": "FORBIDDEN-USER",
                "correo": "forbidden@test.local",
                "password": "Strong-User-123!",
                "rol": estudiante.rol_id,
            },
            format="json",
        )
        self.assertEqual(listado.status_code, 403)
        self.assertEqual(creacion.status_code, 403)

    def test_estudiante_no_puede_cambiar_estado_ni_restablecer_clave(self):
        estudiante = Usuario.objects.create_user(
            "STUDENT-STATE",
            "Student-Strong-456!",
            nombre="Estudiante restringido",
            correo="student-state@test.local",
            rol=Rol.objects.get(nombre="Estudiante"),
        )
        self.client.force_authenticate(estudiante)
        estado = self.client.patch(
            f"/api/usuarios/{self.admin.pk}/estado/",
            {"estado": "INACTIVO"},
            format="json",
        )
        clave = self.client.post(
            f"/api/usuarios/{self.admin.pk}/restablecer-contrasena/",
            {"password": "Reset-Strong-123!"},
            format="json",
        )
        self.assertEqual(estado.status_code, 403)
        self.assertEqual(clave.status_code, 403)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.estado, "ACTIVO")
        self.assertTrue(self.admin.check_password("Admin-password-123"))

    def test_codigo_y_correo_unicos_sin_distinguir_mayusculas(self):
        base = {
            "nombre": "Duplicado",
            "codigo": "admin-1",
            "correo": "other@test.local",
            "password": "Strong-User-123!",
            "rol": Rol.objects.get(nombre="Estudiante").pk,
        }
        duplicado_codigo = self.client.post(
            "/api/usuarios/",
            base,
            format="json",
        )
        self.assertEqual(duplicado_codigo.status_code, 400)
        self.assertIn("codigo", duplicado_codigo.data)

        base["codigo"] = "OTHER-CODE"
        base["correo"] = "ADMIN@test.local"
        duplicado_correo = self.client.post(
            "/api/usuarios/",
            base,
            format="json",
        )
        self.assertEqual(duplicado_correo.status_code, 400)
        self.assertIn("correo", duplicado_correo.data)

    def test_listado_usuarios_busca_filtra_y_pagina(self):
        estudiante = Rol.objects.get(nombre="Estudiante")
        usuarios = [
            Usuario.objects.create_user(
                f"SEARCH-{numero}",
                "Search-Strong-123!",
                nombre=f"Buscable {numero}",
                correo=f"search-{numero}@test.local",
                rol=estudiante,
                estado="INACTIVO" if numero == 1 else "ACTIVO",
            )
            for numero in range(1, 13)
        ]
        self.client.force_authenticate(self.admin)

        pagina = self.client.get("/api/usuarios/?page_size=5")
        self.assertEqual(pagina.status_code, 200, pagina.data)
        self.assertEqual(pagina.data["count"], 13)
        self.assertEqual(len(pagina.data["results"]), 5)
        self.assertIsNotNone(pagina.data["next"])

        filtrado = self.client.get(
            f"/api/usuarios/?rol={estudiante.pk}&estado=INACTIVO&search=SEARCH-1"
        )
        self.assertEqual(filtrado.status_code, 200, filtrado.data)
        self.assertEqual(filtrado.data["count"], 1)
        self.assertEqual(filtrado.data["results"][0]["id"], usuarios[0].pk)

    def test_no_permite_asignar_rol_inactivo_ni_password_corto(self):
        estudiante = Rol.objects.get(nombre="Estudiante")
        estudiante.estado = "INACTIVO"
        estudiante.save(update_fields=["estado"])
        respuesta_rol = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Inválido",
                "codigo": "INVALID-ROLE",
                "correo": "invalid-role@test.local",
                "password": "Strong-User-123!",
                "rol": estudiante.pk,
            },
            format="json",
        )
        self.assertEqual(respuesta_rol.status_code, 400)

        estudiante.estado = "ACTIVO"
        estudiante.save(update_fields=["estado"])
        respuesta_password = self.client.post(
            "/api/usuarios/",
            {
                "nombre": "Inválido",
                "codigo": "SHORT-PASSWORD",
                "correo": "short-password@test.local",
                "password": "short",
                "rol": estudiante.pk,
            },
            format="json",
        )
        self.assertEqual(respuesta_password.status_code, 400)

    def test_estado_usuario_no_permite_autodesactivar_admin(self):
        respuesta = self.client.patch(
            f"/api/usuarios/{self.admin.pk}/estado/",
            {"estado": "INACTIVO"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.estado, "ACTIVO")

    def test_admin_no_puede_quitarse_su_rol_ni_restablecer_password_corto(self):
        estudiante = Rol.objects.get(nombre="Estudiante")
        respuesta_rol = self.client.patch(
            f"/api/usuarios/{self.admin.pk}/",
            {"rol": estudiante.pk},
            format="json",
        )
        self.assertEqual(respuesta_rol.status_code, 400)

        respuesta_password = self.client.post(
            f"/api/usuarios/{self.admin.pk}/restablecer-contrasena/",
            {"password": "tiny"},
            format="json",
        )
        self.assertEqual(respuesta_password.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Admin-password-123"))

    def test_admin_cambia_estado_y_restablece_password(self):
        estudiante = Rol.objects.get(nombre="Estudiante")
        usuario = Usuario.objects.create_user(
            "STATE-USER",
            "Initial-Password-123!",
            nombre="Usuario estado",
            correo="state-user@test.local",
            rol=estudiante,
        )
        desactivado = self.client.patch(
            f"/api/usuarios/{usuario.pk}/estado/",
            {"estado": "INACTIVO"},
            format="json",
        )
        self.assertEqual(desactivado.status_code, 200, desactivado.data)
        usuario.refresh_from_db()
        self.assertEqual(usuario.estado, "INACTIVO")

        reactivado = self.client.patch(
            f"/api/usuarios/{usuario.pk}/estado/",
            {"estado": "ACTIVO"},
            format="json",
        )
        self.assertEqual(reactivado.status_code, 200, reactivado.data)
        restablecida = self.client.post(
            f"/api/usuarios/{usuario.pk}/restablecer-contrasena/",
            {"password": "Reset-Password-123!"},
            format="json",
        )
        self.assertEqual(restablecida.status_code, 200, restablecida.data)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("Reset-Password-123!"))
        self.assertNotIn("contrasena_hash", restablecida.data)
