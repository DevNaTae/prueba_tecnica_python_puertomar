import json
from pathlib import Path

import pytest

from src.domain.exceptions import InputDataError
from src.infrastructure.json_files import load_batch, write_report
from src.schemas.sterilization import BatchInput
from src.services.report_service import ReportService


def test_informa_la_ubicacion_de_un_json_mal_formado(tmp_path: Path) -> None:
    entrada = tmp_path / "entrada-invalida.json"
    entrada.write_text('{"lotes": [', encoding="utf-8")

    with pytest.raises(InputDataError, match="JSON inválido en línea"):
        load_batch(entrada)


def test_archivos_de_ejemplo_forman_un_par_consistente() -> None:
    entrada = load_batch(Path("samples/input.json"))
    esperado = json.loads(Path("samples/output.json").read_text(encoding="utf-8"))

    generado = ReportService().process(entrada).model_dump(mode="json")

    assert generado == esperado


def test_escribe_json_en_un_directorio_nuevo(
    tmp_path: Path,
    lote_valido: dict,
) -> None:
    reporte = ReportService().process(
        BatchInput.model_validate({"lotes": [lote_valido]})
    )
    destino = tmp_path / "reportes" / "resultado.json"

    write_report(reporte, destino)

    assert (
        json.loads(destino.read_text(encoding="utf-8"))["lotes"][0]["estado"]
        == "APROBADO"
    )
