"""FASE 3: auditoria

Tabela append-only. Sem FK em `user_id`, `project_id` e `document_id` de
propósito: o log precisa sobreviver à exclusão da entidade que descreve — um
registro de "documento X excluído" que some junto com o documento não serve
para nada.

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(400), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_project_id", "audit_logs", ["project_id"])
    op.create_index("ix_audit_logs_document_id", "audit_logs", ["document_id"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_user_ts", "audit_logs", ["user_id", "timestamp"])


def downgrade() -> None:
    for indice in (
        "ix_audit_user_ts", "ix_audit_entity", "ix_audit_logs_request_id",
        "ix_audit_logs_document_id", "ix_audit_logs_project_id",
        "ix_audit_logs_action", "ix_audit_logs_user_id", "ix_audit_logs_timestamp",
    ):
        op.drop_index(indice, table_name="audit_logs")
    op.drop_table("audit_logs")
