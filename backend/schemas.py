import re
from pydantic import BaseModel, field_validator
from typing import Optional, List

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ROLES = {"user", "admin", "dev"}
_ACOES = {"aprovado", "reprovado"}


class UsuarioCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("email inválido")
        return v

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        if v not in _ROLES:
            raise ValueError(f"role inválido (use um de {_ROLES})")
        return v


class AmbienteCreate(BaseModel):
    nome: str


class AreaCreate(BaseModel):
    nome: str
    ambiente_id: int


class ProjetoCreate(BaseModel):
    nome: str
    area_id: int


class TipoDocumentoCreate(BaseModel):
    nome: str


class CampoFormularioCreate(BaseModel):
    tipo_documento_id: int
    nome: str
    tipo: str = "text"
    opcoes: Optional[List[str]] = None
    ordem: int = 0


class FluxoCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None


class AtividadeCreate(BaseModel):
    nome: str
    fluxo_id: int


class ConfigTransicaoCreate(BaseModel):
    atividade_origem_id: int
    acao: str
    atividade_destino_id: int
    gera_nova_revisao: bool = False

    @field_validator("acao")
    @classmethod
    def _valid_acao(cls, v: str) -> str:
        if v not in _ACOES:
            raise ValueError(f"acao inválida (use um de {_ACOES})")
        return v


class UsuarioUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class TransicaoRequest(BaseModel):
    acao: str
    observacao: Optional[str] = None

    @field_validator("acao")
    @classmethod
    def _valid_acao(cls, v: str) -> str:
        if v not in _ACOES:
            raise ValueError(f"acao inválida (use um de {_ACOES})")
        return v


class ValorCampoItem(BaseModel):
    campo_id: int
    valor: str


class CamposUpdate(BaseModel):
    valores: List[ValorCampoItem]
