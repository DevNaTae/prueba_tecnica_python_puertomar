-- Lotes con alertas, total de lecturas alertadas y máxima desviación térmica.
WITH lectura_clasificada AS (
    SELECT
        lote.codigo AS lote,
        autoclave.codigo AS autoclave,
        lectura.temperatura,
        ciclo.temperatura_minima,
        ciclo.temperatura_maxima,
        (
            lectura.temperatura NOT BETWEEN
                ciclo.temperatura_minima AND ciclo.temperatura_maxima
            OR lectura.presion NOT BETWEEN
                ciclo.presion_minima AND ciclo.presion_maxima
        ) AS tiene_alerta
    FROM control_esterilizacion.lectura AS lectura
    JOIN control_esterilizacion.ciclo_esterilizacion AS ciclo
      ON ciclo.ciclo_id = lectura.ciclo_id
    JOIN control_esterilizacion.lote AS lote
      ON lote.lote_id = ciclo.lote_id
    JOIN control_esterilizacion.autoclave AS autoclave
      ON autoclave.autoclave_id = ciclo.autoclave_id
)
SELECT
    lote,
    autoclave,
    count(*) FILTER (WHERE tiene_alerta) AS cantidad_alertas,
    round(
        max(
            greatest(
                temperatura - temperatura_maxima,
                temperatura_minima - temperatura,
                0
            )
        ),
        3
    ) AS mayor_desviacion_temperatura
FROM lectura_clasificada
GROUP BY lote, autoclave
HAVING count(*) FILTER (WHERE tiene_alerta) > 0
ORDER BY cantidad_alertas DESC, lote;
