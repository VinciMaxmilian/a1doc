"""Atividade: ordem explícita + papel exigido para transitar

`ordem` substitui a ordenação implícita por id (frágil quando atividades são
recriadas). `role_requerido` habilita autorização por atividade no workflow.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("atividades", sa.Column("ordem", sa.Integer(), nullable=False,
                                          server_default="0"))
    op.add_column("atividades", sa.Column("role_requerido", sa.String(20), nullable=True))
    # Preserva a ordenação que o sistema usava antes (por id).
    op.execute("UPDATE atividades SET ordem = id")


def downgrade() -> None:
    op.drop_column("atividades", "role_requerido")
    op.drop_column("atividades", "ordem")
