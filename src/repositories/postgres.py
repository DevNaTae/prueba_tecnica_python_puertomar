import logging

import psycopg

from src.database import open_connection
from src.domain.exceptions import PersistenceError
from src.schemas.sterilization import BatchInput, LotInput

logger = logging.getLogger(__name__)


class PostgresSterilizationRepository:
    """Persistencia idempotente de una carga completa en una transacción."""

    def __init__(self, connection: psycopg.Connection | None = None) -> None:
        self._connection = connection

    def save_batch(self, batch: BatchInput) -> None:
        try:
            if self._connection is not None:
                for lot in batch.lotes:
                    self._save_lot(self._connection, lot)
                return

            with open_connection() as connection:
                for lot in batch.lotes:
                    self._save_lot(connection, lot)
        except psycopg.Error as error:
            logger.exception("No fue posible persistir el lote de entrada")
            raise PersistenceError(
                "No se pudo guardar la información en PostgreSQL"
            ) from error

    @staticmethod
    def _save_lot(connection: psycopg.Connection, lot: LotInput) -> None:
        autoclave_id = connection.execute(
            """
            INSERT INTO control_esterilizacion.autoclave (codigo)
            VALUES (%s)
            ON CONFLICT (codigo) DO UPDATE SET codigo = EXCLUDED.codigo
            RETURNING autoclave_id
            """,
            (lot.autoclave,),
        ).fetchone()[0]
        lot_id = connection.execute(
            """
            INSERT INTO control_esterilizacion.lote (codigo, producto)
            VALUES (%s, %s)
            ON CONFLICT (codigo) DO UPDATE
            SET producto = EXCLUDED.producto
            RETURNING lote_id
            """,
            (lot.lote_id, lot.producto),
        ).fetchone()[0]
        cycle_id: int = connection.execute(
            """
            INSERT INTO control_esterilizacion.ciclo_esterilizacion (
                lote_id, autoclave_id, inicio, fin,
                temperatura_minima, temperatura_maxima,
                presion_minima, presion_maxima
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lote_id) DO UPDATE SET
                autoclave_id = EXCLUDED.autoclave_id,
                inicio = EXCLUDED.inicio,
                fin = EXCLUDED.fin,
                temperatura_minima = EXCLUDED.temperatura_minima,
                temperatura_maxima = EXCLUDED.temperatura_maxima,
                presion_minima = EXCLUDED.presion_minima,
                presion_maxima = EXCLUDED.presion_maxima
            RETURNING ciclo_id
            """,
            (
                lot_id,
                autoclave_id,
                lot.inicio,
                lot.fin,
                lot.temperatura_minima,
                lot.temperatura_maxima,
                lot.presion_minima,
                lot.presion_maxima,
            ),
        ).fetchone()[0]

        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO control_esterilizacion.lectura (
                    ciclo_id, fecha_hora, temperatura, presion
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (ciclo_id, fecha_hora) DO UPDATE SET
                    temperatura = EXCLUDED.temperatura,
                    presion = EXCLUDED.presion
                """,
                [
                    (
                        cycle_id,
                        reading.fecha_hora,
                        reading.temperatura,
                        reading.presion,
                    )
                    for reading in lot.lecturas
                ],
            )
