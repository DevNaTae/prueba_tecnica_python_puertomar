# Control industrial de ciclos de esterilización

Solución para procesar lecturas de temperatura y presión asociadas a lotes de
producción. La aplicación recibe un archivo JSON, valida la consistencia del
ciclo, identifica desviaciones y genera un reporte ordenado y trazable.

La interfaz principal es una aplicación de consola. PostgreSQL se utiliza como
persistencia opcional y Docker Compose proporciona un entorno reproducible con
Python 3.14 y PostgreSQL 18.

## Qué cubre la solución

- validación estricta del contrato JSON y de sus campos obligatorios;
- control de fechas, zonas horarias, rangos y pertenencia de las lecturas al
  ciclo;
- clasificación independiente de temperatura y presión;
- cálculo de promedios, extremos, alertas y porcentaje de cumplimiento;
- asignación de estado por lote;
- reporte JSON ordenado por fecha de inicio;
- persistencia transaccional e idempotente en PostgreSQL;
- errores de dominio comprensibles y registro de eventos con `logging`.

## Ejecución reproducible con Docker

El entorno completo se inicia desde la raíz del proyecto:

```bash
docker compose up --build
```

Compose se encarga de:

1. iniciar PostgreSQL 18 y esperar hasta que acepte conexiones;
2. aplicar `database/001_schema.sql` mediante un contenedor de migración;
3. construir la imagen de la aplicación con un usuario sin privilegios;
4. procesar `samples/input.json`, persistir la carga y escribir el reporte.

El resultado queda disponible en:

```text
salida/reporte.json
```

La aplicación es un proceso de consola finito, por lo que debe aparecer como
`Exited (0)` al terminar correctamente. El contenedor `database` permanece
activo y saludable mientras `docker compose up` continúa en primer plano.

Estado de los servicios:

```bash
docker compose ps --all
```

Consulta SQL solicitada en la prueba:

```bash
docker compose exec database \
  psql -U nat -d puertitomar -f /sql/002_queries.sql
```

Suite completa dentro de contenedores:

```bash
docker compose --profile test run --build --rm tests
```

Detención del entorno:

```bash
docker compose down
```

El volumen de PostgreSQL se conserva después de `down`. La base no publica
puertos al host y la autenticación `trust` está restringida a la red interna
del entorno local de Compose. Esta configuración no está destinada a
producción.

## Ejecución directa con Python

Requisitos de referencia:

- Python 3.14 o una versión 3.x compatible;
- PostgreSQL 18 para persistencia; el proyecto también fue comprobado
  localmente con PostgreSQL 16.14.

Preparación del entorno:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Procesamiento sin base de datos:

```bash
python -m src.main samples/input.json --output salida/reporte.json
```

Procesamiento con persistencia en la instancia local validada:

```bash
export DATABASE_URL='dbname=puertitomar user=nat host=/var/run/postgresql'
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/001_schema.sql
python -m src.main samples/input.json \
  --output salida/reporte.json \
  --persist
```

También puede utilizarse un archivo `.env` no versionado. La aplicación no
contiene contraseñas ni valores de conexión incorporados en el código.

### Interfaz de consola

```text
python -m src.main INPUT [--output OUTPUT] [--persist]
```

- `INPUT`: archivo JSON que contiene los lotes.
- `--output`: destino del reporte; por defecto `salida/reporte.json`.
- `--persist`: guarda la entrada en PostgreSQL utilizando `DATABASE_URL`.

Códigos de terminación:

- `0`: reporte generado correctamente;
- `2`: archivo, JSON o regla de dominio inválida;
- `3`: error de escritura o persistencia.

## Flujo de procesamiento

La aplicación mantiene una única ruta para las reglas del negocio:

```text
JSON de entrada
    → validación del contrato
    → validación del ciclo
    → clasificación de lecturas
    → métricas y estado del lote
    → persistencia opcional
    → reporte JSON
```

Cada lectura recibe exactamente una clasificación:

- `NORMAL`: temperatura y presión dentro de sus límites;
- `ALERTA_TEMPERATURA`: solo la temperatura está fuera del rango;
- `ALERTA_PRESION`: solo la presión está fuera del rango;
- `ALERTA_MULTIPLE`: ambas mediciones incumplen sus límites.

El estado final depende de la cantidad de lecturas alertadas:

- `APROBADO`: ninguna alerta;
- `OBSERVADO`: una o dos alertas;
- `RECHAZADO`: tres o más alertas.

Los archivos [samples/input.json](samples/input.json) y
[samples/output.json](samples/output.json) forman un caso reproducible distinto
del ejemplo incluido en el enunciado.

## Organización del código

```text
src/
├── domain/
│   ├── enums.py                 # clasificaciones y estados
│   └── exceptions.py            # errores propios del dominio
├── schemas/
│   └── sterilization.py         # contratos estrictos de entrada y salida
├── services/
│   └── report_service.py        # reglas, métricas y construcción del reporte
├── infrastructure/
│   └── json_files.py            # lectura y escritura de JSON
├── repositories/
│   └── postgres.py              # persistencia parametrizada
├── config.py                    # configuración desde el entorno
├── database.py                  # apertura de conexiones Psycopg
└── main.py                      # punto de entrada de consola

database/
├── 001_schema.sql               # tablas, integridad, índices y triggers
└── 002_queries.sql              # lotes con alertas y desviación térmica

tests/
├── unit/                        # dominio, contratos, archivos y CLI
└── integration/                 # comportamiento real de PostgreSQL

Dockerfile                       # etapas runtime y tests
compose.yaml                     # base, migración, aplicación y perfil test
RESPUESTAS_POSTGRESQL.md         # desarrollo de las cinco preguntas
```

El servicio de reportes no conoce el sistema de archivos ni PostgreSQL. Los
adaptadores se coordinan desde la interfaz de consola, evitando duplicar las
reglas de clasificación o de cálculo.

## Estrategia de pruebas

Pruebas unitarias y cobertura:

```bash
pytest -m "not integration"
pytest --cov=src --cov-report=term-missing -m "not integration"
```

Integración contra PostgreSQL:

```bash
TEST_DATABASE_URL="$DATABASE_URL" pytest -m integration
```

Calidad estática:

```bash
ruff format --check src tests
ruff check src tests
```

La suite está distribuida por comportamiento y cubre:

- entrada correcta, campos vacíos y nombres no pertenecientes al contrato;
- fecha final inválida, rangos invertidos y lectura fuera del ciclo;
- alertas individuales, alerta múltiple y límites inclusivos;
- métricas, estados y orden cronológico del reporte;
- errores de archivo y códigos de salida de la CLI;
- configuración de conexión sin exposición de secretos;
- persistencia idempotente e integridad temporal en PostgreSQL.

## Persistencia PostgreSQL

El esquema `control_esterilizacion` separa cuatro entidades:

- `lote`: código operativo y producto;
- `autoclave`: catálogo de equipos;
- `ciclo_esterilizacion`: ventana y límites asociados al lote;
- `lectura`: mediciones tomadas durante el ciclo.

Las claves internas utilizan `bigint identity`. Los códigos del negocio tienen
restricciones únicas y las relaciones emplean `RESTRICT` para proteger la
trazabilidad. La fecha de una lectura se valida mediante triggers porque la
regla depende del intervalo almacenado en otra tabla.

No se persisten estados, clasificaciones, promedios ni porcentajes. Todos son
valores derivados. `database/002_queries.sql` calcula los lotes con alertas, su
cantidad de desviaciones y la mayor desviación de temperatura.

Las respuestas sobre modelado, consulta analítica, índices, concurrencia y
particionamiento están desarrolladas en
[RESPUESTAS_POSTGRESQL.md](RESPUESTAS_POSTGRESQL.md).

## Criterios adoptados

- Los límites mínimos y máximos son inclusivos.
- Una lectura puede coincidir con el inicio o con el fin del ciclo.
- Todas las fechas deben incluir zona horaria.
- Cada lote debe contener al menos una lectura.
- Las presiones y sus límites no pueden ser negativos.
- Las mediciones del reporte se redondean a tres decimales y el porcentaje a
  dos; los cálculos utilizan los valores originales.
- El contrato acepta únicamente los campos en español establecidos en el
  enunciado, sin alias alternativos.
- Una carga repetida actualiza el lote, ciclo y lecturas coincidentes sin
  eliminar mediciones históricas que no aparezcan en el nuevo archivo.

## Dependencias principales

- `pydantic`: validación de los contratos JSON;
- `pydantic-settings`: configuración externa;
- `psycopg`: comunicación con PostgreSQL;
- `pytest` y `pytest-cov`: pruebas automatizadas;
- `ruff`: formato y análisis estático.

Las versiones admitidas se encuentran en [requirements.txt](requirements.txt).