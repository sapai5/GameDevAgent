"""SQLite migration support for rebuildable derived AI memory."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from .storage import StateError


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    checksum: str
    sql: str


def _migration_version(name: str) -> int:
    prefix = name.split("_", 1)[0]
    if not prefix.isdigit():
        raise StateError(f"migration must start with a numeric version: {name}")
    return int(prefix)


def _load_migrations(directory: Path | None) -> tuple[Migration, ...]:
    if directory is None:
        entries: list[Any] = list(files("gamedev_agent").joinpath("sql", "migrations").iterdir())
    else:
        if not directory.is_dir():
            raise StateError(f"migration directory does not exist: {directory}")
        entries = list(directory.iterdir())

    migrations: list[Migration] = []
    for entry in sorted(entries, key=lambda item: item.name):
        if not entry.name.endswith(".sql"):
            continue
        sql = entry.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=_migration_version(entry.name),
                name=entry.name,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )
    if not migrations:
        raise StateError("no SQL migrations were found")
    versions = [migration.version for migration in migrations]
    if versions != sorted(set(versions)):
        raise StateError("SQL migration versions must be unique and ordered")
    return tuple(migrations)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class SqliteMemoryStore:
    """Manage a local derived-memory schema without replacing manifest authority."""

    def __init__(self, path: Path, *, migration_directory: Path | None = None) -> None:
        self.path = path
        self.migration_directory = migration_directory

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> tuple[int, ...]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        migrations = _load_migrations(self.migration_directory)
        applied: list[int] = []
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        checksum TEXT NOT NULL,
                        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                existing = {
                    int(row["version"]): (str(row["name"]), str(row["checksum"]))
                    for row in connection.execute(
                        "SELECT version, name, checksum FROM schema_migrations"
                    )
                }
                for migration in migrations:
                    recorded = existing.get(migration.version)
                    if recorded is not None:
                        if recorded != (migration.name, migration.checksum):
                            raise StateError(
                                f"migration checksum drift at version {migration.version}: "
                                f"{migration.name}"
                            )
                        continue
                    tracking = (
                        "INSERT INTO schema_migrations(version, name, checksum) VALUES ("
                        f"{migration.version}, {_sql_literal(migration.name)}, "
                        f"{_sql_literal(migration.checksum)});"
                    )
                    connection.executescript(
                        "BEGIN IMMEDIATE;\n" + migration.sql + "\n" + tracking + "\nCOMMIT;"
                    )
                    applied.append(migration.version)
        except sqlite3.Error as error:
            raise StateError(
                f"failed to initialize SQLite memory at {self.path}: {error}"
            ) from error
        return tuple(applied)

    def schema_version(self) -> int:
        if not self.path.exists():
            return 0
        try:
            with self.connect() as connection:
                row = connection.execute(
                    "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
                ).fetchone()
        except sqlite3.Error as error:
            raise StateError(f"invalid SQLite memory at {self.path}: {error}") from error
        return int(row["version"]) if row is not None else 0
