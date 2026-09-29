"""Initial relational workspace schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)

    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("digest", sa.String(length=80), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_kind", "assets", ["kind"], unique=False)

    op.create_table(
        "scans",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("profile", sa.String(length=40), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overall_disposition", sa.String(length=16), nullable=True),
        sa.Column("findings", sa.Integer(), nullable=False),
        sa.Column("critical", sa.Integer(), nullable=False),
        sa.Column("quarantine", sa.Integer(), nullable=False),
        sa.Column("review", sa.Integer(), nullable=False),
        sa.Column("coverage_assessed", sa.Integer(), nullable=False),
        sa.Column("coverage_partial", sa.Integer(), nullable=False),
        sa.Column("coverage_total", sa.Integer(), nullable=False),
        sa.Column("result_path", sa.Text(), nullable=True),
        sa.Column("report_dir", sa.Text(), nullable=True),
        sa.Column("report_digest", sa.String(length=80), nullable=True),
        sa.Column("plan", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scans_created_at", "scans", ["created_at"], unique=False)
    op.create_index("ix_scans_status", "scans", ["status"], unique=False)

    op.create_table(
        "scan_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scan_id", sa.String(length=40), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("t_ms", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=8), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detector_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "seq"),
    )
    op.create_index("ix_scan_events_scan_id", "scan_events", ["scan_id"], unique=False)

    op.create_table(
        "finding_state",
        sa.Column("finding_id", sa.String(length=24), nullable=False),
        sa.Column("scan_id", sa.String(length=40), nullable=False),
        sa.Column("detector_id", sa.String(length=64), nullable=False),
        sa.Column("attack_class", sa.String(length=48), nullable=False),
        sa.Column("layer", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("original_disposition", sa.String(length=16), nullable=False),
        sa.Column("disposition", sa.String(length=16), nullable=False),
        sa.Column("deterministic", sa.Boolean(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("owner", sa.String(length=64), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=64), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("finding_id"),
    )
    op.create_index("ix_finding_state_attack_class", "finding_state", ["attack_class"], unique=False)
    op.create_index("ix_finding_state_disposition", "finding_state", ["disposition"], unique=False)
    op.create_index("ix_finding_state_scan_id", "finding_state", ["scan_id"], unique=False)
    op.create_index("ix_finding_state_severity", "finding_state", ["severity"], unique=False)

    op.create_table(
        "decisions",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("finding_id", sa.String(length=24), nullable=False),
        sa.Column("scan_id", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_disposition", sa.String(length=16), nullable=False),
        sa.Column("to_disposition", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["finding_id"], ["finding_state.finding_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decisions_finding_id", "decisions", ["finding_id"], unique=False)
    op.create_index("ix_decisions_scan_id", "decisions", ["scan_id"], unique=False)
    op.create_index("ix_decisions_status", "decisions", ["status"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("target", sa.String(length=96), nullable=False),
        sa.Column("old_state", sa.String(length=64), nullable=True),
        sa.Column("new_state", sa.String(length=64), nullable=True),
        sa.Column("reason_code", sa.String(length=32), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("ledger_seq", sa.Integer(), nullable=True),
        sa.Column("entry_hash", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index("ix_audit_events_actor", "audit_events", ["actor"], unique=False)
    op.create_index("ix_audit_events_target", "audit_events", ["target"], unique=False)
    op.create_index("ix_audit_events_ts", "audit_events", ["ts"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_by", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("scan_id", sa.String(length=40), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_kind", "jobs", ["kind"], unique=False)
    op.create_index("ix_jobs_started_at", "jobs", ["started_at"], unique=False)
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)


def downgrade() -> None:
    for table in ("jobs", "audit_events", "decisions", "finding_state", "scan_events", "scans", "assets", "sessions", "users"):
        op.drop_table(table)
