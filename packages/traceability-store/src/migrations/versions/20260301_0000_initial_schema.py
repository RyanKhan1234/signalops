"""Initial schema: reports, tool_calls, sources tables.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-03-01 00:00:00.000000+00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create reports, tool_calls, and sources tables with all indexes."""

    # ── reports ──────────────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("report_id", sa.Text(), nullable=False),
        sa.Column("digest_type", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("digest_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", name="uq_reports_report_id"),
    )
    op.create_index("ix_reports_report_id", "reports", ["report_id"], unique=True)
    op.create_index("ix_reports_digest_type", "reports", ["digest_type"])
    op.create_index("ix_reports_generated_at", "reports", ["generated_at"])
    op.create_index("ix_reports_user_id", "reports", ["user_id"])
    op.create_index(
        "ix_reports_digest_type_generated_at",
        "reports",
        ["digest_type", "generated_at"],
    )

    # ── tool_calls ────────────────────────────────────────────────────────────
    op.create_table(
        "tool_calls",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("report_id", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.report_id"],
            name="fk_tool_calls_report_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_calls_report_id", "tool_calls", ["report_id"])
    op.create_index("ix_tool_calls_tool_name", "tool_calls", ["tool_name"])
    op.create_index("ix_tool_calls_timestamp", "tool_calls", ["timestamp"])
    op.create_index("ix_tool_calls_status", "tool_calls", ["status"])
    op.create_index(
        "ix_tool_calls_tool_name_timestamp", "tool_calls", ["tool_name", "timestamp"]
    )
    op.create_index(
        "ix_tool_calls_status_timestamp", "tool_calls", ["status", "timestamp"]
    )

    # ── sources ───────────────────────────────────────────────────────────────
    op.create_table(
        "sources",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("report_id", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("published_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.report_id"],
            name="fk_sources_report_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_report_id", "sources", ["report_id"])
    op.create_index("ix_sources_url", "sources", ["url"])
    op.create_index("ix_sources_published_date", "sources", ["published_date"])
    op.create_index("ix_sources_report_id_url", "sources", ["report_id", "url"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("sources")
    op.drop_table("tool_calls")
    op.drop_table("reports")
