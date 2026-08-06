from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from src import database


def test_abre_conexion_con_database_url_secreta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conexion = object()
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(database_url=SecretStr("dbname=ejemplo")),
    )
    monkeypatch.setattr(
        database.psycopg,
        "connect",
        lambda conninfo, **opciones: (conninfo, opciones, conexion),
    )

    conninfo, opciones, resultado = database.open_connection()

    assert conninfo == "dbname=ejemplo"
    assert opciones == {"connect_timeout": 5}
    assert resultado is conexion


def test_exige_configuracion_para_persistir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(database_url=None),
    )

    with pytest.raises(RuntimeError, match="Configure DATABASE_URL"):
        database.open_connection()
