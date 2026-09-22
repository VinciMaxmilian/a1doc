"""FASE 2: sessões, throttle de login e identidades externas

Cria o lastro do refresh token (`user_sessions`), o contador de força bruta
(`login_throttle`) e o vínculo com providers externos (`identidades_externas`).

Compatibilidade: nada é removido. Os tokens JWT já emitidos continuam válidos
até expirarem — eles não têm `sid`, e `get_current_user` trata `sid` ausente
como sessão não rastreada em vez de recusar. Quem logar de novo passa a ter
sessão registrada.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("previous_token_hash", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(30), nullable=False, server_default="local"),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(400), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(100), nullable=True),
    )
    op.create_index("ix_user_sessions_usuario_id", "user_sessions", ["usuario_id"])
    op.create_index(
        "ix_user_sessions_previous_token_hash", "user_sessions", ["previous_token_hash"]
    )
    op.create_index(
        "ix_user_sessions_usuario_revoked", "user_sessions", ["usuario_id", "revoked_at"]
    )

    op.create_table(
        "login_throttle",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("chave", sa.String(200), nullable=False),
        sa.Column("falhas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bloqueios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("primeira_falha", sa.DateTime(), nullable=True),
        sa.Column("ultima_falha", sa.DateTime(), nullable=True),
        sa.Column("bloqueado_ate", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tipo", "chave", name="uq_login_throttle_chave"),
    )

    op.create_table(
        "identidades_externas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("ultimo_login", sa.DateTime(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("provider", "subject", name="uq_identidade_provider_subject"),
    )
    op.create_index("ix_identidades_externas_usuario_id", "identidades_externas", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_identidades_externas_usuario_id", table_name="identidades_externas")
    op.drop_table("identidades_externas")
    op.drop_table("login_throttle")
    op.drop_index("ix_user_sessions_usuario_revoked", table_name="user_sessions")
    op.drop_index("ix_user_sessions_previous_token_hash", table_name="user_sessions")
    op.drop_index("ix_user_sessions_usuario_id", table_name="user_sessions")
    op.drop_table("user_sessions")
