import importlib.resources
import logging
from typing import Any

from django.conf import settings
from django.db import connections
from django.db.backends.signals import connection_created

logger = logging.getLogger(__name__)


class SQLiteVectorExtensionError(RuntimeError):
    """Raised when the sqlite-vector extension cannot be loaded."""


def sqlite_vector_is_enabled() -> bool:
    return bool(getattr(settings, "SQLITE_VECTOR_ENABLED", True))


def sqlite_vector_is_required() -> bool:
    return bool(getattr(settings, "SQLITE_VECTOR_REQUIRED", True))


def get_sqlite_vector_extension_path() -> str:
    try:
        return str(importlib.resources.files("sqlite_vector.binaries") / "vector")
    except ModuleNotFoundError as exc:
        raise SQLiteVectorExtensionError(
            "sqliteai-vector is not installed. Install the sqliteai-vector package "
            "before using RAG vector search."
        ) from exc


def load_sqlite_vector_extension(dbapi_connection: Any) -> None:
    extension_path = get_sqlite_vector_extension_path()

    try:
        dbapi_connection.enable_load_extension(True)
        dbapi_connection.load_extension(extension_path)
    except Exception as exc:
        raise SQLiteVectorExtensionError(
            f"Could not load sqlite-vector extension from {extension_path}."
        ) from exc
    finally:
        try:
            dbapi_connection.enable_load_extension(False)
        except Exception:
            logger.exception("Could not disable SQLite extension loading.")


def load_sqlite_vector_for_connection(
    sender: Any, connection: Any, **kwargs: Any
) -> None:
    if not sqlite_vector_is_enabled():
        return

    if connection.vendor != "sqlite":
        return

    dbapi_connection = connection.connection
    if dbapi_connection is None:
        return

    try:
        load_sqlite_vector_extension(dbapi_connection)
    except SQLiteVectorExtensionError:
        if sqlite_vector_is_required():
            raise
        logger.warning("sqlite-vector extension is unavailable.", exc_info=True)


def register_sqlite_vector_loader() -> None:
    connection_created.connect(
        load_sqlite_vector_for_connection,
        dispatch_uid="rag.load_sqlite_vector",
    )


def get_sqlite_vector_version(using: str = "default") -> str:
    connection = connections[using]
    if connection.vendor != "sqlite":
        raise SQLiteVectorExtensionError("sqlite-vector is only available for SQLite.")

    with connection.cursor() as cursor:
        cursor.execute("SELECT vector_version()")
        row = cursor.fetchone()

    if not row:
        raise SQLiteVectorExtensionError("sqlite-vector did not return a version.")

    return str(row[0])
