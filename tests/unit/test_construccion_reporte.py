from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from src.domain.enums import LotStatus
from src.schemas.sterilization import BatchInput, LotReport
from src.services.report_service import ReportService, status_from_alert_count


def test_calcula_resumen_de_un_lote_conforme(
    lote_valido: dict[str, Any],
    procesar_lote: Callable[[dict[str, Any]], LotReport],
) -> None:
    reporte = procesar_lote(lote_valido)

    assert reporte.estado is LotStatus.APPROVED
    assert reporte.resumen.total_lecturas == 2
    assert reporte.resumen.temperatura_promedio == 119.0
    assert reporte.resumen.presion_promedio == 1.4
    assert reporte.resumen.porcentaje_cumplimiento == 100.0
    assert reporte.alertas == []


@pytest.mark.parametrize(
    ("cantidad_alertas", "estado"),
    [
        (0, LotStatus.APPROVED),
        (1, LotStatus.OBSERVED),
        (2, LotStatus.OBSERVED),
        (3, LotStatus.REJECTED),
        (9, LotStatus.REJECTED),
    ],
)
def test_calcula_estado_por_cantidad_de_alertas(
    cantidad_alertas: int,
    estado: LotStatus,
) -> None:
    assert status_from_alert_count(cantidad_alertas) is estado


def test_ordena_lotes_por_fecha_de_inicio(lote_valido: dict[str, Any]) -> None:
    lote_posterior = deepcopy(lote_valido)
    lote_posterior["lote_id"] = "PRUEBA-LOTE-02"
    lote_posterior["inicio"] = "2026-07-16T06:00:00-05:00"
    lote_posterior["fin"] = "2026-07-16T07:00:00-05:00"
    for lectura in lote_posterior["lecturas"]:
        lectura["fecha_hora"] = lectura["fecha_hora"].replace("07-15", "07-16")

    entrada = BatchInput.model_validate({"lotes": [lote_posterior, lote_valido]})

    reporte = ReportService().process(entrada)

    assert [lote.lote_id for lote in reporte.lotes] == [
        "PRUEBA-LOTE-01",
        "PRUEBA-LOTE-02",
    ]
