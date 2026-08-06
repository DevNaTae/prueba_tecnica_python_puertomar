import json
from pathlib import Path

from pydantic import ValidationError

from src.domain.exceptions import InputDataError
from src.schemas.sterilization import BatchInput, ReportResponse


def load_batch(path: Path) -> BatchInput:
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise InputDataError(f"No existe el archivo de entrada: {path}") from error
    except PermissionError as error:
        raise InputDataError(f"No se puede leer el archivo: {path}") from error
    except json.JSONDecodeError as error:
        raise InputDataError(
            f"JSON inválido en línea {error.lineno}, columna {error.colno}: {error.msg}"
        ) from error

    try:
        return BatchInput.model_validate(raw_data)
    except ValidationError as error:
        messages = "; ".join(
            f"{'.'.join(map(str, issue['loc']))}: {issue['msg']}"
            for issue in error.errors()
        )
        raise InputDataError(f"Entrada inválida: {messages}") from error


def write_report(report: ReportResponse, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
