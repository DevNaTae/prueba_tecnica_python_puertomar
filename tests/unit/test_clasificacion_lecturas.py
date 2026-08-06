from collections.abc import Callable
from typing import Any

import pytest

from src.domain.enums import ReadingClassification
from src.schemas.sterilization import LotReport


def test_clasifica_alerta_multiple(
    copiar_lote: Callable[[], dict[str, Any]],
    procesar_lote: Callable[[dict[str, Any]], LotReport],
) -> None:
    lote = copiar_lote()
    lote["lecturas"][0].update(temperatura=130.0, presion=2.2)

    reporte = procesar_lote(lote)

    assert reporte.alertas[0].clasificacion is ReadingClassification.MULTIPLE_ALERT


@pytest.mark.parametrize(
    ("campo", "valor", "clasificacion"),
    [
        ("temperatura", 130.0, ReadingClassification.TEMPERATURE_ALERT),
        ("presion", 2.2, ReadingClassification.PRESSURE_ALERT),
    ],
)
def test_distingue_alertas_individuales(
    copiar_lote: Callable[[], dict[str, Any]],
    procesar_lote: Callable[[dict[str, Any]], LotReport],
    campo: str,
    valor: float,
    clasificacion: ReadingClassification,
) -> None:
    lote = copiar_lote()
    lote["lecturas"][0][campo] = valor

    assert procesar_lote(lote).alertas[0].clasificacion is clasificacion


def test_considera_normales_los_limites_inclusivos(
    copiar_lote: Callable[[], dict[str, Any]],
    procesar_lote: Callable[[dict[str, Any]], LotReport],
) -> None:
    lote = copiar_lote()
    lote["lecturas"][0]["temperatura"] = lote["temperatura_minima"]
    lote["lecturas"][0]["presion"] = lote["presion_maxima"]

    assert procesar_lote(lote).resumen.lecturas_con_alerta == 0
