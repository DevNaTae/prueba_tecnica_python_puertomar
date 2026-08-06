import argparse
import logging
from pathlib import Path

from src.domain.exceptions import (
    DomainValidationError,
    InputDataError,
    PersistenceError,
)
from src.infrastructure.json_files import load_batch, write_report
from src.repositories.postgres import PostgresSterilizationRepository
from src.services.report_service import ReportService

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Genera el reporte de ciclos de esterilización desde JSON."
    )
    parser.add_argument("input", type=Path, help="Archivo JSON de entrada")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("salida/reporte.json"),
        help="Destino del reporte (predeterminado: salida/reporte.json)",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persiste la carga en PostgreSQL usando DATABASE_URL",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        batch = load_batch(args.input)
        report = ReportService().process(batch)
        if args.persist:
            PostgresSterilizationRepository().save_batch(batch)
        write_report(report, args.output)
        logger.info("Reporte escrito en %s", args.output)
        return 0
    except (InputDataError, DomainValidationError) as error:
        logger.error("No se pudo procesar la entrada: %s", error)
        return 2
    except (PersistenceError, OSError) as error:
        logger.error("No se pudo completar la operación: %s", error)
        return 3


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    raise SystemExit(main())
