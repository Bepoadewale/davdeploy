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
        raise RuntimeError(
            "hosted davdeploy runtime requires durable PostgreSQL; SQLite is not allowed"
        )
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
                text(f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{name}" {definition}')
            )
        return

    columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
    for name, definition in additions.items():
        if name not in columns:
            connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {definition}'))


def _install_generated_plan_immutability(connection) -> None:
    """Reject direct SQL edits to signed generated-plan evidence records."""
    if connection.dialect.name == "sqlite":
        for table in ("generated_plan_artifacts", "generated_plan_approvals"):
            for operation in ("UPDATE", "DELETE"):
                trigger = f"trg_{table}_{operation.lower()}_immutable"
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS {trigger} BEFORE {operation} ON {table} "
                        "BEGIN SELECT RAISE(ABORT, 'generated plan evidence is immutable'); END"
                    )
                )
        return
    if connection.dialect.name == "postgresql":
        connection.execute(
            text(
                "CREATE OR REPLACE FUNCTION davdeploy_reject_generated_plan_mutation() "
                "RETURNS trigger AS $$ BEGIN "
                "RAISE EXCEPTION 'generated plan evidence is immutable'; END; $$ LANGUAGE plpgsql"
            )
        )
        for table in ("generated_plan_artifacts", "generated_plan_approvals"):
            trigger = f"trg_{table}_immutable"
            connection.execute(text(f'DROP TRIGGER IF EXISTS {trigger} ON "{table}"'))
            connection.execute(
                text(
                    f'CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON "{table}" '
                    "FOR EACH ROW EXECUTE FUNCTION davdeploy_reject_generated_plan_mutation()"
                )
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
            connection.execute(
                text(
                    "INSERT INTO worker_dispatch_states (id, next_queue_index) "
                    "VALUES (1, 0) ON CONFLICT (id) DO NOTHING"
                )
            )
            _install_generated_plan_immutability(connection)
            # create_all uses current model metadata, so new databases already include
            # every column through the latest schema version.
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (34)"))
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
            version = 22
        if version < 23:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (23)"))
            version = 23
        if version < 24:
            _add_columns_if_missing(
                connection,
                "cloud_execution_runs",
                {
                    "worker_claim_version": "INTEGER NOT NULL DEFAULT 0",
                    "worker_lease_token": "VARCHAR(64)",
                    "worker_lease_expires_at": "TIMESTAMP WITH TIME ZONE",
                },
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_cloud_execution_runs_worker_lease_expires_at "
                    "ON cloud_execution_runs(worker_lease_expires_at)"
                )
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (24)"))
            version = 24
        if version < 25:
            Base.metadata.create_all(bind=connection)
            _add_columns_if_missing(
                connection,
                "cloud_execution_module_instances",
                {"runner_build_id": "VARCHAR(255)"},
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_cloud_execution_module_runner_build_id "
                    "ON cloud_execution_module_instances(runner_build_id)"
                )
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (25)"))
            version = 25
        if version < 26:
            Base.metadata.create_all(bind=connection)
            _add_columns_if_missing(
                connection,
                "generated_plan_artifacts",
                {
                    "context_sha256": "VARCHAR(64) NOT NULL DEFAULT ''",
                    "policy_human_approval_required": "BOOLEAN NOT NULL DEFAULT TRUE",
                },
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (26)"))
        if version < 27:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (27)"))
            version = 27
        if version < 28:
            _add_columns_if_missing(
                connection,
                "generated_plan_runs",
                {
                    "request_document": "JSON",
                    "preparation_lease_token": "VARCHAR(64)",
                },
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_generated_plan_run_preparation_lease "
                    "ON generated_plan_runs(state, preparation_lease_expires_at)"
                )
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (28)"))
            version = 28
        if version < 29:
            Base.metadata.create_all(bind=connection)
            existing_runs = connection.execute(
                text(
                    "SELECT organization_id, idempotency_key_sha256, request_sha256, id "
                    "FROM generated_plan_runs"
                )
            ).mappings().all()
            for run in existing_runs:
                existing_key = connection.execute(
                    text(
                        "SELECT request_sha256, run_id "
                        "FROM generated_plan_run_idempotency_keys "
                        "WHERE organization_id = :organization_id "
                        "AND idempotency_key_sha256 = :idempotency_key_sha256"
                    ),
                    {
                        "organization_id": run["organization_id"],
                        "idempotency_key_sha256": run["idempotency_key_sha256"],
                    },
                ).mappings().first()
                if existing_key:
                    if (
                        existing_key["request_sha256"] != run["request_sha256"]
                        or existing_key["run_id"] != run["id"]
                    ):
                        raise RuntimeError("Nova plan idempotency key migration found a conflict")
                    continue
                connection.execute(
                    text(
                        "INSERT INTO generated_plan_run_idempotency_keys "
                        "(organization_id, idempotency_key_sha256, request_sha256, run_id) "
                        "VALUES (:organization_id, :idempotency_key_sha256, :request_sha256, :run_id)"
                    ),
                    {
                        "organization_id": run["organization_id"],
                        "idempotency_key_sha256": run["idempotency_key_sha256"],
                        "request_sha256": run["request_sha256"],
                        "run_id": run["id"],
                    },
                )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (29)"))
            version = 29
        if version < 30:
            _add_columns_if_missing(
                connection,
                "generated_plan_runs",
                {"runner_run_id": "VARCHAR(36)"},
            )
            connection.execute(
                text("UPDATE generated_plan_runs SET runner_run_id = id WHERE runner_run_id IS NULL")
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_generated_plan_runs_runner_run_id "
                    "ON generated_plan_runs(runner_run_id)"
                )
            )
            Base.metadata.create_all(bind=connection)
            connection.execute(
                text(
                    "INSERT INTO worker_dispatch_states (id, next_queue_index) "
                    "VALUES (1, 0) ON CONFLICT (id) DO NOTHING"
                )
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (30)"))
        if version < 31:
            _add_columns_if_missing(
                connection,
                "generated_plan_runs",
                {
                    "preparation_phase": "VARCHAR(40)",
                    "codebuild_idempotency_token": "VARCHAR(64)",
                },
            )
            connection.execute(
                text(
                    "UPDATE generated_plan_runs "
                    "SET codebuild_idempotency_token = runner_run_id "
                    "WHERE codebuild_idempotency_token IS NULL AND runner_run_id IS NOT NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE generated_plan_runs SET preparation_phase = 'STAGING_INPUT' "
                    "WHERE preparation_phase IS NULL AND state = 'PREPARING' "
                    "AND codebuild_build_id IS NULL AND input_sha256 IS NOT NULL "
                    "AND input_version_id IS NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE generated_plan_runs SET preparation_phase = 'STARTING_BUILD' "
                    "WHERE preparation_phase IS NULL AND state = 'PREPARING' "
                    "AND codebuild_build_id IS NULL AND input_version_id IS NOT NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE generated_plan_runs SET preparation_phase = 'GENERATING_PROPOSAL' "
                    "WHERE preparation_phase IS NULL AND state = 'PREPARING' "
                    "AND codebuild_build_id IS NULL AND input_sha256 IS NULL"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_generated_plan_runs_codebuild_idempotency_token "
                    "ON generated_plan_runs(codebuild_idempotency_token)"
                )
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (31)"))
            version = 31
        if version < 32:
            if not inspect(connection).has_table("cloud_connections"):
                raise RuntimeError(
                    "Cannot apply schema migration 32: cloud_connections table is missing"
                )
            _add_columns_if_missing(
                connection,
                "cloud_connections",
                {
                    "plan_role_arn": "TEXT",
                    "plan_role_setup_state": "VARCHAR(32) NOT NULL DEFAULT 'NOT_CONFIGURED'",
                },
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (32)"))
            version = 32
        if version < 33:
            # The state backend is additive; create_all installs its four new tables
            # without altering existing tenant or plan records.
            Base.metadata.create_all(bind=connection)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (33)"))
            version = 33
        if version < 34:
            _add_columns_if_missing(
                connection,
                "generated_plan_artifacts",
                {
                    "workspace_artifact_bucket": "VARCHAR(255)",
                    "workspace_artifact_key": "TEXT",
                    "workspace_artifact_version_id": "VARCHAR(1024)",
                    "workspace_artifact_size_bytes": "INTEGER",
                    "workspace_sha256": "VARCHAR(64)",
                },
            )
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (34)"))
        _install_generated_plan_immutability(connection)


def session() -> Generator[Session, None, None]:
    current = SessionLocal()
    try:
        yield current
    finally:
        current.close()
