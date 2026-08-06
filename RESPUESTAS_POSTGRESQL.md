# Respuestas PostgreSQL

## 1. Modelado e integridad

El script ejecutable está en `database/001_schema.sql`. El núcleo del modelo
usa identificadores internos independientes de los códigos del negocio:

```sql
SET search_path TO control_esterilizacion, public;

CREATE TABLE autoclave (
    autoclave_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo varchar(30) NOT NULL UNIQUE CHECK (btrim(codigo) <> '')
);

CREATE TABLE lote (
    lote_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo varchar(50) NOT NULL UNIQUE CHECK (btrim(codigo) <> ''),
    producto text NOT NULL CHECK (btrim(producto) <> '')
);

CREATE TABLE ciclo_esterilizacion (
    ciclo_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lote_id bigint NOT NULL UNIQUE
        REFERENCES lote (lote_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    autoclave_id bigint NOT NULL
        REFERENCES autoclave (autoclave_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    inicio timestamptz NOT NULL,
    fin timestamptz,
    temperatura_minima numeric(7, 3) NOT NULL,
    temperatura_maxima numeric(7, 3) NOT NULL,
    presion_minima numeric(7, 3) NOT NULL,
    presion_maxima numeric(7, 3) NOT NULL,
    CHECK (fin IS NULL OR fin > inicio),
    CHECK (temperatura_minima <= temperatura_maxima),
    CHECK (presion_minima >= 0 AND presion_minima <= presion_maxima)
);

CREATE TABLE lectura (
    lectura_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ciclo_id bigint NOT NULL
        REFERENCES ciclo_esterilizacion (ciclo_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    fecha_hora timestamptz NOT NULL,
    temperatura numeric(7, 3) NOT NULL,
    presion numeric(7, 3) NOT NULL CHECK (presion >= 0),
    UNIQUE (ciclo_id, fecha_hora)
);
```

`fin` admite `NULL` para representar un ciclo abierto. La relación única con
`lote` aplica el alcance de un ciclo por lote. `RESTRICT` evita una eliminación
accidental de trazabilidad. La fecha de una lectura depende de otra fila, por
lo que el script usa triggers en ambos sentidos; esa regla no corresponde a un
`CHECK`. Clasificación, estado y agregados se calculan al consultar.

Referencia: [constraints de PostgreSQL 18](https://www.postgresql.org/docs/18/ddl-constraints.html).

## 2. Consulta analítica

Primero se consolida cada ciclo y después cada autoclave/mes. De ese modo, la
cantidad de lecturas no multiplica la cantidad de lotes.

```sql
SET search_path TO control_esterilizacion, public;

WITH metricas_ciclo AS (
    SELECT
        ciclo.autoclave_id,
        ciclo.ciclo_id,
        date_trunc('month', ciclo.inicio) AS mes,
        sum(lectura.temperatura) AS suma_temperatura,
        count(*) AS cantidad_lecturas,
        count(*) FILTER (
            WHERE lectura.temperatura NOT BETWEEN
                    ciclo.temperatura_minima AND ciclo.temperatura_maxima
               OR lectura.presion NOT BETWEEN
                    ciclo.presion_minima AND ciclo.presion_maxima
        ) AS cantidad_fuera_rango
    FROM lectura
    JOIN ciclo_esterilizacion AS ciclo
      ON ciclo.ciclo_id = lectura.ciclo_id
    GROUP BY ciclo.autoclave_id, ciclo.ciclo_id, date_trunc('month', ciclo.inicio)
)
SELECT
    autoclave.codigo,
    metricas.mes,
    count(*) AS lotes_procesados,
    round(
        sum(metricas.suma_temperatura)
        / NULLIF(sum(metricas.cantidad_lecturas), 0),
        3
    ) AS temperatura_promedio,
    sum(metricas.cantidad_fuera_rango) AS lecturas_fuera_rango,
    round(
        count(*) FILTER (WHERE metricas.cantidad_fuera_rango = 0) * 100.0
        / NULLIF(count(*), 0),
        2
    ) AS porcentaje_lotes_aprobados
FROM metricas_ciclo AS metricas
JOIN autoclave ON autoclave.autoclave_id = metricas.autoclave_id
GROUP BY autoclave.autoclave_id, autoclave.codigo, metricas.mes
ORDER BY autoclave.codigo, metricas.mes;
```

`NULLIF(denominador, 0)` devuelve `NULL` ante un denominador cero y evita una
excepción. El agrupamiento actual no genera grupos vacíos, pero la protección
mantiene correctas las expresiones si la consulta cambia.

## 3. Índices y plan de ejecución

`autoclave_id` y `fecha_hora` pertenecen a tablas distintas, por lo que un
único índice no puede cubrir el filtro sin desnormalizar. Propongo:

```sql
SET search_path TO control_esterilizacion, public;

CREATE INDEX ciclo_autoclave_inicio_idx
    ON ciclo_esterilizacion (autoclave_id, inicio DESC)
    INCLUDE (ciclo_id, lote_id, fin);

CREATE UNIQUE INDEX lectura_ciclo_fecha_idx
    ON lectura (ciclo_id, fecha_hora);

CREATE INDEX lectura_fecha_ciclo_idx
    ON lectura (fecha_hora, ciclo_id);
```

El primero reduce los ciclos candidatos por autoclave. El índice único sirve
cuando el plan parte de esos ciclos; el tercero favorece rangos temporales
globales. Mantendría los tres únicamente si los planes y el costo de escritura
lo justifican.

```sql
ANALYZE ciclo_esterilizacion;
ANALYZE lectura;

EXPLAIN (ANALYZE, BUFFERS)
SELECT lectura.*
FROM lectura
JOIN ciclo_esterilizacion AS ciclo
  ON ciclo.ciclo_id = lectura.ciclo_id
WHERE ciclo.autoclave_id = $1
  AND lectura.fecha_hora >= $2
  AND lectura.fecha_hora < $3
ORDER BY lectura.fecha_hora;
```

Compararía filas estimadas/reales, método de join, scans, ordenamiento, tiempo y
buffers. PostgreSQL puede preferir `Seq Scan` en tablas pequeñas, filtros poco
selectivos o cuando el acceso aleatorio al índice y heap cuesta más que una
lectura secuencial.

Referencias: [índices multicolumna](https://www.postgresql.org/docs/18/indexes-multicolumn.html) y [EXPLAIN](https://www.postgresql.org/docs/18/sql-explain.html).

## 4. Concurrencia y transacciones

Para un cierre simple basta una actualización condicional atómica en
`READ COMMITTED`:

```sql
SET search_path TO control_esterilizacion, public;

BEGIN;

UPDATE ciclo_esterilizacion
SET fin = $2
WHERE ciclo_id = $1
  AND fin IS NULL
  AND $2 > inicio
RETURNING ciclo_id, inicio, fin;

COMMIT;
```

`UPDATE` bloquea la fila. Un proceso la cierra; el segundo espera y, al volver
a evaluar `fin IS NULL`, actualiza cero filas. La aplicación interpreta ese
resultado como “ciclo ya cerrado”. Si el cierre exige leer y calcular antes,
usaría `SELECT ... FOR UPDATE` en la misma transacción. Reservaría
`SERIALIZABLE` para invariantes entre varias filas y reintentaría SQLSTATE
`40001`.

Referencia: [bloqueo de filas con SELECT](https://www.postgresql.org/docs/18/sql-select.html#SQL-FOR-UPDATE-SHARE).

## 5. Particionamiento y operación

Particionaría `lectura` por rango de `fecha_hora` cuando el volumen, las
consultas y la retención fueran principalmente temporales. Para una tabla
pequeña, la cantidad adicional de objetos y el costo de planificación no se
justifican. Usaría particiones mensuales con límites inferior inclusivo y
superior exclusivo:

```sql
SET search_path TO control_esterilizacion, public;

CREATE TABLE lectura_particionada (
    lectura_id bigint GENERATED ALWAYS AS IDENTITY,
    ciclo_id bigint NOT NULL REFERENCES ciclo_esterilizacion (ciclo_id),
    fecha_hora timestamptz NOT NULL,
    temperatura numeric(7, 3) NOT NULL,
    presion numeric(7, 3) NOT NULL CHECK (presion >= 0),
    PRIMARY KEY (fecha_hora, lectura_id),
    UNIQUE (ciclo_id, fecha_hora)
) PARTITION BY RANGE (fecha_hora);

CREATE TABLE lectura_2026_07 PARTITION OF lectura_particionada
FOR VALUES FROM ('2026-07-01T00:00:00-05:00')
         TO ('2026-08-01T00:00:00-05:00');
```

Crearía particiones futuras antes de recibir datos y aplicaría retención con
`DETACH PARTITION` antes de archivar o eliminar. Dos prácticas operativas
relevantes son:

1. ajustar autovacuum/autoanalyze por tabla o partición y vigilar tuplas
   muertas, antigüedad de XID y estadísticas del padre particionado;
2. monitorear `pg_stat_user_tables`, `pg_stat_activity`,
   `pg_stat_progress_vacuum`, bloqueos, WAL, latencia y planes críticos.

Referencias: [particionamiento declarativo](https://www.postgresql.org/docs/18/ddl-partitioning.html), [vacuum rutinario](https://www.postgresql.org/docs/18/routine-vacuuming.html) y [monitoreo](https://www.postgresql.org/docs/18/monitoring.html).
