"""Models do controle de acesso (FASE 1).

Desenho: toda a política é DADO, não código. O `PermissionService` tem um único
caminho de avaliação; quem decide o que cada um pode são as linhas destas
tabelas. Isso é o que permite apertar ou afrouxar o acesso de uma instalação
sem tocar no código — e é pré-requisito do low-code da FASE 80.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from indoc.core.database import Base
from indoc.core.time import utcnow


class Grupo(Base):
    """Agrupamento de usuários — Engenharia Mecânica, Fornecedor A, etc."""

    __tablename__ = "grupos"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), unique=True, nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    membros = relationship("UsuarioGrupo", back_populates="grupo", cascade="all, delete-orphan")


class UsuarioGrupo(Base):
    __tablename__ = "usuario_grupos"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    usuario = relationship("User")
    grupo = relationship("Grupo", back_populates="membros")
    __table_args__ = (UniqueConstraint("usuario_id", "grupo_id", name="uq_usuario_grupo"),)


class Perfil(Base):
    """Conjunto nomeado de permissões (projetista, aprovador, fornecedor...).

    `sistema=True` marca os perfis semente: podem ser editados nas permissões,
    mas não excluídos — a aplicação depende de `administrador` existir.
    """

    __tablename__ = "perfis"
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)
    descricao = Column(Text, nullable=True)
    sistema = Column(Boolean, default=False, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    permissoes = relationship("PerfilPermissao", back_populates="perfil", cascade="all, delete-orphan")


class PerfilPermissao(Base):
    """Uma permissão concedida por um perfil. `permission='*'` concede todas."""

    __tablename__ = "perfil_permissoes"
    id = Column(Integer, primary_key=True)
    perfil_id = Column(Integer, ForeignKey("perfis.id"), nullable=False, index=True)
    permission = Column(String(50), nullable=False)
    perfil = relationship("Perfil", back_populates="permissoes")
    __table_args__ = (UniqueConstraint("perfil_id", "permission", name="uq_perfil_permissao"),)


class UsuarioPerfil(Base):
    """Atribui um perfil a um usuário, opcionalmente restrito a um recurso.

    `resource_type=NULL` significa atribuição global. Preenchido, o perfil só
    vale naquele recurso e abaixo dele — é o que permite "Fornecedor A é
    fornecedor NO projeto X e não enxerga nada fora dali".
    """

    __tablename__ = "usuario_perfis"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    perfil_id = Column(Integer, ForeignKey("perfis.id"), nullable=False, index=True)
    resource_type = Column(String(20), nullable=True)
    resource_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    usuario = relationship("User")
    perfil = relationship("Perfil")
    __table_args__ = (
        UniqueConstraint(
            "usuario_id", "perfil_id", "resource_type", "resource_id",
            name="uq_usuario_perfil_escopo",
        ),
    )


class ACLEntry(Base):
    """Concessão ou negação explícita de uma permissão.

    Sujeito (usuário, grupo ou perfil) x recurso (global, ambiente, área,
    projeto ou documento) x permissão, com `allow` True/False.

    `allow=False` é a negação explícita exigida pela FASE 1: dentro de um mesmo
    nível ela vence qualquer concessão. Ver `PermissionService` para a ordem de
    resolução completa.
    """

    __tablename__ = "acl_entries"
    id = Column(Integer, primary_key=True)
    subject_type = Column(String(20), nullable=False)
    subject_id = Column(Integer, nullable=False)
    resource_type = Column(String(20), nullable=False)
    # NULL para resource_type='global' — a raiz não tem id.
    resource_id = Column(Integer, nullable=True)
    permission = Column(String(50), nullable=False)
    allow = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    created_by_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    created_by = relationship("User")
    __table_args__ = (
        UniqueConstraint(
            "subject_type", "subject_id", "resource_type", "resource_id", "permission",
            name="uq_acl_subject_resource_permission",
        ),
        # A resolução sempre filtra por sujeito; a administração da ACL lista
        # por recurso. Um índice para cada caminho de acesso.
        Index("ix_acl_subject", "subject_type", "subject_id"),
        Index("ix_acl_resource", "resource_type", "resource_id"),
    )
