import json
from pathlib import Path

from src.main import main


def test_cli_genera_el_reporte(
    tmp_path: Path,
    lote_valido: dict,
) -> None:
    entrada = tmp_path / "entrada.json"
    salida = tmp_path / "resultado.json"
    entrada.write_text(json.dumps({"lotes": [lote_valido]}), encoding="utf-8")

    codigo = main([str(entrada), "--output", str(salida)])

    assert codigo == 0
    assert (
        json.loads(salida.read_text(encoding="utf-8"))["lotes"][0]["estado"]
        == "APROBADO"
    )


def test_cli_controla_un_archivo_inexistente(tmp_path: Path) -> None:
    codigo = main([str(tmp_path / "no-existe.json")])

    assert codigo == 2
