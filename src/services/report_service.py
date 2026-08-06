import logging
from statistics import fmean

from src.domain.enums import LotStatus, ReadingClassification
from src.domain.exceptions import DomainValidationError
from src.schemas.sterilization import (
    AlertDetail,
    BatchInput,
    GlobalSummary,
    LotInput,
    LotReport,
    LotSummary,
    ReadingInput,
    ReportResponse,
)

logger = logging.getLogger(__name__)


def classify_reading(
    reading: ReadingInput,
    lot: LotInput,
) -> ReadingClassification:
    temperature_alert = not (
        lot.temperatura_minima <= reading.temperatura <= lot.temperatura_maxima
    )
    pressure_alert = not (lot.presion_minima <= reading.presion <= lot.presion_maxima)

    if temperature_alert and pressure_alert:
        return ReadingClassification.MULTIPLE_ALERT
    if temperature_alert:
        return ReadingClassification.TEMPERATURE_ALERT
    if pressure_alert:
        return ReadingClassification.PRESSURE_ALERT
    return ReadingClassification.NORMAL


def status_from_alert_count(alert_count: int) -> LotStatus:
    if alert_count == 0:
        return LotStatus.APPROVED
    if alert_count <= 2:
        return LotStatus.OBSERVED
    return LotStatus.REJECTED


class ReportService:
    """Valida los lotes y construye un reporte determinista."""

    def process(self, batch: BatchInput) -> ReportResponse:
        reports = [self._process_lot(lot) for lot in batch.lotes]
        reports.sort(key=lambda report: report.inicio)

        summary = GlobalSummary(
            total_lotes=len(reports),
            lotes_aprobados=sum(r.estado is LotStatus.APPROVED for r in reports),
            lotes_observados=sum(r.estado is LotStatus.OBSERVED for r in reports),
            lotes_rechazados=sum(r.estado is LotStatus.REJECTED for r in reports),
        )
        logger.info("Reporte generado para %s lote(s)", len(reports))
        return ReportResponse(resumen_general=summary, lotes=reports)

    def _process_lot(self, lot: LotInput) -> LotReport:
        self._validate_lot(lot)
        classifications = [classify_reading(reading, lot) for reading in lot.lecturas]
        alert_count = sum(
            classification is not ReadingClassification.NORMAL
            for classification in classifications
        )
        temperatures = [reading.temperatura for reading in lot.lecturas]
        pressures = [reading.presion for reading in lot.lecturas]
        total = len(lot.lecturas)

        alerts = [
            AlertDetail(
                fecha_hora=reading.fecha_hora,
                temperatura=self._round_measurement(reading.temperatura),
                presion=self._round_measurement(reading.presion),
                clasificacion=classification,
            )
            for reading, classification in zip(
                lot.lecturas, classifications, strict=True
            )
            if classification is not ReadingClassification.NORMAL
        ]

        summary = LotSummary(
            total_lecturas=total,
            lecturas_normales=total - alert_count,
            lecturas_con_alerta=alert_count,
            temperatura_promedio=self._round_measurement(fmean(temperatures)),
            temperatura_minima=self._round_measurement(min(temperatures)),
            temperatura_maxima=self._round_measurement(max(temperatures)),
            presion_promedio=self._round_measurement(fmean(pressures)),
            presion_minima=self._round_measurement(min(pressures)),
            presion_maxima=self._round_measurement(max(pressures)),
            porcentaje_cumplimiento=round((total - alert_count) * 100 / total, 2),
        )
        status = status_from_alert_count(alert_count)
        logger.info(
            "Lote %s procesado: %s alerta(s), estado %s",
            lot.lote_id,
            alert_count,
            status,
        )
        return LotReport(
            lote_id=lot.lote_id,
            producto=lot.producto,
            autoclave=lot.autoclave,
            inicio=lot.inicio,
            fin=lot.fin,
            estado=status,
            resumen=summary,
            alertas=alerts,
        )

    @staticmethod
    def _validate_lot(lot: LotInput) -> None:
        prefix = f"Lote '{lot.lote_id}'"
        if lot.fin <= lot.inicio:
            raise DomainValidationError(
                f"{prefix}: la fecha de fin debe ser posterior a la de inicio"
            )
        if lot.temperatura_minima > lot.temperatura_maxima:
            raise DomainValidationError(
                f"{prefix}: temperatura_min no puede superar temperatura_max"
            )
        if lot.presion_minima > lot.presion_maxima:
            raise DomainValidationError(
                f"{prefix}: presion_min no puede superar presion_max"
            )
        if lot.presion_minima < 0 or lot.presion_maxima < 0:
            raise DomainValidationError(
                f"{prefix}: los límites de presión no pueden ser negativos"
            )

        for index, reading in enumerate(lot.lecturas, start=1):
            if reading.presion < 0:
                raise DomainValidationError(
                    f"{prefix}, lectura {index}: la presión no puede ser negativa"
                )
            if not lot.inicio <= reading.fecha_hora <= lot.fin:
                raise DomainValidationError(
                    f"{prefix}, lectura {index}: fecha_hora está fuera del ciclo"
                )

    @staticmethod
    def _round_measurement(value: float) -> float:
        return round(value, 3)
