import psycopg

from src.config import get_settings


def open_connection(conninfo: str | None = None) -> psycopg.Connection:
    """Abre una conexión; el llamador controla su ciclo de vida."""
    settings = get_settings()
    database_url = conninfo
    if database_url is None and settings.database_url is not None:
        database_url = settings.database_url.get_secret_value()
    if database_url is None:
        raise RuntimeError("Configure DATABASE_URL para usar PostgreSQL")

    return psycopg.connect(database_url, connect_timeout=5)
