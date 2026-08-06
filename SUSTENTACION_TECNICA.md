# Guía de sustentación técnica

Documento de apoyo para explicar la solución durante la entrevista. No sustituye
al README ni a las respuestas de PostgreSQL.

## Presentación en un minuto

> Desarrollé una aplicación de consola que procesa lotes de esterilización desde
> JSON. Separé la validación del contrato, las reglas del dominio, la generación
> del reporte y la persistencia. Cada lectura se clasifica según temperatura y
> presión; después se calculan métricas y el estado del lote. PostgreSQL conserva
> únicamente datos base y protege la integridad con constraints, claves foráneas
> y triggers. La solución puede ejecutarse directamente o con Docker Compose y
> tiene pruebas unitarias e integración real con PostgreSQL.

## Cómo se cubrió el requerimiento

| Necesidad | Implementación |
|---|---|
| Leer y validar JSON | Modelos Pydantic estrictos y adaptador de archivos |
| Validar ciclo y rangos | Reglas centralizadas en `ReportService` |
| Clasificar lecturas | Función pura `classify_reading` |
| Calcular métricas y estado | Servicio de reportes, sin duplicar lógica |
| Generar salida ordenada | Modelos de salida y escritura JSON |
| Manejar errores | Excepciones propias, mensajes claros y códigos de salida |
| Persistir información | Repositorio Psycopg con SQL parametrizado y transacciones |
| Proteger integridad | PK, FK, `UNIQUE`, `CHECK`, índices y triggers |
| Automatizar el entorno | Docker Compose con base, migración, CLI y pruebas |

## Recorrido de la arquitectura

```text
src.main
   ├── infrastructure.json_files     lee y escribe JSON
   ├── schemas.sterilization         valida el contrato
   ├── services.report_service       aplica las reglas del negocio
   └── repositories.postgres         persiste cuando se solicita
```

Responsabilidad de cada capa:

- `schemas`: estructura, tipos, campos requeridos y fechas con zona horaria;
- `services`: reglas que relacionan varios campos y cálculos del caso;
- `domain`: estados, clasificaciones y excepciones propias;
- `infrastructure`: acceso a archivos;
- `repositories`: acceso transaccional a PostgreSQL;
- `main`: coordinación y códigos de salida, sin reglas del negocio.

La decisión central fue mantener el servicio de reportes independiente del
sistema de archivos, PostgreSQL y Docker. Esto permite probar las reglas sin
infraestructura.

## Reglas que debo poder explicar

- Una lectura en el límite mínimo o máximo es válida: los límites son
  inclusivos.
- La lectura puede coincidir con el inicio o el fin del ciclo.
- Las fechas deben contener zona horaria para evitar comparaciones ambiguas.
- Una lectura es `ALERTA_MULTIPLE` cuando fallan temperatura y presión al mismo
  tiempo.
- El porcentaje de cumplimiento es:

```text
lecturas normales / total de lecturas × 100
```

- `APROBADO`: cero alertas.
- `OBSERVADO`: una o dos alertas.
- `RECHAZADO`: tres o más alertas.
- El reporte se ordena por la fecha de inicio, no por el orden del archivo.
- Los cálculos usan los valores originales; el redondeo se aplica al resultado.

## Decisiones técnicas principales

### Por qué una CLI y no una API

El enunciado acepta consola, REST o una estructura equivalente. Elegí CLI porque
el flujo principal consiste en transformar un archivo en otro y el tiempo de la
prueba es limitado. Una API agregaría rutas, servidor, manejo HTTP y pruebas
adicionales sin mejorar las reglas evaluadas.

### Por qué Pydantic

Permite validar el contrato de entrada, rechazar campos desconocidos, exigir
fechas conscientes de zona horaria y producir errores estructurados. No existen
alias: se acepta únicamente la nomenclatura en español definida por la prueba.

Pydantic valida forma y tipos. `ReportService` valida reglas relacionales, por
ejemplo que `fin > inicio` o que cada lectura pertenezca al intervalo.

### Por qué funciones puras para clasificación y estado

`classify_reading` y `status_from_alert_count` dependen solo de sus argumentos.
Esto facilita probar límites y estados sin archivos, mocks ni conexiones.

### Por qué un repositorio

El código SQL queda aislado de la lógica del reporte. El repositorio recibe
modelos ya validados, usa parámetros en lugar de concatenar SQL y convierte
errores de Psycopg en `PersistenceError`.

### Cómo se controla la transacción

La conexión administrada por contexto confirma todos los lotes al finalizar
correctamente y revierte la operación ante una excepción. Así no queda una
carga parcialmente persistida. Las pruebas de integración reciben una conexión
externa y hacen `rollback` para no dejar datos de prueba.

### Por qué la carga es idempotente

Los códigos de lote y autoclave son únicos. Se utiliza `ON CONFLICT` para
actualizar la información existente y la combinación
`(ciclo_id, fecha_hora)` identifica una lectura. Repetir la misma carga no crea
duplicados.

Una carga no elimina lecturas históricas que falten en el nuevo JSON. Es una
decisión conservadora para preservar trazabilidad.

## Modelo PostgreSQL

El esquema `control_esterilizacion` contiene:

- `lote`: identidad del lote y producto;
- `autoclave`: catálogo único de equipos;
- `ciclo_esterilizacion`: lote, autoclave, fechas y límites;
- `lectura`: instante, temperatura y presión.

### Puntos que pueden preguntar

**¿Por qué existe una tabla `autoclave` adicional?**

Evita repetir y escribir de forma inconsistente el código del equipo. También
permite relacionar futuros atributos o mantenimiento sin modificar los ciclos.

**¿Por qué las claves internas son `bigint identity`?**

Son compactas, eficientes para índices y no dependen de códigos operativos que
podrían cambiar. Los códigos siguen protegidos por `UNIQUE`.

**¿Por qué `timestamptz`?**

Representa un instante real y normaliza correctamente entradas con zona
horaria. Es apropiado para comparar ciclos y lecturas provenientes de distintas
configuraciones horarias.

**¿Por qué `numeric` en PostgreSQL pero `float` en Python?**

La base conserva mediciones decimales de forma estable. Para el alcance y la
precisión del ejemplo, `float` es suficiente en los cálculos y se rechazan
infinito y `NaN`. En un sistema regulado o con precisión contractual migraría
los modelos y cálculos a `Decimal`.

**¿Por qué no guardar clasificación, promedios o estado?**

Son valores derivados de lecturas y límites. Guardarlos duplicaría información
y podría producir inconsistencias al modificar una medición.

**¿Por qué la fecha de la lectura se valida con un trigger?**

La regla consulta el intervalo de otra tabla. Un `CHECK` debe depender de la
fila que está validando y no garantiza correctamente reglas entre tablas. El
trigger bloquea el ciclo con `FOR SHARE` mientras comprueba el intervalo; otro
trigger impide reducir un ciclo dejando lecturas afuera.

**¿Por qué `RESTRICT` en las relaciones?**

Un borrado en cascada podría eliminar trazabilidad industrial accidentalmente.
Con `RESTRICT`, la eliminación debe ser explícita y ejecutarse en un orden
controlado.

### Índices defendibles

- La restricción única del lote cubre búsquedas por código.
- `(autoclave_id, inicio DESC)` localiza ciclos por equipo y fecha.
- `(ciclo_id, fecha_hora)` evita lecturas duplicadas y sirve para rangos dentro
  de un ciclo.
- `(fecha_hora, ciclo_id)` favorece consultas globales por rango temporal.

No se debe afirmar que un índice siempre será utilizado. Se verifica con datos
representativos mediante `EXPLAIN (ANALYZE, BUFFERS)`; PostgreSQL puede elegir
`Seq Scan` para tablas pequeñas o filtros poco selectivos.

## Estrategia de pruebas

Las pruebas no están agrupadas en un único archivo. Se separaron por regla o
componente para que un fallo identifique con claridad la responsabilidad.

| Caso obligatorio | Prueba principal |
|---|---|
| Flujo correcto | `test_calcula_resumen_de_un_lote_conforme` |
| Fecha inválida | `test_rechaza_fecha_final_igual_al_inicio` |
| Rango inválido | `test_rechaza_un_rango_invertido` |
| Lectura fuera del ciclo | `test_rechaza_una_lectura_anterior_al_ciclo` |
| Alerta múltiple | `test_clasifica_alerta_multiple` |
| Cálculo de estado | `test_calcula_estado_por_cantidad_de_alertas` |

Además se prueban campos vacíos, contrato sin alias, presión negativa, alertas
individuales, límites inclusivos, orden del reporte, JSON inválido, CLI,
configuración, idempotencia y trigger temporal.

Última validación realizada:

- 27 pruebas aprobadas;
- 25 unitarias y 2 de integración;
- 91% de cobertura medida sobre `src`;
- Ruff sin errores de formato ni análisis.

Las pruebas parametrizadas no agrupan comportamientos distintos: reutilizan el
mismo escenario para comprobar valores equivalentes, como los tres estados del
lote o los dos tipos de rango inválido.

## Docker Compose

La composición tiene cuatro responsabilidades independientes:

- `database`: PostgreSQL 18 con volumen persistente y healthcheck;
- `migration`: aplica el SQL y termina;
- `application`: procesa el ejemplo, persiste, genera el reporte y termina;
- `tests`: perfil opcional para ejecutar pytest.

Que `application` aparezca como `Exited (0)` es correcto: no es un servidor, es
una tarea de consola completada.

La imagen ejecuta Python como usuario sin privilegios. PostgreSQL no publica su
puerto al host. `trust` se acepta únicamente porque la red es interna y local;
en producción usaría SCRAM, secretos administrados y un usuario con privilegios
mínimos.

## Preguntas difíciles y respuesta corta

**¿Qué ocurre si el JSON está mal formado?**  
El adaptador captura el error de decodificación, informa línea y columna y la
CLI termina con código `2` sin mostrar un traceback al usuario.

**¿Qué pasa si falla el segundo lote al persistir?**  
La transacción completa se revierte; no queda guardado solamente el primero.

**¿Cómo evitaría que dos procesos cierren el mismo ciclo?**  
Usaría un `UPDATE` condicional con `WHERE fin IS NULL ... RETURNING`, o
`SELECT ... FOR UPDATE` si antes debo leer y calcular. El segundo proceso
actualizaría cero filas después de esperar el bloqueo.

**¿Por qué `fin` puede ser nulo en PostgreSQL si el JSON lo exige?**  
El archivo representa ciclos listos para procesar, pero la base también puede
modelar un ciclo todavía abierto. Al cerrarlo se exige que sea posterior al
inicio.

**¿Por qué un solo ciclo por lote?**  
El enunciado describe un ciclo por lote y esa cardinalidad se protege con
`UNIQUE(lote_id)`. Si el negocio admite reprocesos, eliminaría esa unicidad y
añadiría un número o tipo de ciclo.

**¿Por qué no se usó un ORM?**  
El modelo es pequeño y la prueba evalúa PostgreSQL. SQL explícito permite mostrar
constraints, `ON CONFLICT`, índices y transacciones sin agregar una abstracción
innecesaria.

**¿Es una solución lista para producción?**  
Es una entrega completa para el alcance evaluado. Producción requeriría gestión
de secretos, migraciones versionadas, observabilidad, políticas de respaldo,
pruebas de carga y definición formal de retención.

**¿Dónde está aplicada la orientación a objetos?**  
En modelos con responsabilidades claras, `ReportService` y el repositorio. No
se crearon clases para cada función porque la clasificación y el estado se
expresan mejor como funciones puras.

**¿Cómo se utilizó asistencia automatizada?**  
Se utilizó Codex para apoyar arquitectura, implementación, revisión, pruebas y
documentación. La decisión debe declararse y todo el contenido debe poder ser
explicado por la persona candidata.

## Limitaciones que conviene reconocer

- `float` es suficiente para la prueba, pero `Decimal` sería preferible si la
  precisión tuviera efectos regulatorios.
- El JSON se carga completo en memoria; para volúmenes grandes usaría lectura
  incremental o procesamiento por lotes.
- El DDL es ejecutable e idempotente, pero no reemplaza un sistema de
  migraciones versionadas.
- La autenticación Docker está diseñada solo para desarrollo local.
- La cardinalidad actual permite un ciclo por lote.
- No existe API porque no era necesaria para el flujo solicitado.

## Mejoras prioritarias con más tiempo

1. Incorporar migraciones versionadas y CI con PostgreSQL 18.
2. Sustituir `float` por `Decimal` si el negocio define precisión contractual.
3. Configurar SCRAM y secretos para un despliegue no local.
4. Añadir pruebas de concurrencia y rendimiento con un volumen representativo.
5. Definir retención y particionamiento cuando el tamaño de `lectura` lo
   justifique.

## Demostración sugerida

```bash
docker compose up --build
docker compose ps --all
cat salida/reporte.json
docker compose --profile test run --build --rm tests
docker compose exec database \
  psql -U nat -d puertitomar -f /sql/002_queries.sql
```

Durante la demostración:

1. mostrar que migración y aplicación terminan con código `0`;
2. abrir un lote aprobado, uno observado y uno rechazado en el reporte;
3. señalar una alerta múltiple y el porcentaje de cumplimiento;
4. ejecutar las pruebas;
5. cerrar con la consulta de lotes alertados y desviación térmica.

## Frases que debo evitar

- “Está listo para producción”.
- “PostgreSQL siempre usará este índice”.
- “Psycopg crea un pool de conexiones” — el proyecto no usa un pool.
- “Docker guarda la contraseña” — no se versionó ninguna contraseña.
- “La aplicación se cayó” cuando aparece `Exited (0)`.
- “La API procesa los lotes” — esta solución no tiene API.

La mejor defensa es explicar las decisiones, reconocer los límites y relacionar
cada parte del código con un requisito concreto.
