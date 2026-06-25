from pydantic import BaseModel
from typing import Optional, List


class UsuarioCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"


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


class UsuarioUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class TransicaoRequest(BaseModel):
    acao: str
    observacao: Optional[str] = None


class ValorCampoItem(BaseModel):
    campo_id: int
    valor: str


class CamposUpdate(BaseModel):
    valores: List[ValorCampoItem]
