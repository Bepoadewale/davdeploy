from __future__ import annotations

from datetime import UTC, datetime, timedelta

from davdeploy.db import _add_columns_if_missing, run_migrations
from davdeploy.invitation_email import ResendInvitationEmailSender, SesInvitationEmailSender
from sqlalchemy import create_engine, inspect, text


def test_postgresql_column_migrations_avoid_schema_reflection():
    class Dialect:
        name = "postgresql"

    class Connection:
        dialect = Dialect()

        def __init__(self):
            self.statements = []

        def execute(self, statement):
            self.statements.append(str(statement))

    connection = Connection()

    _add_columns_if_missing(
        connection,
        "workspace_invitations",
        {"delivery_state": "VARCHAR(24) DEFAULT 'PENDING'"},
    )

    assert connection.statements == [
        (
            'ALTER TABLE "workspace_invitations" ADD COLUMN IF NOT EXISTS "delivery_state" '
            "VARCHAR(24) DEFAULT 'PENDING'"
        )
    ]


def test_ses_invitation_sender_uses_one_bounded_transactional_message():
    class SesClient:
        def __init__(self):
            self.requests = []

        def send_email(self, **request):
            self.requests.append(request)
            return {"MessageId": "ses-message-1"}

    client = SesClient()
    sender = SesInvitationEmailSender(
        from_address="team@davdeploy.example",
        frontend_origin="https://davdeploy.example",
        region="us-east-1",
        client=client,
    )

    delivery = sender.send(
        email="invitee@example.com",
        role="developer",
        token="safe-token",
        workspace_name="Example workspace",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    request = client.requests[0]
    assert request["FromEmailAddress"] == "team@davdeploy.example"
    assert request["Destination"] == {"ToAddresses": ["invitee@example.com"]}
    text = request["Content"]["Simple"]["Body"]["Text"]["Data"]
    assert "https://davdeploy.example/login?invite=safe-token" in text
    assert delivery.message_id == "ses-message-1"


def test_resend_invitation_sender_uses_a_bounded_transactional_message():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "resend-message-1"}

    class Client:
        def __init__(self):
            self.requests = []

        def post(self, url, **request):
            self.requests.append((url, request))
            return Response()

    client = Client()
    sender = ResendInvitationEmailSender(
        api_key="resend-secret",
        from_address="DavDeploy <notify@davdeploy.tech>",
        reply_to_address="support@davdeploy.tech",
        frontend_origin="https://davdeploy.tech",
        client=client,
    )

    delivery = sender.send(
        email="invitee@example.com",
        role="developer",
        token="safe-token",
        workspace_name="Example workspace",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    url, request = client.requests[0]
    assert url == "https://api.resend.com/emails"
    assert request["headers"] == {"Authorization": "Bearer resend-secret"}
    assert request["json"]["from"] == "DavDeploy <notify@davdeploy.tech>"
    assert request["json"]["reply_to"] == "support@davdeploy.tech"
    assert request["json"]["to"] == ["invitee@example.com"]
    assert "https://davdeploy.tech/login?invite=safe-token" in request["json"]["text"]
    assert delivery.message_id == "resend-message-1"


def test_fresh_schema_records_current_invitation_migration():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    run_migrations(engine)

    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT MAX(version) FROM schema_migrations")
        ).scalar_one()
    assert version == 20
    columns = {column["name"] for column in inspect(engine).get_columns("workspace_invitations")}
    assert {"delivery_state", "send_count", "last_sent_at", "cancelled_at"} <= columns


def test_invitation_migration_upgrades_existing_version_19_schema():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO schema_migrations(version) VALUES (19)"))
        connection.execute(
            text(
                "CREATE TABLE workspace_invitations ("
                "id VARCHAR(36) PRIMARY KEY, organization_id VARCHAR(36), email VARCHAR(320), "
                "role VARCHAR(32), token_digest VARCHAR(64), state VARCHAR(24), "
                "invited_by_subject VARCHAR(255), expires_at TIMESTAMP, accepted_at TIMESTAMP, "
                "created_at TIMESTAMP)"
            )
        )

    run_migrations(engine)
    run_migrations(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("workspace_invitations")}
    assert {
        "delivery_state",
        "delivery_provider",
        "provider_message_id",
        "send_count",
        "last_sent_at",
        "cancelled_at",
    } <= columns
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT MAX(version) FROM schema_migrations")
        ).scalar_one()
    assert version == 21
