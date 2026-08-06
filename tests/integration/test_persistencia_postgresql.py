import os
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import psycopg
import pytest

from src.repositories.postgres import PostgresSterilizationRepository
from src.schemas.sterilization import BatchInput


@pytest.mark.integration
def test_persiste_un_ciclo_completo_de_forma_idempotente(
    copiar_lote: Callable[[], dict[str, Any]],
) -> None:
    conninfo = os.getenv("TEST_DATABASE_URL")
    if not conninfo:
        pytest.skip("TEST_DATABASE_URL no está configurada")

    lote = copiar_lote()
    lote["lote_id"] = f"INTEGRACION-{uuid4()}"
    entrada = BatchInput.model_validate({"lotes": [lote]})

    with psycopg.connect(conninfo) as conexion:
        repositorio = PostgresSterilizationRepository(conexion)
        repositorio.save_batch(entrada)
        repositorio.save_batch(entrada)

        total_lecturas, total_alertas = conexion.execute(
            """
            SELECT
                count(*),
                count(*) FILTER (
                    WHERE lectura.temperatura NOT BETWEEN
                        ciclo.temperatura_minima AND ciclo.temperatura_maxima
                       OR lectura.presion NOT BETWEEN
                        ciclo.presion_minima AND ciclo.presion_maxima
                )
            FROM control_esterilizacion.lectura AS lectura
            JOIN control_esterilizacion.ciclo_esterilizacion AS ciclo
              ON ciclo.ciclo_id = lectura.ciclo_id
            JOIN control_esterilizacion.lote AS lote
              ON lote.lote_id = ciclo.lote_id
            WHERE lote.codigo = %s
            """,
            (lote["lote_id"],),
        ).fetchone()

        assert (total_lecturas, total_alertas) == (2, 0)
        conexion.rollback()


@pytest.mark.integration
def test_base_rechaza_lectura_fuera_del_intervalo(
    copiar_lote: Callable[[], dict[str, Any]],
) -> None:
    conninfo = os.getenv("TEST_DATABASE_URL")
    if not conninfo:
        pytest.skip("TEST_DATABASE_URL no está configurada")

    lote = copiar_lote()
    lote["lote_id"] = f"INTEGRACION-{uuid4()}"
    entrada = BatchInput.model_validate({"lotes": [lote]})

    with psycopg.connect(conninfo) as conexion:
        PostgresSterilizationRepository(conexion).save_batch(entrada)
        ciclo_id = conexion.execute(
            """
            SELECT ciclo.ciclo_id
            FROM control_esterilizacion.ciclo_esterilizacion AS ciclo
            JOIN control_esterilizacion.lote AS lote
              ON lote.lote_id = ciclo.lote_id
            WHERE lote.codigo = %s
            """,
            (lote["lote_id"],),
        ).fetchone()[0]

        with (
            pytest.raises(psycopg.errors.CheckViolation),
            conexion.transaction(),
        ):
            conexion.execute(
                """
                INSERT INTO control_esterilizacion.lectura (
                    ciclo_id, fecha_hora, temperatura, presion
                )
                VALUES (%s, %s::timestamptz - interval '1 second', %s, %s)
                """,
                (ciclo_id, lote["inicio"], 118.0, 1.4),
            )

        conexion.rollback()
