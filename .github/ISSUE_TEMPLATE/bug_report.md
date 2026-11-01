---
name: Reporte de bug
about: Reporta un comportamiento incorrecto con matriz de reproducibilidad, traza y plan de regresión
title: "[BUG] "
labels: bug
assignees: ""
---

## 1. Resumen

<!-- Una o dos frases claras: qué falla y a quién afecta. -->

- **Severidad:** <!-- Crítica | Alta | Media | Baja -->
- **Módulo:** <!-- accounts | questions | quizzes | attempts | imports | core | frontend | CI -->
- **Issue relacionado:** <!-- #123 -->
- **¿Bloquea el merge o el despliegue?** <!-- Sí | No -->

## 2. Matriz de reproducibilidad

| Dimensión | Valor |
| --- | --- |
| Frecuencia | <!-- Siempre (100 %) \| Intermitente (indicar %) \| Una vez --> |
| Entorno | <!-- Local \| Desarrollo \| CI \| Producción --> |
| Sistema operativo | <!-- Windows 11, Ubuntu 24.04, macOS... --> |
| Python | <!-- 3.11.x \| 3.12.x \| 3.13.x --> |
| Django | <!-- 5.2.x --> |
| Base de datos | <!-- MariaDB/MySQL + versión \| SQLite :memory: --> |
| Navegador / cliente | <!-- Chrome 1xx, Firefox, curl, Postman... --> |
| Commit / rama | <!-- hash corto y rama --> |
| Configuración | <!-- saber_tyt.settings.test \| development \| production --> |
| Primera vez observado | <!-- fecha/hora y zona America/Bogota --> |

**Condiciones previas**

- <!-- Rol del usuario, permisos, estado del cuestionario/intento, datos necesarios. -->
- <!-- Variables de entorno relevantes (sin mostrar valores secretos). -->

**Datos de prueba**

- <!-- IDs, archivos .xlsx, pasos de seed o fixture. No adjuntes datos personales reales. -->

## 3. Pasos para reproducir

1.
2.
3.
4.

**Resultado actual**

<!-- Qué ocurre, con código HTTP, mensaje exacto o captura. -->

**Resultado esperado**

<!-- Qué debería ocurrir según el contrato de aceptación o la regla de negocio. -->

**¿Se reproduce en la suite de pruebas?**

- [ ] Sí. Test: <!-- ruta::Clase::test --> 
- [ ] No.
- [ ] No aplica.

## 4. Evidencia y traza de log

```text
# Pega aquí la traza completa y el comando que la produjo.
# Ejemplo:
# python manage.py test apps.attempts --settings=saber_tyt.settings.test
# Traceback (most recent call last):
#   ...
```

**Log del servidor / CI**

```text
# Fragmento relevante. Incluye timestamp, nivel y mensaje.
```

**Petición / respuesta (si aplica)**

```http
### Petición
POST /api/... HTTP/1.1
Content-Type: application/json

{ ... }

### Respuesta
HTTP/1.1 4xx
Content-Type: application/json

{ ... }
```

> **Sanitiza siempre:** elimina contraseñas, tokens JWT, `DJANGO_SECRET_KEY`,
> credenciales `DB_*`, correos, documentos y datos personales de estudiantes.
> No adjuntes `.env` ni volcados completos de la base de datos.

## 5. Impacto y alcance

- **Usuarios/roles afectados:**
- **Datos afectados:**
- **¿Hay pérdida o corrupción de datos?** <!-- Sí | No | Por confirmar -->
- **Workaround temporal:**
- **¿Afecta seguridad, permisos o calificaciones?** <!-- Sí | No; explica -->

## 6. Hipótesis técnica

<!-- Archivos, funciones, consultas, migraciones o dependencias sospechosas. -->

- **Capa afectada:** <!-- model | selector/manager | service | serializer | view | template -->
- **Archivo(s) probable(s):**
- **Hipótesis:**
- **¿El origen parece una violación de separación de capas o SOLID?** <!-- Sí/No; explica -->
- **Cómo validarla:**

## 7. Criterios de aceptación del arreglo

| ID | Dado | Cuando | Entonces |
| --- | --- | --- | --- |
| CA-01 | | | |
| CA-02 | | | |

- [ ] El comportamiento actual deja de ocurrir.
- [ ] El resultado esperado se cumple en todos los entornos indicados.
- [ ] No se introducen regresiones en módulos relacionados.

## 8. Checklist de pruebas de regresión

- [ ] Prueba que reproduce el bug y falla antes del arreglo.
- [ ] La misma prueba pasa después del arreglo.
- [ ] Prueba a nivel de servicio/selector (si la lógica lo amerita).
- [ ] El arreglo no introduce lógica de negocio en vistas, serializadores ni
      plantillas.
- [ ] Caso borde relacionado cubierto.
- [ ] Permisos/alcances verificados (si aplica).
- [ ] Validaciones de modelo/serializador verificadas (si aplica).
- [ ] Migración probada sobre base existente (si aplica).
- [ ] Suite completa del módulo afectado en verde.
- [ ] Suite completa del proyecto en verde.

## 9. Verificación obligatoria

```powershell
python manage.py check --settings=saber_tyt.settings.test
python manage.py makemigrations --check --dry-run --settings=saber_tyt.settings.test
python manage.py test --settings=saber_tyt.settings.test
```

- [ ] Los tres comandos terminan sin errores.
- [ ] Salida de pruebas adjunta en el PR (cantidad de tests y `OK`).
- [ ] CI en verde y `Testing Gatekeeper` aprobado.

## 10. Notas adicionales

<!-- Enlaces, capturas, discusiones, decisiones pendientes o riesgo de rollback. -->
