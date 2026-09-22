"""Schemas da administração de permissões."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indoc.permissions.constants import (
    QUALQUER_PERMISSAO,
    TODAS_PERMISSOES,
    Permission,
    ResourceType,
    SubjectType,
)


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _validar_permissao(v: str) -> str:
    if v != QUALQUER_PERMISSAO and v not in TODAS_PERMISSOES:
        raise ValueError(
            f"permissão inválida: '{v}'. Use uma de {sorted(TODAS_PERMISSOES)} ou '*'"
        )
    return v


# ── grupos ──────────────────────────────────────────────────────────────

class GrupoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    descricao: Optional[str] = None


class GrupoUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=200)
    descricao: Optional[str] = None
    ativo: Optional[bool] = None


class GrupoOut(_Base):
    id: int
    nome: str
    descricao: Optional[str] = None
    ativo: bool
    total_membros: int = 0


class MembroOut(_Base):
    id: int
    username: str
    email: str


# ── perfis ──────────────────────────────────────────────────────────────

class PerfilCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    descricao: Optional[str] = None
    permissoes: list[str] = []

    @field_validator("permissoes")
    @classmethod
    def _permissoes_validas(cls, v: list[str]) -> list[str]:
        return [_validar_permissao(p) for p in v]


class PerfilUpdate(BaseModel):
    descricao: Optional[str] = None
    ativo: Optional[bool] = None
    permissoes: Optional[list[str]] = None

    @field_validator("permissoes")
    @classmethod
    def _permissoes_validas(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return None if v is None else [_validar_permissao(p) for p in v]


class PerfilOut(_Base):
    id: int
    nome: str
    descricao: Optional[str] = None
    sistema: bool
    ativo: bool
    permissoes: list[str] = []


# ── atribuição de perfil ────────────────────────────────────────────────

class AtribuirPerfil(BaseModel):
    """Escopo opcional: sem `resource_type`, o perfil vale globalmente."""

    perfil_id: int
    resource_type: Optional[ResourceType] = None
    resource_id: Optional[int] = None

    @model_validator(mode="after")
    def _escopo_coerente(self):
        if self.resource_type is None and self.resource_id is not None:
            raise ValueError("resource_id sem resource_type")
        if (
            self.resource_type is not None
            and self.resource_type != ResourceType.GLOBAL
            and self.resource_id is None
        ):
            raise ValueError(f"resource_type '{self.resource_type.value}' exige resource_id")
        return self


class UsuarioPerfilOut(_Base):
    id: int
    perfil_id: int
    perfil_nome: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None


# ── ACL ─────────────────────────────────────────────────────────────────

class ACLCreate(BaseModel):
    subject_type: SubjectType
    subject_id: int
    resource_type: ResourceType
    resource_id: Optional[int] = None
    permission: str
    allow: bool = True

    @field_validator("permission")
    @classmethod
    def _permissao_valida(cls, v: str) -> str:
        return _validar_permissao(v)

    @model_validator(mode="after")
    def _escopo_coerente(self):
        if self.resource_type == ResourceType.GLOBAL and self.resource_id is not None:
            raise ValueError("recurso global não tem resource_id")
        if self.resource_type != ResourceType.GLOBAL and self.resource_id is None:
            raise ValueError(f"resource_type '{self.resource_type.value}' exige resource_id")
        return self


class ACLOut(_Base):
    id: int
    subject_type: str
    subject_id: int
    resource_type: str
    resource_id: Optional[int] = None
    permission: str
    allow: bool
    created_at: Optional[datetime] = None


# ── consulta de permissões efetivas ─────────────────────────────────────

class PermissoesEfetivasOut(BaseModel):
    """O que um usuário pode, de fato, num recurso. Para a UI e para suporte."""

    usuario_id: int
    resource_type: str
    resource_id: Optional[int] = None
    is_admin: bool
    permissoes: list[str]


class CatalogoOut(BaseModel):
    """Vocabulário aceito pela API — evita a UI hardcodar as listas."""

    permissoes: list[str] = [p.value for p in Permission]
    subject_types: list[str] = [s.value for s in SubjectType]
    resource_types: list[str] = [r.value for r in ResourceType]
