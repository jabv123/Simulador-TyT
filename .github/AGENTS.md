# AGENTS.md — Arnés de IA de Simulador-TyT

Este archivo es la fuente de verdad para agentes de IA y colaboradores que
trabajen en **Simulador-TyT**. Define cómo razonar, qué contexto respetar, qué
herramientas usar, cómo ejecutar el proyecto y cómo verificar el trabajo antes
de proponer un cambio.

> Jerarquía de decisión ante conflictos:
> 1. Código, migraciones y pruebas existentes.
> 2. Este archivo.
> 3. `README.md`.
> 4. Supuestos del agente (deben declararse explícitamente en el PR).

---

## 1. Razonamiento: cómo debe trabajar un agente

1. **Leer antes de escribir.** Revisa `README.md`, este archivo, los modelos,
   serializadores, servicios, vistas, URLs y pruebas del módulo afectado.
2. **No adivinar el esquema.** Los nombres de tablas, columnas y reglas de
   negocio se obtienen de `apps/*/models.py` y de las migraciones. Si un campo
   no existe, propone una migración; no lo simules solo en el frontend.
3. **Entender el flujo completo.** Para una funcionalidad, identifica:
   modelo → servicio → serializador → vista/permiso → URL → frontend → pruebas.
4. **Plan mínimo.** Antes de editar, enumera archivos a cambiar, migraciones
   necesarias y pruebas que demostrarán el comportamiento. Evita refactors
   masivos o cambios no relacionados con el issue.
5. **Trabajar con evidencia.** Reproduce el problema o escribe primero la prueba
   que falla. Después implementa el cambio mínimo que la hace pasar.
6. **Respetar trabajo ajeno.** No borres, sobrescribas ni reformatees cambios
   que no formen parte del issue. No ejecutes comandos destructivos sobre bases
   de datos, archivos o historial de Git.
7. **Autoevaluarse.** Revisa el diff completo: sin secretos, sin `print()` de
   depuración, sin código comentado, sin dependencias innecesarias y sin pruebas
   deshabilitadas.
8. **Detenerse con diagnóstico.** Si tras dos intentos razonables las pruebas
   siguen fallando, no las debilites: documenta el error, el comando ejecutado,
   la traza relevante y la hipótesis en el PR o en un comentario del issue.

### Reglas de comunicación

- Issues, PRs, mensajes de error de la API y documentación de usuario: español.
- Código, nombres de clases/funciones y comentarios técnicos: español coherente
  con el estilo existente (`Cuestionario`, `Intento`, `permiso_requerido`).
- En el PR incluye: qué cambió, por qué, cómo se probó y riesgos.
- Nunca inventes resultados de pruebas. Si no pudiste ejecutar algo, dilo.

---

## 2. Contexto y reglas del sistema

### Stack y estructura

- **Python:** 3.11, 3.12 y 3.13.
- **Framework:** Django 5.2.x + Django REST Framework 3.16.x.
- **Autenticación:** SimpleJWT 5.5.x (access 15 min, refresh 1 día, rotación y
  lista negra).
- **Base de datos:** MariaDB/MySQL con `utf8mb4`; SQLite en memoria solo para
  pruebas.
- **Dependencias principales:** `mysqlclient`, `openpyxl`, `python-dotenv`.
- **Frontend:** plantillas Django, HTML, CSS y JavaScript vanilla. No agregues
  frameworks, bundlers ni pasos de compilación sin aprobación del Tech Lead.

```text
manage.py
saber_tyt/
  settings/
    base.py          # configuración común; lee variables de entorno al importar
    development.py
    production.py
    test.py          # SQLite :memory: + hashers rápidos
  urls.py
apps/
  accounts/          # Usuario, Rol, Permiso, RolPermiso, autenticación JWT
  questions/         # Categoria, Pregunta, OpcionRespuesta
  quizzes/           # Cuestionario, CuestionarioPregunta
  attempts/          # Intento, RespuestaIntento, calificación
  imports/           # Importación Excel
  core/              # configuración institucional y utilidades
static/
templates/
```

- `AUTH_USER_MODEL = "accounts.Usuario"`; usa `get_user_model()` o
  `settings.AUTH_USER_MODEL`, nunca `django.contrib.auth.models.User`.
- Las tablas usan `db_table` explícito en español y snake_case
  (`cuestionarios`, `respuestas_intento`, `rol_permisos`, etc.). No las renombres
  sin migración, respaldo y plan de compatibilidad.
- Cada app mantiene la separación `models.py` → `services.py` →
  `serializers.py` → `views.py` → `urls.py` → `tests.py`.
- Los permisos se validan en el servidor con `HasModulePermission` y
  `required_permissions`; los alcances `TODOS`, `A_SU_CARGO` y `PROPIOS` se
  aplican en las consultas. Ocultar un botón en el frontend **no** es seguridad.

### Arquitectura obligatoria: SOLID y separación de capas

Queda prohibido el **“vibe coding”**: código monolítico, vistas que concentran
lógica de negocio (*Fat Views*), lógica de negocio en plantillas, serializadores
que orquestan procesos completos o modelos que esconden flujos de negocio.

Toda funcionalidad nueva debe justificar su estructura bajo SOLID y respetar
estas responsabilidades:

| Capa | Responsabilidad permitida | Prohibido |
| --- | --- | --- |
| `models.py` | Esquema, relaciones, `constraints` e invariantes simples del registro en `clean()` | Orquestar casos de uso, consultas complejas, llamadas externas o efectos secundarios ocultos |
| `managers.py` / `selectors.py` | Consultas, filtros, `select_related`, `prefetch_related`, anotaciones y agregaciones | Escrituras, reglas de negocio, cálculos de negocio o validación de permisos |
| `services.py` | Casos de uso, transacciones, cálculos, transiciones de estado e integración entre modelos | Manejar `HttpRequest`/`HttpResponse`, serializar respuestas o decidir permisos HTTP |
| `serializers.py` | Validación de entrada y representación de salida; delega reglas de negocio a `services.py` | Duplicar reglas de negocio, orquestar flujos o hacer `save()` con lógica compleja |
| `views.py` / `viewsets.py` | Recibir la petición, aplicar permisos, invocar un servicio o selector y devolver la respuesta | Consultas complejas, cálculos, transacciones de negocio o `.save()` de flujos completos |
| `urls.py` | Enrutamiento | Lógica de negocio o consultas |
| `templates/` y `static/` | Presentación, accesibilidad y experiencia de usuario | Consultas, cálculos de negocio o decisiones de autorización |
| `tests.py` | Pruebas por capa y de integración HTTP | Depender de datos o servicios externos no controlados |

**Aplicación de SOLID en Django**

- **S — Responsabilidad única:** una función o clase de servicio por caso de
  uso (`iniciar_intento`, `finalizar_intento`, `calcular_nota`,
  `importar_preguntas`). Una vista solo coordina; no implementa el caso de uso.
- **O — Abierto/Cerrado:** reportes, exportadores, importadores y notificadores
  se extienden mediante una clase base, `Protocol` o estrategia registrada. Un
  nuevo formato o regla debe agregar una implementación, no un nuevo bloque
  `if/elif` dentro del código existente.
- **L — Sustitución de Liskov:** toda subclase o implementación debe respetar el
  contrato de la abstracción: mismos tipos de entrada/salida, mismas garantías y
  errores documentados. No cambies el significado del contrato en una subclase.
- **I — Segregación de interfaces:** prefiere contratos pequeños y cohesivos
  (`ExportadorReporte`, `LectorArchivo`, `Notificador`) antes que una clase
  “God service” con decenas de métodos.
- **D — Inversión de dependencias:** los servicios de alto nivel dependen de
  abstracciones para integraciones externas (Excel, correo, almacenamiento,
  relojes). Inyecta la dependencia por constructor o parámetro con una
  implementación por defecto; en pruebas usa un doble o fake. El cableado
  concreto se hace en la vista, configuración o composición, no dentro del
  servicio.

**Reglas de implementación**

- `transaction.atomic()` y `select_for_update()` pertenecen al servicio, no a la
  vista. Los selectores solo leen.
- Los servicios no devuelven `HttpResponse` ni conocen códigos HTTP. Lanzan
  excepciones de dominio; la capa HTTP las traduce a `400`, `403`, `404` o `409`.
- Las consultas complejas y los filtros viven en `selectors.py` o en un manager
  dedicado. Las vistas no repiten `.filter()` ni arman querysets de negocio.
- Los filtros se validan en el borde HTTP (serializador o vista) y se aplican en
  el selector. Evita N+1 con `select_related`/`prefetch_related` y verifica el
  número de consultas en los casos críticos.
- El acceso entre apps pasa por servicios o selectores del dominio dueño; no
  dupliques reglas ni importes modelos de otra app para reimplementar su lógica.
- No uses señales (`signals`) para esconder flujos de negocio. Si son necesarias
  para un efecto transversal, documéntalo y pruébalo.
- Un servicio no debe mezclar dos casos de uso. Como guía, una vista no debería
  superar ~50 líneas; si ocurre, extrae la lógica al servicio o selector.
- SOLID no significa sobreingeniería: no crees abstracciones sin una segunda
  implementación, una necesidad real de prueba o un punto de extensión previsto.
- Estas reglas aplican a código nuevo y a código que se modifique. No conviertas
  un bugfix en un refactor masivo; la deuda existente se corrige en un issue
  aparte y con pruebas de regresión.
- Prohibido `except Exception: pass`, `print()` de depuración, credenciales
  hardcodeadas y lógica de negocio en etiquetas de plantilla.

### Reglas de negocio que no se deben romper

- Una pregunta tiene exactamente una opción correcta. Selección múltiple: 2–4
  opciones. Verdadero/falso: exactamente `Verdadero` y `Falso`.
- Una pregunta con respuestas de intentos anteriores no se puede editar.
- Eliminar categorías, preguntas o cuestionarios es **lógico** (cambio de
  estado); no se borran registros académicos con historia.
- `fecha_cierre > fecha_apertura`; notas, tiempo límite e intentos dentro de los
  rangos definidos en el modelo.
- Un cuestionario solo se publica si tiene al menos una pregunta.
- Un intento no puede iniciarse antes de la apertura ni después del cierre. El
  límite efectivo es el menor entre `fecha_inicio + tiempo_limite_minutos` y
  `fecha_cierre`.
- La nota se calcula en el servidor con `Decimal` y se redondea a dos decimales:
  `(puntaje obtenido / puntaje posible) * calificación máxima`.
- Durante un intento nunca se revelan respuestas correctas ni
  retroalimentación; la revisión respeta `permitir_revision`.
- Duplicados de enunciados: comparación por categoría ignorando mayúsculas,
  tildes y espacios repetidos.
- Un administrador no puede desactivarse a sí mismo, quitarse el rol de
  administrador ni desactivar al último administrador activo. Los roles
  `Administrador` y `Estudiante` no se pueden desactivar ni eliminar.
- Fechas conscientes de zona horaria (`America/Bogota`, `USE_TZ=True`); usa
  `timezone.now()`, no `datetime.now()`.

### Ramas, commits y PRs

Formato obligatorio:

```text
feature/issue-<ID>-<descripcion>
bugfix/issue-<ID>-<descripcion>
chore/<descripcion>
```

- `<ID>` es el número del issue de GitHub, sin `#`.
- `<descripcion>`: minúsculas, ASCII, palabras separadas por guiones, 3–6
  palabras, sin tildes, `ñ`, espacios ni barras.
- Usa `chore/` solo para infraestructura, CI, herramientas o documentación que
  no implementen una historia de usuario ni corrijan un bug. Si existe un issue,
  usa `feature/` o `bugfix/` y enlázalo.
- Ejemplos válidos:
  - `feature/issue-12-reportes-calificaciones`
  - `feature/issue-123-filtros-resultados-academicos`
  - `bugfix/issue-456-login-usuario-inactivo`
  - `bugfix/issue-502-nota-mal-redondeada`
  - `chore/arnes-ia-ci-gobernanza`
- Una rama por issue o cambio. No hagas push directo a `main`; `main` está
  protegida.
- Actualiza tu rama con `main` antes de pedir revisión y resuelve conflictos en
  tu rama, nunca en `main`.
- Título de PR: `[FEATURE #123] Descripción breve` o
  `[BUGFIX #456] Descripción breve`.
- Commits en formato Conventional Commits, en español o inglés consistente:
  `feat(resultados): agrega filtro por período académico`,
  `fix(auth): rechaza refresh de usuarios inactivos`,
  `test(quizzes): cubre intentos agotados`, `docs: actualiza README`.
- El PR debe enlazar el issue (`Closes #123`), describir el cambio, listar las
  pruebas ejecutadas y adjuntar evidencia (salida de comandos o capturas).
- No incluyas en el PR: `.env`, credenciales, tokens, datos personales de
  estudiantes, archivos `media/`, bases SQLite ni artefactos de build.

---

## 3. Herramientas: comandos y dependencias

### Preparación local (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completa en `.env` `DJANGO_SECRET_KEY` y las variables `DB_*`. En Linux/macOS,
usa `source .venv/bin/activate` y `cp .env.example .env`.

### Dependencias del sistema para `mysqlclient`

`mysqlclient` se compila contra las cabeceras del cliente MySQL/MariaDB. Si
faltan, la instalación falla con errores de `mysql.h` o `pkg-config`.

**Debian/Ubuntu:**

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  default-libmysqlclient-dev build-essential pkg-config
```

**Windows:** instala Visual Studio Build Tools con la carga de trabajo
“Desarrollo para escritorio con C++” si no hay rueda binaria disponible para tu
versión de Python.

**macOS:** `brew install mysql-client pkg-config` y exporta las rutas de
`mysql-client` si es necesario.

El workflow de CI instala estas dependencias en cada ejecución. **No** elimines
ese paso ni cambies `mysqlclient` por un conector no soportado para “arreglar”
la instalación.

### Variables de entorno

`base.py` evalúa `os.environ[...]` **al importarse**. Por eso incluso la
configuración de pruebas necesita valores válidos (aunque no se conecten):

```dotenv
DJANGO_SECRET_KEY=valor-solo-para-pruebas
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver
DB_NAME=simulador_tyt
DB_USER=usuario
DB_PASSWORD=clave
DB_HOST=127.0.0.1
DB_PORT=3306
```

- `.env` está en `.gitignore`. Nunca lo subas ni imprimas su contenido.
- En CI se usan valores ficticios y la base de pruebas es SQLite en memoria.
- No apuntes la suite de pruebas a MariaDB de desarrollo o producción.

### Comandos de desarrollo

```powershell
python manage.py check
python manage.py migrate
python manage.py runserver
python manage.py seed_admin
```

Antes de aplicar migraciones sobre una base existente:

```powershell
python manage.py migrate --plan
```

Haz respaldo antes de migrar datos reales. Usa `--fake-initial` solo cuando el
esquema existente coincida exactamente y exista respaldo verificado. Nunca
borres tablas para “resolver” un conflicto.

---

## 4. Entorno de ejecución

- Trabaja desde la raíz del repositorio; todos los comandos asumen ese
  directorio.
- Usa el entorno virtual local (`.venv`). No instales paquetes globales.
- Desarrollo local: MariaDB/MySQL con `utf8mb4` y `utf8mb4_unicode_ci`.
- Pruebas y CI: SQLite en memoria (`saber_tyt.settings.test`), sin escrituras en
  MariaDB.
- CI: `ubuntu-latest`, matriz Python 3.11/3.12/3.13, sin servicios externos.
- Si tu cambio requiere una versión nueva de Python o de una dependencia,
  actualiza `requirements.txt`, este archivo y la matriz de CI en el mismo PR.
- No desactives `DEBUG`, `ALLOWED_HOSTS`, validadores, permisos, CSRF ni pruebas
  para hacer pasar el pipeline. Si un control estorba, explica por qué y propone
  una alternativa segura.
- Las migraciones de datos deben ser idempotentes (`get_or_create`,
  `update_or_create`) porque pueden ejecutarse sobre bases existentes.
- Las pruebas deben usar el ORM y evitar SQL específico de MySQL cuando el
  comportamiento pueda variar en SQLite; las diferencias de motor deben
  documentarse y cubrirse con una prueba de integración si son críticas.

---

## 5. Verificación y feedback: puerta obligatoria antes de un PR

Esta puerta es **obligatoria y no negociable**. Ejecuta **todos** estos comandos
desde la raíz, corrige cualquier fallo y adjunta la evidencia antes de abrir,
actualizar o fusionar un PR:

```powershell
python manage.py check --settings=saber_tyt.settings.test
python manage.py makemigrations --check --dry-run --settings=saber_tyt.settings.test
python manage.py test --settings=saber_tyt.settings.test
```

Ningún agente puede declarar una tarea terminada ni pedir revisión si la suite
falla, si se omitió su ejecución o si no puede mostrar la salida. “Los tests
pasaban antes” no es evidencia suficiente.

Recomendado además:

```powershell
python -m compileall -q apps saber_tyt manage.py
python -m pip check
```

Criterios:

- `check`: sin errores ni advertencias nuevas.
- `makemigrations --check --dry-run`: `No changes detected`. Si hay cambios,
  crea la migración y revisa su contenido antes de commitear.
- `test`: **0 fallos, 0 errores**. No se aceptan pruebas omitidas o marcadas
  como `skip` sin justificación y aprobación.
- Pega la salida resumida de las pruebas en el PR (número de tests y `OK`).
- Si agregas o modificas comportamiento, agrega o ajusta pruebas en el mismo PR.
  Todo bugfix debe incluir una prueba de regresión que falle sin el arreglo.
- Si el pipeline de CI falla, el merge queda bloqueado. No lo reintentes a
  ciegas: lee el log, reproduce localmente y corrige la causa.
- Arquitectura: la vista solo maneja HTTP, la lógica está en `services.py`, las
  consultas complejas en `selectors.py`/managers y no hay reglas duplicadas.

### Contrato de CI

Archivo: `.github/workflows/ci.yml`.

- Se ejecuta en `push` y `pull_request` hacia `main`, `feature/*`, `bugfix/*` y
  `chore/*`.
- Matriz: Python 3.11, 3.12 y 3.13 sobre `ubuntu-latest`.
- Paso 1: instala `default-libmysqlclient-dev`, `build-essential`, `pkg-config`
  y `requirements.txt`.
- Paso 2: valida dependencias, imports, sintaxis, `check` y migraciones.
- Paso 3: ejecuta la suite con `saber_tyt.settings.test`. Cualquier fallo marca
  el workflow como fallido.
- El job `Testing Gatekeeper` resume el resultado de la matriz y debe ser el
  check requerido en la protección de rama de `main`.
- No modifiques el workflow para saltar pruebas, usar `continue-on-error` o
  debilitar la matriz sin aprobación del Tech Lead.

### Plantillas de issues

- `.github/ISSUE_TEMPLATE/feature_request.md`: historia de usuario, contrato de
  aceptación, filtros requeridos, checklist de arquitectura SOLID y checklist de
  pruebas.
- `.github/ISSUE_TEMPLATE/bug_report.md`: matriz de reproducibilidad,
  comportamiento actual/esperado, traza de log y pruebas de regresión.

### Definición de terminado (DoD)

- [ ] El issue está enlazado y la rama cumple el formato.
- [ ] El cambio es mínimo, revisado y sin secretos ni datos personales.
- [ ] Migraciones incluidas y revisadas; `makemigrations --check` limpio.
- [ ] Arquitectura SOLID revisada: sin Fat Views ni lógica de negocio en
      modelos, plantillas o serializadores; servicios y selectores separados.
- [ ] Pruebas nuevas/ajustadas y suite completa en verde.
- [ ] Permisos y alcances validados en el servidor.
- [ ] Documentación (`README.md`, este archivo o docstrings) actualizada si
      cambió el comportamiento o la API.
- [ ] CI en verde y check `Testing Gatekeeper` aprobado.
