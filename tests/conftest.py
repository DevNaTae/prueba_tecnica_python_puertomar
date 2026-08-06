from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from src.schemas.sterilization import BatchInput, LotReport
from src.services.report_service import ReportService


@pytest.fixture
def lote_valido() -> dict[str, Any]:
    return {
        "lote_id": "PRUEBA-LOTE-01",
        "producto": "Conserva para pruebas",
        "autoclave": "AUTOCLAVE-PRUEBA",
        "inicio": "2026-07-15T06:00:00-05:00",
        "fin": "2026-07-15T07:00:00-05:00",
        "temperatura_minima": 115.5,
        "temperatura_maxima": 122.5,
        "presion_minima": 1.1,
        "presion_maxima": 1.7,
        "lecturas": [
            {
                "fecha_hora": "2026-07-15T06:15:00-05:00",
                "temperatura": 117.0,
                "presion": 1.3,
            },
            {
                "fecha_hora": "2026-07-15T06:45:00-05:00",
                "temperatura": 121.0,
                "presion": 1.5,
            },
        ],
    }


@pytest.fixture
def copiar_lote(lote_valido: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    return lambda: deepcopy(lote_valido)


@pytest.fixture
def procesar_lote() -> Callable[[dict[str, Any]], LotReport]:
    def procesar(datos: dict[str, Any]) -> LotReport:
        entrada = BatchInput.model_validate({"lotes": [datos]})
        return ReportService().process(entrada).lotes[0]

    return procesar
