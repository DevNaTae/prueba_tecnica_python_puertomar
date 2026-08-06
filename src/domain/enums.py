from enum import StrEnum


class ReadingClassification(StrEnum):
    NORMAL = "NORMAL"
    TEMPERATURE_ALERT = "ALERTA_TEMPERATURA"
    PRESSURE_ALERT = "ALERTA_PRESION"
    MULTIPLE_ALERT = "ALERTA_MULTIPLE"


class LotStatus(StrEnum):
    APPROVED = "APROBADO"
    OBSERVED = "OBSERVADO"
    REJECTED = "RECHAZADO"
