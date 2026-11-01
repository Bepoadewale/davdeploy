from __future__ import annotations

import os
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import ClassVar

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from davdeploy.models import Base


class AuroraDatabaseUnavailable(RuntimeError):
    """Raised when a paused Aurora cluster does not become ready in time."""


class AuroraReadinessGuard:
    """Wake a scale-to-zero Aurora cluster before opening an application session."""

    _RESUMING_CODES: ClassVar[frozenset[str]] = frozenset(
        {"DatabaseResumingException", "DatabaseUnavailableException"}
    )

    def __init__(self, *, cache_seconds: float = 600.0) -> None:
        self._cache_seconds = cache_seconds
        self._ready_until = 0.0
        self._lock = threading.Lock()

    def ensure_ready(
        self,
        *,
        client=None,
        sleeper=time.sleep,
        clock=time.monotonic,
        delays: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0, 6.0),
    ) -> None:
        cluster_arn = os.getenv("DAVDEPLOY_AURORA_CLUSTER_ARN")
        secret_arn = os.getenv("DAVDEPLOY_DATABASE_SECRET_ARN")
        if not cluster_arn and not secret_arn:
            return
        if not cluster_arn or not secret_arn:
            raise AuroraDatabaseUnavailable("database configuration is incomplete")
        if clock() < self._ready_until:
            return

        with self._lock:
            if clock() < self._ready_until:
                return
            data_api = client or boto3.client("rds-data")
            database = os.getenv("DAVDEPLOY_DATABASE_NAME", "davdeploy")
            for attempt in range(len(delays) + 1):
                try:
                    data_api.execute_statement(
                        resourceArn=cluster_arn,
                        secretArn=secret_arn,
                        database=database,
                        sql="SELECT 1",
                    )
                    self._ready_until = clock() + self._cache_seconds
                    return
                except ClientError as error:
                    code = error.response.get("Error", {}).get("Code")
                    if code not in self._RESUMING_CODES:
                        raise
                    if attempt == len(delays):
                        raise AuroraDatabaseUnavailable(
                            "database is resuming; retry shortly"
                        ) from error
                    sleeper(delays[attempt])


AURORA_READINESS = AuroraReadinessGuard()


def ensure_aurora_ready() -> None:
    AURORA_READINESS.ensure_ready()


def database_url() -> str:
    cluster_arn = os.getenv("DAVDEPLOY_AURORA_CLUSTER_ARN")
    secret_arn = os.getenv("DAVDEPLOY_DATABASE_SECRET_ARN")
    if cluster_arn or secret_arn:
        if not cluster_arn or not secret_arn:
            raise RuntimeError("Aurora Data API requires both cluster and secret ARNs")
        database = os.getenv("DAVDEPLOY_DATABASE_NAME", "davdeploy")
        return f"postgresql+auroradataapi://:@/{database}"
    resolved = os.getenv("DAVDEPLOY_DATABASE_URL", "sqlite+pysqlite:///./.local/davdeploy.db")
    if os.getenv("DAVDEPLOY_HOSTED_MODE", "false").lower() == "true" and resolved.startswith(
        "sqlite"
    ):
        raise RuntimeError("hosted davdeploy runtime requires durable PostgreSQL; SQLite is not allowed")
    return resolved


def make_engine(url: str | None = None) -> Engine:
    resolved = url or database_url()
    if resolved.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    elif resolved.startswith("postgresql+auroradataapi"):
        connect_args = {
            "aurora_cluster_arn": os.environ["DAVDEPLOY_AURORA_CLUSTER_ARN"],
            "secret_arn": os.environ["DAVDEPLOY_DATABASE_SECRET_ARN"],
        }
    else:
        connect_args = {}
    return create_engine(
        resolved,
        future=True,
        connect_args=connect_args,
        pool_pre_ping=not resolved.startswith("postgresql+auroradataapi"),
    )


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _add_columns_if_missing(connection, table_name: str, additions: dict[str, str]) -> None:
    """Add known migration columns without PostgreSQL schema reflection.

    Aurora Data API cannot return PostgreSQL's internal ``CHAR`` values used by SQLAlchemy's
    reflection query. PostgreSQL supports idempotent ``ADD COLUMN IF NOT EXISTS`` directly, so
    migrations do not need to retrieve the system catalogue at all. SQLite keeps the reflection
    fallback used by local tests and development.
    """
    if connection.dialect.name == "postgresql":
        for name, definition in additions.items():
            connection.execute(
                text(
                    f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{name}" {definition}'
                )
            )
        return

    columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
    for name, definition in additions.items():
        if name not in columns:
            connection.execute(
                text(f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {definition}')
            )


def run_migrations(target: Engine | None = None) -> None:
    """Small versioned bootstrap for V1; replace with an expanded migration set as schemas evolve."""
    selected = target or engine
    if str(selected.url).startswith("sqlite"):
        database = selected.url.database
        if database and database not in {":memory:"}:
            path = Path(database)
            if path.parent != Path("."):
                path.parent.mkdir(parents=True, exist_ok=True)
            elif str(path).startswith(".local/"):
                Path(".local").mkdir(exist_ok=True)
    with selected.begin() as connection:
        # API and worker can start together in Compose. PostgreSQL needs one
        # transaction-scoped lock before either process creates the migration table.
        if selected.dialect.name == "postgresql" and "+auroradataapi" not in str(selected.url):
            connection.execute(text("SELECT pg_advisory_xact_lock(84202601)"))
        connection.execute(
            text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
        )
        version = connection.execute(
            text("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
        ).scalar_one()
        if version < 1:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (20)"))
            return
        if version < 2:
            connection.execute(
                text("ALTER TABLE execution_jobs ADD COLUMN environment_id VARCHAR(36)")
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (2)"))
            version = 2
        if version < 3:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (3)"))
            version = 3
        if version < 4:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (4)"))
            version = 4
        if version < 5:
            _add_columns_if_missing(
                connection,
                "cloud_connections",
                {
                    "account_id": "VARCHAR(12)",
                    "discovery_role_arn": "TEXT",
                    "external_id": "TEXT",
                    "setup_state": "VARCHAR(32) DEFAULT 'DRAFT'",
                },
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (5)"))
            version = 5
        if version < 6:
            _add_columns_if_missing(
                connection, "cloud_connections", {"external_id_secret_ref": "TEXT"}
            )
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (6)"))
            version = 6
        if version < 7:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (7)"))
            version = 7
        if version < 8:
            _add_columns_if_missing(
                connection, "repository_connections", {"selected_branch": "VARCHAR(255)"}
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (8)"))
            version = 8
        if version < 9:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (9)"))
            version = 9
        if version < 10:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (10)"))
            version = 10
        if version < 11:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (11)"))
            version = 11
        if version < 12:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (12)"))
            version = 12
        if version < 13:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (13)"))
            version = 13
        if version < 14:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (14)"))
            version = 14
        if version < 15:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (15)"))
            version = 15
        if version < 16:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (16)"))
            version = 16
        if version < 17:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (17)"))
            version = 17
        if version < 18:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (18)"))
            version = 18
        if version < 19:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (19)"))
            version = 19
        if version < 20:
            _add_columns_if_missing(
                connection,
                "workspace_invitations",
                {
                    "delivery_state": "VARCHAR(24) DEFAULT 'PENDING'",
                    "delivery_provider": "VARCHAR(40)",
                    "provider_message_id": "VARCHAR(255)",
                    "send_count": "INTEGER DEFAULT 0",
                    "last_sent_at": "TIMESTAMP WITH TIME ZONE",
                    "cancelled_at": "TIMESTAMP WITH TIME ZONE",
                },
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (20)"))
            version = 20
        if version < 21:
            if inspect(connection).has_table("cloud_connections"):
                _add_columns_if_missing(
                    connection, "cloud_connections", {"execution_role_arn": "TEXT"}
                )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (21)"))
            version = 21
        if version < 22:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (22)"))


def session() -> Generator[Session, None, None]:
    current = SessionLocal()
    try:
        yield current
    finally:
        current.close()
