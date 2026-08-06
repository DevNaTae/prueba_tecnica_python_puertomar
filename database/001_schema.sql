BEGIN;

CREATE SCHEMA IF NOT EXISTS control_esterilizacion;

CREATE TABLE IF NOT EXISTS control_esterilizacion.autoclave (
    autoclave_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo varchar(30) NOT NULL,
    CONSTRAINT autoclave_codigo_unico UNIQUE (codigo),
    CONSTRAINT autoclave_codigo_requerido CHECK (btrim(codigo) <> '')
);

CREATE TABLE IF NOT EXISTS control_esterilizacion.lote (
    lote_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo varchar(50) NOT NULL,
    producto text NOT NULL,
    CONSTRAINT lote_codigo_unico UNIQUE (codigo),
    CONSTRAINT lote_codigo_requerido CHECK (btrim(codigo) <> ''),
    CONSTRAINT lote_producto_requerido CHECK (btrim(producto) <> '')
);

CREATE TABLE IF NOT EXISTS control_esterilizacion.ciclo_esterilizacion (
    ciclo_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lote_id bigint NOT NULL,
    autoclave_id bigint NOT NULL,
    inicio timestamptz NOT NULL,
    fin timestamptz,
    temperatura_minima numeric(7, 3) NOT NULL,
    temperatura_maxima numeric(7, 3) NOT NULL,
    presion_minima numeric(7, 3) NOT NULL,
    presion_maxima numeric(7, 3) NOT NULL,
    CONSTRAINT ciclo_lote_unico UNIQUE (lote_id),
    CONSTRAINT ciclo_lote_fk FOREIGN KEY (lote_id)
        REFERENCES control_esterilizacion.lote (lote_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT ciclo_autoclave_fk FOREIGN KEY (autoclave_id)
        REFERENCES control_esterilizacion.autoclave (autoclave_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT ciclo_intervalo_valido CHECK (fin IS NULL OR fin > inicio),
    CONSTRAINT ciclo_temperatura_valida
        CHECK (temperatura_minima <= temperatura_maxima),
    CONSTRAINT ciclo_presion_valida
        CHECK (presion_minima >= 0 AND presion_minima <= presion_maxima)
);

CREATE TABLE IF NOT EXISTS control_esterilizacion.lectura (
    lectura_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ciclo_id bigint NOT NULL,
    fecha_hora timestamptz NOT NULL,
    temperatura numeric(7, 3) NOT NULL,
    presion numeric(7, 3) NOT NULL,
    CONSTRAINT lectura_ciclo_fk FOREIGN KEY (ciclo_id)
        REFERENCES control_esterilizacion.ciclo_esterilizacion (ciclo_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT lectura_presion_no_negativa CHECK (presion >= 0),
    CONSTRAINT lectura_instante_unico UNIQUE (ciclo_id, fecha_hora)
);

-- Localiza primero los ciclos de una autoclave y conserva el orden temporal.
CREATE INDEX IF NOT EXISTS ciclo_autoclave_inicio_idx
    ON control_esterilizacion.ciclo_esterilizacion (
        autoclave_id,
        inicio DESC
    )
    INCLUDE (ciclo_id, lote_id, fin);

-- Complementa el índice UNIQUE (ciclo_id, fecha_hora) para rangos globales.
CREATE INDEX IF NOT EXISTS lectura_fecha_ciclo_idx
    ON control_esterilizacion.lectura (fecha_hora, ciclo_id);

CREATE OR REPLACE FUNCTION control_esterilizacion.validar_fecha_lectura()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, control_esterilizacion
AS $$
DECLARE
    ciclo_inicio timestamptz;
    ciclo_fin timestamptz;
BEGIN
    SELECT inicio, fin
      INTO ciclo_inicio, ciclo_fin
     FROM control_esterilizacion.ciclo_esterilizacion
     WHERE ciclo_id = NEW.ciclo_id
       FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El ciclo % no existe', NEW.ciclo_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF NEW.fecha_hora < ciclo_inicio
       OR (ciclo_fin IS NOT NULL AND NEW.fecha_hora > ciclo_fin) THEN
        RAISE EXCEPTION 'La lectura debe pertenecer al intervalo del ciclo'
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS validar_fecha_lectura_trg
    ON control_esterilizacion.lectura;
CREATE TRIGGER validar_fecha_lectura_trg
BEFORE INSERT OR UPDATE OF ciclo_id, fecha_hora
ON control_esterilizacion.lectura
FOR EACH ROW
EXECUTE FUNCTION control_esterilizacion.validar_fecha_lectura();

CREATE OR REPLACE FUNCTION control_esterilizacion.proteger_intervalo_ciclo()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, control_esterilizacion
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM control_esterilizacion.lectura AS lectura
         WHERE lectura.ciclo_id = NEW.ciclo_id
           AND (
               lectura.fecha_hora < NEW.inicio
               OR (NEW.fin IS NOT NULL AND lectura.fecha_hora > NEW.fin)
           )
    ) THEN
        RAISE EXCEPTION 'El intervalo dejaría lecturas fuera del ciclo'
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS proteger_intervalo_ciclo_trg
    ON control_esterilizacion.ciclo_esterilizacion;
CREATE TRIGGER proteger_intervalo_ciclo_trg
BEFORE UPDATE OF inicio, fin
ON control_esterilizacion.ciclo_esterilizacion
FOR EACH ROW
EXECUTE FUNCTION control_esterilizacion.proteger_intervalo_ciclo();

COMMENT ON SCHEMA control_esterilizacion IS
    'Persistencia normalizada para lotes, ciclos, autoclaves y lecturas.';

COMMIT;
