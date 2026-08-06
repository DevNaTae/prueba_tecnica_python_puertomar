from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from src.domain.enums import LotStatus, ReadingClassification


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ReadingInput(StrictModel):
    fecha_hora: AwareDatetime
    temperatura: float = Field(allow_inf_nan=False)
    presion: float = Field(allow_inf_nan=False)


class LotInput(StrictModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: AwareDatetime
    fin: AwareDatetime
    temperatura_minima: float = Field(allow_inf_nan=False)
    temperatura_maxima: float = Field(allow_inf_nan=False)
    presion_minima: float = Field(allow_inf_nan=False)
    presion_maxima: float = Field(allow_inf_nan=False)
    lecturas: list[ReadingInput] = Field(min_length=1)

    @field_validator("lote_id", "producto", "autoclave")
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("no puede estar vacío")
        return value


class BatchInput(StrictModel):
    lotes: list[LotInput] = Field(min_length=1)


class AlertDetail(StrictModel):
    fecha_hora: AwareDatetime
    temperatura: float
    presion: float
    clasificacion: ReadingClassification


class LotSummary(StrictModel):
    total_lecturas: int
    lecturas_normales: int
    lecturas_con_alerta: int
    temperatura_promedio: float
    temperatura_minima: float
    temperatura_maxima: float
    presion_promedio: float
    presion_minima: float
    presion_maxima: float
    porcentaje_cumplimiento: float


class LotReport(StrictModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: AwareDatetime
    fin: AwareDatetime
    estado: LotStatus
    resumen: LotSummary
    alertas: list[AlertDetail]


class GlobalSummary(StrictModel):
    total_lotes: int
    lotes_aprobados: int
    lotes_observados: int
    lotes_rechazados: int


class ReportResponse(StrictModel):
    resumen_general: GlobalSummary
    lotes: list[LotReport]
