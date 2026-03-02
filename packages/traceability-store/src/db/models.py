"""SQLAlchemy ORM models for the Traceability Store.

JSON storage note: JSONB is used on PostgreSQL for efficient storage and
indexing. For SQLite (used in tests) the same columns fall back to standard
JSON via the ``FlexibleJSON`` custom type below.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class FlexibleJSON(TypeDecorator):
    """JSON type that renders as JSONB on PostgreSQL and JSON elsewhere (SQLite).

    This lets the ORM models work transparently in both production (asyncpg +
    PostgreSQL) and test (aiosqlite + SQLite) environments without any import
    monkey-patching.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class Report(Base):
    """Stores every generated digest report.

    One row per digest. The full structured digest is stored in ``digest_json``
    as JSONB (PostgreSQL) / JSON (SQLite) so the schema does not need to change
    when the digest format evolves.
    """

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    digest_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    digest_json: Mapped[dict] = mapped_column(FlexibleJSON, nullable=False)
    user_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        "ToolCall", back_populates="report", cascade="all, delete-orphan"
    )
    sources: Mapped[list["Source"]] = relationship(
        "Source", back_populates="report", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_reports_digest_type_generated_at", "digest_type", "generated_at"),
    )


class ToolCall(Base):
    """Records every MCP tool call made during digest generation.

    Stores input/output as FlexibleJSON for flexibility. The ``latency_ms``
    column enables p50/p95/p99 latency metrics across all tool invocations.
    """

    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[str] = mapped_column(
        Text, ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    input_json: Mapped[dict] = mapped_column(FlexibleJSON, nullable=False)
    output_json: Mapped[dict | None] = mapped_column(FlexibleJSON, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship
    report: Mapped["Report"] = relationship("Report", back_populates="tool_calls")

    __table_args__ = (
        Index("ix_tool_calls_tool_name_timestamp", "tool_name", "timestamp"),
        Index("ix_tool_calls_status_timestamp", "status", "timestamp"),
    )


class Source(Base):
    """Records every source article referenced in a digest.

    Enables the Web App debug panel to display all articles that contributed to
    a digest and supports source-frequency analytics.
    """

    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[str] = mapped_column(
        Text, ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship
    report: Mapped["Report"] = relationship("Report", back_populates="sources")

    __table_args__ = (Index("ix_sources_report_id_url", "report_id", "url"),)
