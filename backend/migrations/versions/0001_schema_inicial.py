"""Schema inicial

Bancos que já existem (criados pelo antigo create_all/migrate_db) devem ser
marcados sem executar nada:

    alembic stamp 0001

Revision ID: 0001
Revises:
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), server_default="user"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
    )

    op.create_table(
        "ambientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False),
    )

    op.create_table(
        "areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("ambiente_id", sa.Integer(), sa.ForeignKey("ambientes.id"), nullable=False),
    )

    op.create_table(
        "projetos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False),
    )

    op.create_table(
        "tipos_documento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False),
    )

    op.create_table(
        "campos_formulario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo_documento_id", sa.Integer(),
                  sa.ForeignKey("tipos_documento.id"), nullable=False),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("tipo", sa.String(50), server_default="text"),
        sa.Column("opcoes", sa.JSON(), nullable=True),
        sa.Column("ordem", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "fluxos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.Integer(), nullable=False, unique=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
    )

    op.create_table(
        "atividades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("fluxo_id", sa.Integer(), sa.ForeignKey("fluxos.id"), nullable=False),
    )
    op.create_index("ix_atividades_fluxo_id", "atividades", ["fluxo_id"])

    op.create_table(
        "config_transicoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("atividade_origem_id", sa.Integer(),
                  sa.ForeignKey("atividades.id"), nullable=False),
        sa.Column("acao", sa.String(20), nullable=False),
        sa.Column("atividade_destino_id", sa.Integer(),
                  sa.ForeignKey("atividades.id"), nullable=False),
        sa.Column("gera_nova_revisao", sa.Boolean(), server_default=sa.false()),
        sa.UniqueConstraint("atividade_origem_id", "acao", name="uq_transicao_origem_acao"),
    )

    op.create_table(
        "documentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(100), nullable=False, unique=True),
        sa.Column("nome", sa.String(500), nullable=False),
        sa.Column("ambiente_id", sa.Integer(), sa.ForeignKey("ambientes.id"), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False),
        sa.Column("projeto_id", sa.Integer(), sa.ForeignKey("projetos.id"), nullable=False),
        sa.Column("tipo_documento_id", sa.Integer(),
                  sa.ForeignKey("tipos_documento.id"), nullable=False),
        sa.Column("responsavel_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("atividade_atual_id", sa.Integer(),
                  sa.ForeignKey("atividades.id"), nullable=True),
        sa.Column("revisao_indice", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_documentos_nome", "documentos", ["nome"])
    op.create_index("ix_documentos_ambiente_id", "documentos", ["ambiente_id"])
    op.create_index("ix_documentos_area_id", "documentos", ["area_id"])
    op.create_index("ix_documentos_projeto_id", "documentos", ["projeto_id"])
    op.create_index("ix_documentos_tipo_documento_id", "documentos", ["tipo_documento_id"])

    op.create_table(
        "documento_arquivos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id"), nullable=False),
        sa.Column("arquivo_nome", sa.String(500), nullable=False),
        sa.Column("arquivo_path", sa.String(1000), nullable=False),
        sa.Column("revisao_indice", sa.Integer(), server_default="0"),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("atividade_id", sa.Integer(), sa.ForeignKey("atividades.id"), nullable=True),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_documento_arquivos_documento_id", "documento_arquivos", ["documento_id"])

    op.create_table(
        "historico_workflow",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id"), nullable=False),
        sa.Column("atividade_origem_id", sa.Integer(),
                  sa.ForeignKey("atividades.id"), nullable=True),
        sa.Column("atividade_destino_id", sa.Integer(),
                  sa.ForeignKey("atividades.id"), nullable=False),
        sa.Column("acao", sa.String(50), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_historico_workflow_documento_id", "historico_workflow", ["documento_id"])

    op.create_table(
        "valores_campo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id"), nullable=False),
        sa.Column("campo_id", sa.Integer(), sa.ForeignKey("campos_formulario.id"), nullable=False),
        sa.Column("valor", sa.Text(), nullable=True),
        sa.UniqueConstraint("documento_id", "campo_id", name="uq_valor_campo"),
    )
    op.create_index("ix_valores_campo_documento_id", "valores_campo", ["documento_id"])

    op.create_table(
        "upload_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), server_default="pendente"),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id"), nullable=True),
        sa.Column("erro_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    for tabela in (
        "upload_jobs", "valores_campo", "historico_workflow", "documento_arquivos",
        "documentos", "config_transicoes", "atividades", "fluxos",
        "campos_formulario", "tipos_documento", "projetos", "areas",
        "ambientes", "usuarios",
    ):
        op.drop_table(tabela)
