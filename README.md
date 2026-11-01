# Simulador de Pruebas Saber TyT

Aplicación académica construida con Django, Django REST Framework, SimpleJWT,
MariaDB, HTML, CSS, JavaScript vanilla y `openpyxl`.

## Requisitos y preparación

- Python 3.11 o superior.
- MariaDB con una base de datos `utf8mb4`.
- En Windows, herramientas de compilación C++ solo si `mysqlclient` no tiene
  una rueda disponible para la versión de Python instalada.
- El paquete de configuración Django se llama `saber_tyt`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completa en `.env` la clave secreta de Django y las credenciales MariaDB.
No compartas ese archivo ni lo incluyas en Git.

## Crear la base MariaDB

Desde una consola de MariaDB con permisos para crear bases y usuarios, ejecuta
lo siguiente. Sustituye `CAMBIA_ESTA_CLAVE` por una contraseña segura y usa
esos mismos datos en `.env`:

```sql
CREATE DATABASE IF NOT EXISTS simulador_tyt
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'simulador_user'@'localhost'
  IDENTIFIED BY 'CAMBIA_ESTA_CLAVE';

GRANT ALL PRIVILEGES ON simulador_tyt.* TO 'simulador_user'@'localhost';
FLUSH PRIVILEGES;
```

```dotenv
DB_NAME=simulador_tyt
DB_USER=simulador_user
DB_PASSWORD=CAMBIA_ESTA_CLAVE
DB_HOST=localhost
DB_PORT=3306
```

## Migraciones

Este proyecto incluye el mapeo de las tablas académicas existentes. Si la base
de datos ya contiene las tablas del esquema del simulador:

1. Haz una copia de seguridad de MariaDB.
2. Ejecuta `python manage.py migrate --plan` y revisa las operaciones.
3. Si los nombres y columnas existentes coinciden con el esquema, registra las
   tablas iniciales con `python manage.py migrate --fake-initial`.

La opción `--fake-initial` registra las migraciones iniciales para tablas
existentes; las migraciones posteriores agregan validaciones nuevas y datos de
catálogo (permisos predeterminados y configuración institucional). No elimines
tablas para resolver conflictos. Si el plan muestra diferencias, corrige el
esquema o las migraciones antes de aplicarlas.

Para una base nueva, configura primero `.env` y ejecuta normalmente:

```powershell
python manage.py migrate
python manage.py createsuperuser
```

El superusuario recibe el rol `Administrador`; también se crean los roles
predeterminados `Administrador` y `Estudiante`. Un rol `Docente` existente se
configura durante la migración; los roles personalizados se administran desde
la API.

Para crear el administrador inicial desde variables de `.env`, configura
`SEED_ADMIN_CODIGO`, `SEED_ADMIN_CORREO`, `SEED_ADMIN_NOMBRE` y
`SEED_ADMIN_PASSWORD`, luego ejecuta:

```powershell
python manage.py seed_admin
```

El comando es idempotente: si ya existe el código como administrador, no cambia
su contraseña. El inicio de sesión acepta el código institucional o el correo.

La migración `accounts.0004_permisos_por_accion` crea el catálogo granular para
usuarios, roles, categorías, preguntas, cuestionarios, importaciones, resultados
e intentos. El administrador recibe todos los permisos; el estudiante solo
recibe permisos de consulta de cuestionarios disponibles, inicio/respuesta/
finalización de intentos y consulta de su propia nota. Los roles `Docente`
preexistentes conservan y amplían sus permisos de trabajo académico.

Los modelos de las 13 tablas (`roles`, `permisos`, `rol_permisos`, `usuarios`,
`categorias`, `preguntas`, `opciones_respuesta`, `cuestionarios`,
`cuestionario_preguntas`, `intentos`, `respuestas_intento`, `importaciones` y
`configuracion_sistema`) declaran sus `db_table` explícitos. Las claves foráneas
usan índices Django y se agregan índices compuestos para filtros por estado,
fechas, propietario y orden.

## Ejecutar y probar

```powershell
python manage.py check
python manage.py runserver
```

Abre `http://127.0.0.1:8000/` para usar la interfaz web. Para ejecutar la suite
aislada en SQLite temporal (sin escribir en MariaDB):

```powershell
python manage.py test --settings=saber_tyt.settings.test
```

La configuración establece `America/Bogota`, `USE_TZ=True`, idioma `es-co`,
autenticación JWT que comprueba el estado vigente de la cuenta y
`IsAuthenticated` por defecto. El token de acceso dura 15 minutos; el refresh
dura un día, rota al renovarse y el anterior se invalida mediante la lista negra
de SimpleJWT.

## Autenticación y API

- `POST /api/auth/login/`: recibe `codigo` o `correo` y `password`; devuelve
  `access`, `refresh` y `usuario` con id, nombre, rol y permisos `modulo.accion`.
- `POST /api/auth/refresh/`: recibe `refresh` y devuelve un nuevo token de
  acceso y un refresh rotado. Rechaza cuentas o roles inactivos, expirados o
  revocados.
- `POST /api/auth/logout/`: recibe `refresh` para incluirlo en la lista negra;
  no requiere access token vigente.
- `GET /api/auth/me/`: muestra el perfil y los permisos del usuario.
- `POST /api/auth/change-password/`: requiere `contrasena_actual` y
  `contrasena_nueva`.
- `POST /api/auth/token/`, `POST /api/auth/token/renovar/` y
  `GET /api/auth/perfil/` se conservan como rutas compatibles.
- `PATCH /api/auth/perfil/`: permite actualizar nombre, foto y teléfono con el
  permiso `PERFIL.EDITAR`.
- `/api/auth/usuarios/`, `/api/auth/roles/` y `/api/auth/permisos/`: gestión
  administrativa; las contraseñas se escriben con hash y nunca se serializan.
- `/api/categorias/` y `/api/preguntas/`: banco de preguntas.
- `/api/cuestionarios/`: creación y configuración; `/disponibles/` lista pruebas
  abiertas a los estudiantes.
- `/api/cuestionarios/<id>/iniciar/`, `/api/intentos/<id>/respuestas/` y
  `/api/intentos/<id>/enviar/`: presentación y calificación.
- `/api/resultados/`: resultados filtrados por alcance.
- `/api/importaciones/`: carga Excel e historial.
- `/api/configuracion/administracion/`: configuración institucional.

### Administración de usuarios

La gestión de usuarios está disponible en `/api/usuarios/` y requiere los
permisos del módulo `USUARIOS`: `VER`, `CREAR`, `EDITAR` o `DESACTIVAR` según la
acción. El listado acepta `search` (nombre, código, correo o teléfono), `rol`,
`estado` (`ACTIVO`/`INACTIVO`), `page` y `page_size`; la respuesta está paginada.

- `GET /api/usuarios/`: listar, buscar y filtrar.
- `POST /api/usuarios/`: crear usuario. Requiere nombre, código, correo,
  contraseña de al menos 8 caracteres y un rol activo; teléfono y foto son
  opcionales.
- `GET /api/usuarios/{id}/` y `PATCH /api/usuarios/{id}/`: consultar y editar.
- `PATCH /api/usuarios/{id}/estado/`: recibe `{"estado":"ACTIVO"}` o
  `{"estado":"INACTIVO"}`.
- `POST /api/usuarios/{id}/restablecer-contrasena/`: recibe
  `{"password":"Nueva-Clave-123!"}`.

Código y correo se validan como únicos sin distinguir mayúsculas/minúsculas.
Las contraseñas se almacenan mediante el hash de Django, y nunca se devuelve la
columna `contrasena_hash`. Un administrador no puede desactivar su propia
cuenta ni quitarse el rol de administrador; tampoco se permite desactivar al
último administrador activo. Los estudiantes reciben 403 al intentar gestionar
usuarios.

Las vistas protegidas comprueban los permisos del rol en el servidor. Las
vistas existentes que aún usan `TienePermisoConfigurado` y
`permiso_requerido` mantienen compatibilidad; las nuevas deben declarar
permisos granulares.

Las vistas con permisos granulares usan `HasModulePermission` y declaran
`required_permissions` por acción HTTP o acción DRF, por ejemplo:
`{"list": ("preguntas", "ver"), "create": ("preguntas", "crear")}`.
Los permisos y sus alcances se cargan una sola vez por petición desde
`rol_permisos`. `A_SU_CARGO` filtra los cuestionarios y resultados por el
docente propietario; `PROPIOS` limita consultas al usuario autenticado.

La administración de roles también está disponible en `/api/roles/` y la de
usuarios en `/api/usuarios/`. `GET /api/roles/permisos/` agrupa el catálogo por
módulo; `PUT /api/roles/{id}/permisos/` reemplaza de forma atómica las
asignaciones completas usando una lista de objetos `permiso_id` y `alcance`.
Los roles Administrador y Estudiante no se pueden desactivar ni eliminar.

### Prueba rápida con curl.exe (PowerShell)

Ejecuta estos ejemplos con el servidor activo. Sustituye `CODIGO` y `CLAVE`;
puedes iniciar sesión enviando `correo` en lugar de `codigo`. En Postman,
selecciona **Body → raw → JSON** para el cuerpo y configura el access token en
**Authorization → Bearer Token** para las rutas protegidas.

```powershell
# Login correcto por código (para probar por correo, cambia "codigo" por "correo").
curl.exe -X POST http://127.0.0.1:8000/api/auth/login/ `
  -H "Content-Type: application/json" `
  --data-raw '{"codigo":"CODIGO","password":"CLAVE"}'

# Perfil autenticado: reemplaza ACCESS por el access devuelto al iniciar sesión.
curl.exe http://127.0.0.1:8000/api/auth/me/ `
  -H "Authorization: Bearer ACCESS"

# Renovar tokens: reemplaza REFRESH por el refresh más reciente.
curl.exe -X POST http://127.0.0.1:8000/api/auth/refresh/ `
  -H "Content-Type: application/json" `
  --data-raw '{"refresh":"REFRESH"}'

# Cambiar contraseña con un access vigente.
curl.exe -X POST http://127.0.0.1:8000/api/auth/change-password/ `
  -H "Authorization: Bearer ACCESS" `
  -H "Content-Type: application/json" `
  --data-raw '{"contrasena_actual":"CLAVE","contrasena_nueva":"Nueva-Clave-456"}'

# Cerrar sesión. Después de esto, reutilizar ese refresh debe responder HTTP 401.
curl.exe -X POST http://127.0.0.1:8000/api/auth/logout/ `
  -H "Content-Type: application/json" `
  --data-raw '{"refresh":"REFRESH"}'

# Login con una cuenta cuyo estado sea INACTIVO: debe responder HTTP 401.
curl.exe -X POST http://127.0.0.1:8000/api/auth/login/ `
  -H "Content-Type: application/json" `
  --data-raw '{"codigo":"CODIGO_INACTIVO","password":"CLAVE"}'

# Sin token: debe responder HTTP 401.
curl.exe http://127.0.0.1:8000/api/auth/me/

# Reutilizar REFRESH después de logout o de una renovación: debe responder HTTP 401.
curl.exe -X POST http://127.0.0.1:8000/api/auth/refresh/ `
  -H "Content-Type: application/json" `
  --data-raw '{"refresh":"REFRESH"}'

# Para probar un access expirado, espera 15 minutos y repite la consulta de perfil:
curl.exe http://127.0.0.1:8000/api/auth/me/ `
  -H "Authorization: Bearer ACCESS"
```

## Banco de preguntas

Las categorías se administran en `/api/categorias/` y las preguntas en
`/api/preguntas/`. Las acciones requieren permisos granulares `CATEGORIAS` o
`PREGUNTAS`; eliminar una categoría o pregunta solo cambia su estado a
`Inactivo`, sin borrar registros ni opciones.

- `GET /api/preguntas/`: permite `search` (enunciado/texto base), `categoria`,
  `tipo` (`MULTIPLE` o `VERDADERO_FALSO`), `estado` (`Activo` o `Inactivo`),
  `page` y `page_size`. Devuelve resultados paginados.
- `POST /api/preguntas/`: recibe categoría, tipo, enunciado, puntaje y opciones
  anidadas; `texto_base` y retroalimentaciones son opcionales. El creador se
  asigna desde el usuario autenticado.
- `GET /api/preguntas/{id}/`, `PATCH /api/preguntas/{id}/` y
  `DELETE /api/preguntas/{id}/`: consulta, edición y desactivación lógica.
- `GET /api/categorias/`, `POST /api/categorias/`,
  `PATCH /api/categorias/{id}/` y `DELETE /api/categorias/{id}/`: CRUD lógico
  de categorías con nombre único.

Las preguntas de selección múltiple requieren entre 2 y 4 opciones y una sola
respuesta correcta. Verdadero/falso requiere las opciones `Verdadero` y `Falso`
y exactamente una correcta. Los enunciados duplicados se detectan por categoría
ignorando mayúsculas, tildes y espacios repetidos. La escritura de pregunta y
opciones es atómica. Preguntas con respuestas de intentos anteriores no se
pueden editar; las desactivadas no se pueden incluir en cuestionarios nuevos y
sus registros existentes se conservan.

## Cuestionarios

El CRUD protegido por permisos `CUESTIONARIOS` está disponible en
`/api/cuestionarios/`. El alcance `PROPIOS` o `A_SU_CARGO` limita las consultas
administrativas al `docente_id` autenticado. `GET /api/cuestionarios/` y
`GET /api/cuestionarios/{id}/` incluyen `estado_efectivo` y
`puntaje_total_posible`. El modelo y el serializador validan fechas, notas,
tiempo límite e intentos permitidos.

- `POST /api/cuestionarios/`: crea un cuestionario borrador; puede incluir una
  lista opcional `preguntas` con `pregunta`, `orden` y `puntaje`.
- `POST /api/cuestionarios/{id}/preguntas/`: agrega una pregunta activa.
- `PUT /api/cuestionarios/{id}/preguntas/`: reemplaza la lista completa, útil
  para reordenar y editar puntajes; `GET` en la misma ruta consulta la lista.
- `PATCH /api/cuestionarios/{id}/preguntas/{pregunta_id}/`: cambia el orden o
  puntaje individual. `DELETE` en esta ruta la quita.
- `POST /api/cuestionarios/{id}/publicar/`: exige al menos una pregunta y
  publica como `PROGRAMADO` antes de la apertura o `DISPONIBLE` durante el
  período.
- `POST /api/cuestionarios/{id}/desactivar/`: devuelve a `BORRADOR`; si ya
  existen intentos, lo cierra. `DELETE /api/cuestionarios/{id}/` aplica esa
  misma desactivación lógica.

Un borrador desactivado manualmente conserva el estado `BORRADOR`; las fechas
por sí solas no lo publican. `estado_efectivo` refleja el horario del servidor
sin modificar esa decisión manual. El endpoint para estudiantes
`GET /api/cuestionarios/disponibles/` solo lista cuestionarios abiertos ahora e
incluye `intentos_usados` e `intentos_restantes`. Una vez iniciado un intento,
no se permite editar datos ni preguntas; únicamente se puede cerrar el
cuestionario.

## Intentos y calificación

El servidor controla permisos, disponibilidad, duración y calificación. El
endpoint canónico para iniciar es
`POST /api/cuestionarios/{id}/intentos/iniciar/` (se conserva
`POST /api/cuestionarios/{id}/iniciar/` por compatibilidad). Requiere un usuario
con rol Estudiante activo y permiso `INTENTOS.INICIAR`; si ya hay un intento en
curso, devuelve ese intento para reanudarlo.

- `PUT /api/intentos/{id}/respuestas/`: recibe `pregunta_id` y
  `opcion_seleccionada_id` (nullable), y opcionalmente
  `marcada_para_revision`. Se rechazan intentos ajenos, finalizados o vencidos.
- `POST /api/intentos/{id}/finalizar/`: finaliza el intento y devuelve la nota,
  si aprobó, el estado y la revisión solo cuando `permitir_revision` está
  habilitado. Se conserva `POST /api/intentos/{id}/enviar/` como alias.
- `GET /api/intentos/{id}/`: consulta un intento propio; si venció, lo finaliza
  antes de responder.
- `GET /api/intentos/mis-resultados/`: historial propio del estudiante.
- `GET /api/resultados/`: requiere permiso de resultados y admite filtros
  `cuestionario_id` y `usuario_id`; el alcance del rol restringe la consulta.

El límite efectivo es el menor entre `fecha_inicio + tiempo_limite_minutos` y
`fecha_cierre`. Una consulta o finalización posterior cierra automáticamente
el intento y conserva una respuesta vacía por cada pregunta sin contestar.
Durante un intento nunca se envían indicadores de respuesta correcta ni
retroalimentación. La nota se calcula en el servidor con la suma de puntajes
por pregunta y se redondea a dos decimales. Por ejemplo, 16 respuestas correctas
de 20 preguntas de un punto, con nota máxima 5.00, producen una calificación
de 4.00.

## Importación Excel

El módulo de importaciones acepta archivos `.xlsx` de hasta 10 MB. Descarga la
plantilla con `GET /api/importaciones/plantilla/`; incluye las columnas
`categoria`, `tipo`, `texto_base`, `pregunta`, `opcion_a`, `opcion_b`,
`opcion_c`, `opcion_d`, `respuesta_correcta`, `retroalimentacion` y `puntaje`,
más una fila de ejemplo.

El flujo recomendado tiene dos pasos y ambos requieren un archivo y un
`cuestionario_id` destino:

1. `POST /api/importaciones/previsualizar/`: multipart/form-data con `archivo`
   y `cuestionario_id`. Devuelve `validas`, `duplicadas` y `errores`, sin crear
   categorías, preguntas ni registros de importación. Cada fila indica su
   número de Excel; las categorías indican si ya existen o se crearían.
2. `POST /api/importaciones/confirmar/`: vuelve a enviar el mismo archivo y
   destino. Revalida y guarda atómicamente las filas válidas, omite duplicados,
   relaciona preguntas existentes al cuestionario cuando están activas y
   registra conteos y detalles en el historial. No se guardan filas inválidas.

`tipo` admite `MULTIPLE` y `VERDADERO_FALSO`. La respuesta correcta debe ser la
letra `A`, `B`, `C` o `D` y corresponder a una opción con texto. La selección
múltiple admite 2 a 4 opciones consecutivas; verdadero/falso requiere las
opciones `Verdadero` y `Falso`. Categoría, tipo, pregunta, dos opciones,
respuesta correcta y puntaje son obligatorios; `texto_base`, opciones C/D y
retroalimentación son opcionales. El puntaje debe ser numérico y mayor que
cero. El historial está disponible en `GET /api/importaciones/historial/`.

El archivo [ejemplo_importacion_preguntas.xlsx](./ejemplo_importacion_preguntas.xlsx)
contiene filas válidas, una repetida por normalización del enunciado y una fila
errónea sin respuesta correcta. Prueba manual desde PowerShell:

```powershell
$archivo = "ejemplo_importacion_preguntas.xlsx"
$cuestionarioId = 1
curl.exe -X POST http://127.0.0.1:8000/api/importaciones/previsualizar/ `
  -H "Authorization: Bearer ACCESS" `
  -F "archivo=@$archivo" `
  -F "cuestionario_id=$cuestionarioId"

# Repite el envío a confirmar/ después de revisar el resultado:
curl.exe -X POST http://127.0.0.1:8000/api/importaciones/confirmar/ `
  -H "Authorization: Bearer ACCESS" `
  -F "archivo=@$archivo" `
  -F "cuestionario_id=$cuestionarioId"
```

## Interfaz web, autenticación y sesión

Django sirve la plantilla compartida `templates/base.html` y los archivos
estáticos de `static/`. La página de inicio presenta el login y, una vez
autenticado, el panel cambia sus enlaces según los permisos devueltos por el
perfil. Ese filtrado es solo una ayuda de navegación; cada operación continúa
protegida y verificada por el backend. Si una ruta de la interfaz no está
autorizada, muestra `/acceso-denegado/`.

- `static/js/api.js` centraliza las peticiones, agrega el access token, intenta
  renovar una sola vez ante HTTP 401 y reintenta la petición. Si no se puede
  renovar, borra ambos tokens y vuelve al login. Guarda la rotación del refresh
  token en `sessionStorage`.
- `static/js/auth.js` contiene `login`, `logout`, `getCurrentUser`,
  `hasPermission('modulo.accion')` y `guard`.
- `static/js/components.js` ofrece tablas con filtro y paginación, modal,
  notificaciones tipo toast y validación visual de formularios.
- `static/css/app.css` define el tema responsive, los estados de error/carga y
  los componentes compartidos.
- El panel incorpora administración de usuarios con filtros, creación y edición
  en modal, activación y restablecimiento de contraseña; la pantalla de roles
  presenta la matriz de permisos por módulo y conserva el alcance asignado.
- El banco permite crear y editar preguntas con opciones y selección de respuesta
  correcta, fija las opciones de verdadero/falso y muestra los errores del API.
  La importación Excel presenta las filas válidas, duplicadas y erróneas en
  pestañas antes de confirmar.
- Cuestionarios incluye selección de preguntas con orden y puntaje, edición,
  publicación y desactivación. Resultados permite filtrar por cuestionario y
  estudiante, consultar la aprobación y revisar la duración del intento.

Los controles visibles se limitan según los permisos cargados en el perfil. Las
operaciones siguen protegidas por la API; los filtros de alcance (`PROPIOS` y
`A_SU_CARGO`) los aplica el servidor.

**Probar login y logout:** inicia `.\.venv\Scripts\python.exe manage.py runserver`,
abre `http://127.0.0.1:8000/` e ingresa el código o correo y contraseña del
usuario activo. La sesión se mantiene en `sessionStorage` durante la pestaña.
Usa **Cerrar sesión** para llamar a `/api/auth/logout/`, revocar el refresh y
limpiar la sesión. Credenciales incorrectas o una cuenta desactivada muestran
el mensaje del servidor en español.

**Probar renovación automática:** en las herramientas de desarrollador, cambia
temporalmente el valor `tyt_access` de `sessionStorage` por un token inválido y
carga un panel que consulte la API. La petición responderá 401, el cliente
intentará `POST /api/auth/refresh/`, guardará los tokens renovados y reintentará
la petición original. Si el refresh expiró o ya fue revocado, se borrará la
sesión y se mostrará nuevamente el login.

## Reglas principales cubiertas

- Una pregunta debe tener exactamente una opción correcta; verdadero/falso
  admite exactamente dos opciones.
- Cierre posterior a apertura, notas en rango, tiempo e intentos mayores que
  cero.
- Una pregunta puede aparecer en varios cuestionarios mediante
  `cuestionario_preguntas`.
- No se puede iniciar una prueba antes de abrir ni después de cerrar.
- Cada pregunta de un intento tiene una fila de respuesta desde el inicio;
  las que se dejan en blanco se conservan y reciben cero.
- La nota se calcula como `(puntaje obtenido / puntaje posible) * calificación
  máxima`, redondeada a dos decimales.
- La revisión de respuestas correctas no se filtra durante el intento y respeta
  la opción de revisión del cuestionario.
- `RolPermiso` conserva su clave primaria compuesta (`rol_id`, `permiso_id`);
  el catálogo granular de acciones se carga con una migración de datos.
