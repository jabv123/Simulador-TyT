---
name: Historia de usuario / Feature
about: Propone una funcionalidad con contrato de aceptación, filtros requeridos y plan de pruebas
title: "[FEATURE] "
labels: enhancement
assignees: ""
---

## 1. Historia de usuario

**Como** <!-- rol: estudiante, docente, administrador... -->
**Quiero** <!-- capacidad concreta -->
**Para** <!-- beneficio o problema que resuelve -->

## 2. Contexto y valor

<!-- Situación actual, problema, impacto esperado y módulos involucrados. -->

- **Módulo(s):** <!-- accounts | questions | quizzes | attempts | imports | core | frontend -->
- **Issue relacionado:** <!-- #123 -->
- **Prioridad:** <!-- Alta | Media | Baja -->
- **Dependencias:** <!-- issues, migraciones, endpoints o datos externos -->

## 3. Alcance

### Incluye

- [ ] <!-- ... -->

### No incluye

- [ ] <!-- ... -->

## 4. Contrato de aceptación

Cada criterio debe ser observable y verificable. Usa `CA-01`, `CA-02`, etc.

| ID | Dado (contexto) | Cuando (acción) | Entonces (resultado esperado) |
| --- | --- | --- | --- |
| CA-01 | | | |
| CA-02 | | | |
| CA-03 | | | |

**Reglas de negocio adicionales**

- <!-- Validaciones, permisos, alcances, estados, fechas, redondeos, etc. -->
- <!-- Errores esperados y códigos HTTP: 400, 401, 403, 404, 409. -->

## 5. Filtros requeridos

Marca los filtros aplicables y documenta su comportamiento. Todo filtro debe
validarse en el servidor, combinarse con los demás mediante `AND`, respetar el
alcance del rol y devolver `400` ante valores inválidos y `200 []` cuando no
haya coincidencias.

| Filtro | Parámetro propuesto | ¿Requerido? | Tipo / formato | Regla y caso borde |
| --- | --- | --- | --- | --- |
| Período académico | `periodo_academico` | Sí / No / Condicional | Texto o enum (`YYYY-S`) | <!-- ej. período activo por defecto --> |
| Año | `anio` | Sí / No / Condicional | Entero de 4 dígitos | <!-- rango permitido --> |
| Curso | `curso` / `curso_id` | Sí / No / Condicional | ID o texto | <!-- curso del estudiante --> |
| Eje temático | `eje_tematico` / `eje_tematico_id` | Sí / No / Condicional | ID o texto | <!-- catálogo relacionado --> |
| Cuestionario | `cuestionario_id` | Sí / No / Condicional | ID | <!-- cuestionario existente --> |
| Estudiante | `estudiante_id` / `usuario_id` | Sí / No / Condicional | ID | <!-- solo si el rol lo permite --> |

**Requisitos transversales de filtros**

- [ ] El filtro se aplica en la consulta ORM (no en el frontend).
- [ ] Se valida el tipo y el formato; valores inválidos responden `400` con
      mensaje en español.
- [ ] Se respetan `PROPIOS` / `A_SU_CARGO` / `TODOS`.
- [ ] Los filtros se pueden combinar sin duplicar resultados.
- [ ] La respuesta conserva paginación y orden definidos.
- [ ] Si el campo no existe en el modelo actual, el issue incluye la migración
      y la actualización de contrato antes de implementar.
- [ ] Se agregan índices si el filtro se usa sobre tablas grandes.

## 6. Propuesta técnica

- **Endpoints / rutas:**
- **Modelos y migraciones:**
- **Selectores / managers:**
- **Servicios y casos de uso:**
- **Serializadores:**
- **Permisos y alcances:**
- **Frontend / plantillas:**
- **Impacto en datos existentes:**

## 7. Impacto arquitectónico y SOLID

**Capas afectadas:** <!-- models | selectors/managers | services | serializers | views | templates -->

**Justificación de la estructura:** <!-- Por qué esta división es la mínima y correcta. -->

- [ ] **S:** cada caso de uso está en un servicio; la vista solo maneja HTTP.
- [ ] **O:** la funcionalidad se extiende agregando una implementación, sin
      nuevos bloques `if/elif` en código existente.
- [ ] **L:** las subclases o implementaciones respetan el contrato de la
      abstracción (entradas, salidas y errores).
- [ ] **I:** los contratos son pequeños y cohesivos; no hay “God services”.
- [ ] **D:** las integraciones externas se inyectan detrás de una abstracción.
- [ ] Las consultas complejas viven en `selectors.py` o en un manager dedicado.
- [ ] Las transacciones y las excepciones de dominio viven en `services.py`.
- [ ] No hay lógica de negocio en modelos, serializadores, vistas ni plantillas.
- [ ] No hay N+1: se usan `select_related` / `prefetch_related` cuando aplica.
- [ ] Si se modifica código existente, se justifica por qué no puede resolverse
      mediante extensión.
- [ ] Deuda técnica o excepciones a estas reglas: <!-- justificar o "Ninguna" -->

## 8. Checklist de pruebas unitarias

- [ ] Servicio: caso de uso, transacción, cálculos y excepciones de dominio.
- [ ] Selector/manager: filtros y consultas complejas, sin escrituras.
- [ ] Contrato de estrategia/exportador: implementaciones intercambiables (si aplica).
- [ ] Vista: delega en el servicio/selector y responde correctamente, sin lógica
      de negocio propia.
- [ ] Modelo/servicio: validaciones y reglas de negocio del cambio.
- [ ] Endpoint: caso feliz con datos válidos.
- [ ] Endpoint: sin resultados devuelve `200` y lista vacía.
- [ ] Endpoint: parámetro inválido devuelve `400`.
- [ ] Filtro por período académico.
- [ ] Filtro por año.
- [ ] Filtro por curso.
- [ ] Filtro por eje temático.
- [ ] Filtro por cuestionario.
- [ ] Filtro por estudiante.
- [ ] Combinación de dos o más filtros.
- [ ] Permisos: anónimo `401`, rol sin permiso `403`, rol autorizado `200`.
- [ ] Alcance `PROPIOS` / `A_SU_CARGO`: no se filtran datos ajenos.
- [ ] Paginación, orden y campos de respuesta.
- [ ] Regresión de funcionalidades existentes del módulo.
- [ ] Migración probada sobre base existente (si aplica).

## 9. Verificación obligatoria

```powershell
python manage.py check --settings=saber_tyt.settings.test
python manage.py makemigrations --check --dry-run --settings=saber_tyt.settings.test
python manage.py test --settings=saber_tyt.settings.test
```

- [ ] Los tres comandos terminan sin errores.
- [ ] Salida de pruebas adjunta en el PR (cantidad de tests y `OK`).
- [ ] CI en verde y `Testing Gatekeeper` aprobado.
- [ ] La tarea no se marca como terminada si la suite falló o no se ejecutó.

## 10. Definición de terminado

- [ ] Contrato de aceptación implementado y verificado.
- [ ] Arquitectura SOLID revisada y sin Fat Views ni lógica en plantillas.
- [ ] Pruebas nuevas/ajustadas incluidas en el mismo PR.
- [ ] Permisos y filtros validados en el servidor.
- [ ] Migraciones incluidas y revisadas (si aplica).
- [ ] Documentación/README actualizados (si cambió la API).
- [ ] Sin secretos, datos personales ni artefactos generados en el PR.

## 11. Riesgos y notas

<!-- Impacto, rollback, compatibilidad con datos existentes, dudas abiertas. -->
