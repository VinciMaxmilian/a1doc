"""FASE 1: RBAC + ACL granular

Cria grupos, perfis e ACL, e adiciona os campos corporativos de usuário.

Compatibilidade — o ponto delicado desta migration:

A ACL é default-deny. Aplicada crua num banco existente, ela trancaria todos os
usuários para fora de todos os documentos. Por isso a migration SEMEIA o acesso
que já existia: todo usuário com `role='user'` recebe o perfil
`usuario_padrao` em escopo global, que concede exatamente o que qualquer
usuário autenticado já podia fazer antes. `admin`/`dev` recebem
`administrador`.

Resultado: ninguém ganha nem perde acesso ao aplicar esta migration. Fechar o
acesso amplo passa a ser uma decisão de configuração — remover a atribuição
global de `usuario_padrao` e conceder por projeto. Ver `docs/permissions.md`.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


# Reproduzido aqui em vez de importado de `indoc.permissions.constants`:
# migration é histórico, não pode mudar de efeito porque o código mudou.
PERFIS = {
    "administrador": ("Acesso total. Equivale aos papéis 'admin' e 'dev' anteriores.", ["*"]),
    "usuario_padrao": (
        "Compatibilidade: o que todo usuário autenticado já podia fazer antes da ACL.",
        ["read", "create", "upload", "download", "revise", "approve", "reject"],
    ),
    "controle_documental": (
        "Controle documental: administra metadados, distribui e revisa.",
        ["read", "create", "update", "download", "upload", "revise",
         "comment", "distribute", "manage_metadata"],
    ),
    "projetista": (
        "Elabora e emite documentos da sua disciplina.",
        ["read", "create", "update", "download", "upload", "revise", "comment"],
    ),
    "revisor": ("Analisa e comenta, sem aprovar.", ["read", "download", "comment"]),
    "aprovador": (
        "Aprova ou reprova documentos submetidos.",
        ["read", "download", "comment", "approve", "reject"],
    ),
    "fornecedor": (
        "Externo: envia documentos e revisões do próprio escopo.",
        ["read", "download", "upload", "revise", "comment"],
    ),
    "cliente": (
        "Externo: consulta e comenta o que lhe foi distribuído.",
        ["read", "download", "comment"],
    ),
    "consulta": ("Somente leitura.", ["read"]),
}


def upgrade() -> None:
    # ── campos corporativos do usuário (todos nullable) ──
    with op.batch_alter_table("usuarios") as batch:
        batch.add_column(sa.Column("departamento", sa.String(200), nullable=True))
        batch.add_column(sa.Column("cargo", sa.String(200), nullable=True))
        batch.add_column(sa.Column("ultimo_login", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("bloqueado_em", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("motivo_bloqueio", sa.String(500), nullable=True))

    # ── grupos ──
    op.create_table(
        "grupos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False, unique=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "usuario_grupos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("grupo_id", sa.Integer(), sa.ForeignKey("grupos.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("usuario_id", "grupo_id", name="uq_usuario_grupo"),
    )
    op.create_index("ix_usuario_grupos_usuario_id", "usuario_grupos", ["usuario_id"])
    op.create_index("ix_usuario_grupos_grupo_id", "usuario_grupos", ["grupo_id"])

    # ── perfis ──
    op.create_table(
        "perfis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(100), nullable=False, unique=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("sistema", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "perfil_permissoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("perfil_id", sa.Integer(), sa.ForeignKey("perfis.id"), nullable=False),
        sa.Column("permission", sa.String(50), nullable=False),
        sa.UniqueConstraint("perfil_id", "permission", name="uq_perfil_permissao"),
    )
    op.create_index("ix_perfil_permissoes_perfil_id", "perfil_permissoes", ["perfil_id"])

    op.create_table(
        "usuario_perfis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("perfil_id", sa.Integer(), sa.ForeignKey("perfis.id"), nullable=False),
        sa.Column("resource_type", sa.String(20), nullable=True),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "usuario_id", "perfil_id", "resource_type", "resource_id",
            name="uq_usuario_perfil_escopo",
        ),
    )
    op.create_index("ix_usuario_perfis_usuario_id", "usuario_perfis", ["usuario_id"])
    op.create_index("ix_usuario_perfis_perfil_id", "usuario_perfis", ["perfil_id"])

    # ── ACL ──
    op.create_table(
        "acl_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("permission", sa.String(50), nullable=False),
        sa.Column("allow", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.UniqueConstraint(
            "subject_type", "subject_id", "resource_type", "resource_id", "permission",
            name="uq_acl_subject_resource_permission",
        ),
    )
    # A resolução filtra sempre por sujeito e depois por recurso.
    op.create_index("ix_acl_subject", "acl_entries", ["subject_type", "subject_id"])
    op.create_index("ix_acl_resource", "acl_entries", ["resource_type", "resource_id"])

    _semear(op.get_bind())


def _semear(conn) -> None:
    """Cria os perfis semente e preserva o acesso dos usuários existentes."""
    perfis = sa.table(
        "perfis",
        sa.column("id", sa.Integer),
        sa.column("nome", sa.String),
        sa.column("descricao", sa.Text),
        sa.column("sistema", sa.Boolean),
        sa.column("ativo", sa.Boolean),
    )
    perfil_perms = sa.table(
        "perfil_permissoes",
        sa.column("perfil_id", sa.Integer),
        sa.column("permission", sa.String),
    )
    usuario_perfis = sa.table(
        "usuario_perfis",
        sa.column("usuario_id", sa.Integer),
        sa.column("perfil_id", sa.Integer),
        sa.column("resource_type", sa.String),
        sa.column("resource_id", sa.Integer),
    )

    conn.execute(
        perfis.insert(),
        [
            {"nome": nome, "descricao": desc, "sistema": True, "ativo": True}
            for nome, (desc, _) in PERFIS.items()
        ],
    )

    ids = dict(conn.execute(sa.select(perfis.c.nome, perfis.c.id)).fetchall())

    conn.execute(
        perfil_perms.insert(),
        [
            {"perfil_id": ids[nome], "permission": perm}
            for nome, (_, perms) in PERFIS.items()
            for perm in perms
        ],
    )

    # Traduz os papéis existentes em perfis, em escopo global.
    usuarios = sa.table("usuarios", sa.column("id", sa.Integer), sa.column("role", sa.String))
    linhas = conn.execute(sa.select(usuarios.c.id, usuarios.c.role)).fetchall()
    atribuicoes = [
        {
            "usuario_id": uid,
            "perfil_id": ids["administrador" if role in ("admin", "dev") else "usuario_padrao"],
            "resource_type": None,
            "resource_id": None,
        }
        for uid, role in linhas
    ]
    if atribuicoes:
        conn.execute(usuario_perfis.insert(), atribuicoes)


def downgrade() -> None:
    op.drop_index("ix_acl_resource", table_name="acl_entries")
    op.drop_index("ix_acl_subject", table_name="acl_entries")
    op.drop_table("acl_entries")

    op.drop_index("ix_usuario_perfis_perfil_id", table_name="usuario_perfis")
    op.drop_index("ix_usuario_perfis_usuario_id", table_name="usuario_perfis")
    op.drop_table("usuario_perfis")

    op.drop_index("ix_perfil_permissoes_perfil_id", table_name="perfil_permissoes")
    op.drop_table("perfil_permissoes")
    op.drop_table("perfis")

    op.drop_index("ix_usuario_grupos_grupo_id", table_name="usuario_grupos")
    op.drop_index("ix_usuario_grupos_usuario_id", table_name="usuario_grupos")
    op.drop_table("usuario_grupos")
    op.drop_table("grupos")

    with op.batch_alter_table("usuarios") as batch:
        batch.drop_column("motivo_bloqueio")
        batch.drop_column("bloqueado_em")
        batch.drop_column("ultimo_login")
        batch.drop_column("cargo")
        batch.drop_column("departamento")
