"""Persistent LangGraph checkpoints selected by the application's database URL."""
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3
from threading import RLock
from urllib.parse import unquote, urlsplit

_SQLITE_LOCK = RLock()


@contextmanager
def open_checkpointer(database_url: str):
    """Open the configured checkpoint backend for one review operation.

    SQLite writes are serialized within this process. SQLite remains a local,
    single-process backend; use PostgreSQL when multiple workers share sessions.
    """
    if database_url.startswith("sqlite:///"):
        database = unquote(urlsplit(database_url).path)
        if database.startswith("//"):
            database = database[1:]
        elif database.startswith("/"):
            database = database[1:]
        if not database or database == ":memory:":
            raise ValueError("Resumable reviews require a file-backed SQLite database.")
        Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

        serde = JsonPlusSerializer(allowed_msgpack_modules=[])
        with _SQLITE_LOCK:
            with closing(sqlite3.connect(database, check_same_thread=False)) as connection:
                saver = SqliteSaver(connection, serde=serde)
                saver.setup()
                yield saver
        return

    if database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        from psycopg import Connection
        from psycopg.rows import dict_row
        from langgraph.checkpoint.postgres import PostgresSaver
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

        serde = JsonPlusSerializer(allowed_msgpack_modules=[])
        normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        with Connection.connect(normalized, autocommit=True, prepare_threshold=0, row_factory=dict_row) as connection:
            saver = PostgresSaver(connection, serde=serde)
            saver.setup()
            yield saver
        return

    raise ValueError("Review checkpoints support SQLite or PostgreSQL.")
