"""Schemas de autenticação (FASE 2)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginFirebase(BaseModel):
    id_token: str = Field(min_length=10)


class UsuarioSessaoOut(_Base):
    id: int
    username: str
    email: str
    role: str


class LoginOut(BaseModel):
    """Resposta do login.

    `access_token` continua no corpo por compatibilidade com clientes de API.
    O navegador não precisa dele: os cookies já foram definidos na resposta, e
    o front usa `csrf_token` para os métodos que mudam estado.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    csrf_token: str
    user: UsuarioSessaoOut


class SessaoOut(_Base):
    id: int
    provider: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    atual: bool = False
    ativa: bool = False


class ProvidersOut(BaseModel):
    """Como o front descobre quais formas de login oferecer."""

    providers: list[str]
    firebase_project_id: Optional[str] = None


class RevogacaoOut(BaseModel):
    revogadas: int
