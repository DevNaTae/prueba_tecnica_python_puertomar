from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from src.domain.exceptions import DomainValidationError
from src.schemas.sterilization import BatchInput, LotReport


def test_rechaza_un_campo_obligatorio_vacio(
    copiar_lote: Callable[[], dict[str, Any]],
) -> None:
    lote = copiar_lote()
    lote["producto"] = "   "

    with pytest.raises(ValidationError, match="no puede estar vacío"):
        BatchInput.model_validate({"lotes": [lote]})


def test_rechaza_nombres_alternativos_del_contrato(
    lote_valido: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        BatchInput.model_validate({"lots": [lote_valido]})


def test_rechaza_fecha_final_igual_al_inicio(
    copiar_lote: Callable[[], dict[str, Any]],
    procesar_lote: Callable[[dict[str, Any]], LotReport],
) -> None:
    lote = copiar_lote()
    lote["fin"] = lote["inicio"]

    with pytest.raises(DomainValidationError, match="fin debe ser posterior"):
        procesar_lote(lote)


@pytest.mark.parametrize(
    ("campo_minimo", "campo_maximo", "mensaje"),
    [
        ("temperatura_minima", "temperatura_maxima", "temperatura_min"),
        ("presion_minima", "presion_maxima", "presion_min"),
    ],
)
def test_rechaza_un_rango_invertido(
    copiar_lote: Callable[[], dict[str, Any]],
    procesar_lote: Callable[[dict[str, Any]], LotReport],
    campo_minimo: str,
    campo_maximo: str,
    mensaje: str,
) -> None:
    lote = copiar_lote()
    lote[campo_minimo] = float(lote[campo_maximo]) + 0.1

    with pytest.raises(DomainValidationError, match=mensaje):
        procesar_lote(lote)


def test_rechaza_una_lectura_anterior_al_ciclo(
    copiar_lote: Callable[[], dict[str, Any]],
    procesar_lote: Callable[[dict[str, Any]], LotReport],
) -> None:
    lote = copiar_lote()
    lote["lecturas"][0]["fecha_hora"] = "2026-07-15T05:59:59-05:00"

    with pytest.raises(DomainValidationError, match="fuera del ciclo"):
        procesar_lote(lote)


def test_rechaza_presion_negativa(
    copiar_lote: Callable[[], dict[str, Any]],
    procesar_lote: Callable[[dict[str, Any]], LotReport],
) -> None:
    lote = copiar_lote()
    lote["lecturas"][0]["presion"] = -0.1

    with pytest.raises(DomainValidationError, match="presión no puede ser negativa"):
        procesar_lote(lote)
