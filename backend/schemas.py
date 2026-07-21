"""Schemas Pydantic: entrada (validação) e saída (response_model)."""
from datetime import datetime, timezone
from typing import Literal, Optional

import email_validator
from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_serializer

# GED corporativo costuma rodar em rede interna: domínios como "empresa.local"
# são legítimos aqui, embora o email-validator os rejeite por padrão.
email_validator.SPECIAL_USE_DOMAIN_NAMES = [
    d for d in email_validator.SPECIAL_USE_DOMAIN_NAMES if d != "local"
]

Role = Literal["user", "admin", "dev"]
Acao = Literal["aprovado", "reprovado"]
TipoCampo = Literal["text", "number", "date", "select", "textarea"]


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class _ComData(_Base):
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, dt: datetime) -> str:
        """Datas são gravadas em UTC naïve; explicita o fuso para o cliente."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


class _ComRevisao(_Base):
    revisao_indice: int

    @computed_field
    @property
    def revisao_label(self) -> str:
        """Revisão exibida ao usuário é 1-based; o índice interno é 0-based."""
        return str(self.revisao_indice + 1)


# ══════════════════════ Entrada ══════════════════════

class UsuarioCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    role: Role = "user"


class UsuarioUpdate(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class AmbienteCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=200)


class AreaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    ambiente_id: int


class ProjetoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    area_id: int


class TipoDocumentoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=200)


class CampoFormularioCreate(BaseModel):
    # tipo_documento_id vem pela URL; mantido opcional por compatibilidade do cliente.
    tipo_documento_id: Optional[int] = None
    nome: str = Field(min_length=1, max_length=200)
    tipo: TipoCampo = "text"
    opcoes: Optional[list[str]] = None
    ordem: int = 0


class FluxoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    descricao: Optional[str] = None


class AtividadeCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    fluxo_id: int
    ordem: int = 0
    role_requerido: Optional[Role] = None


class ConfigTransicaoCreate(BaseModel):
    atividade_origem_id: int
    acao: Acao
    atividade_destino_id: int
    gera_nova_revisao: bool = False


class TransicaoRequest(BaseModel):
    acao: Acao
    observacao: Optional[str] = None


class ValorCampoItem(BaseModel):
    campo_id: int
    valor: str


class CamposUpdate(BaseModel):
    valores: list[ValorCampoItem]


# ══════════════════════ Saída ══════════════════════

class OkOut(BaseModel):
    ok: bool = True


class UsuarioOut(_Base):
    id: int
    username: str
    email: str
    role: str


class UsuarioAdminOut(UsuarioOut):
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    user: UsuarioOut


class UserRefOut(_Base):
    id: int
    username: str


class AmbienteOut(_Base):
    id: int
    nome: str


class AreaOut(_Base):
    id: int
    nome: str
    ambiente_id: int


class ProjetoOut(_Base):
    id: int
    nome: str
    area_id: int


class AreaTreeOut(AreaOut):
    projetos: list[ProjetoOut] = []


class AmbienteTreeOut(AmbienteOut):
    areas: list[AreaTreeOut] = []


class TipoDocumentoOut(_Base):
    id: int
    nome: str


class CampoFormularioOut(_Base):
    id: int
    nome: str
    tipo: str
    opcoes: Optional[list[str]] = None
    ordem: int


class AtividadeOut(_Base):
    id: int
    nome: str
    fluxo_id: int
    ordem: int = 0
    role_requerido: Optional[str] = None


class FluxoRefOut(_Base):
    id: int
    numero: int
    nome: str


class FluxoOut(FluxoRefOut):
    descricao: Optional[str] = None
    atividades: list[AtividadeOut] = []


class AtividadeDocOut(AtividadeOut):
    fluxo: FluxoRefOut


class AtividadeRefOut(_Base):
    id: int
    nome: str


class HistoricoAtividadeOut(_Base):
    id: int
    nome: str
    fluxo_id: int


class TransicaoOut(_Base):
    id: int
    atividade_origem_id: int
    atividade_origem_nome: str
    acao: str
    atividade_destino_id: int
    atividade_destino_nome: str
    gera_nova_revisao: bool


class DocumentoOut(_ComRevisao, _ComData):
    id: int
    codigo: str
    nome: str
    ambiente_id: int
    area_id: int
    projeto_id: int
    tipo_documento_id: int
    responsavel: UserRefOut
    atividade_atual: Optional[AtividadeDocOut] = None


class ArquivoOut(_ComRevisao, _ComData):
    id: int
    arquivo_nome: str
    observacao: Optional[str] = None
    atividade: Optional[AtividadeRefOut] = None
    uploaded_by: UserRefOut


class HistoricoOut(_ComData):
    id: int
    atividade_origem: Optional[HistoricoAtividadeOut] = None
    atividade_destino: HistoricoAtividadeOut
    acao: Optional[str] = None
    observacao: Optional[str] = None
    user: UserRefOut


class ValorCampoOut(BaseModel):
    campo_id: int
    campo_nome: str
    campo_tipo: str
    opcoes: Optional[list[str]] = None
    valor: Optional[str] = None


class DocumentoDetalheOut(DocumentoOut):
    arquivos: list[ArquivoOut] = []
    historico: list[HistoricoOut] = []
    # O alias impede que `from_attributes` tente ler a relação ORM homônima
    # (ValorCampo não tem campo_nome/campo_tipo). O router preenche depois,
    # cruzando os valores com a definição do formulário.
    valores_campos: list[ValorCampoOut] = Field(
        default=[], validation_alias="_valores_campos_montados"
    )


class PaginaDocumentosOut(BaseModel):
    total: int
    skip: int
    limit: int
    itens: list[DocumentoOut]


class UploadAceitoOut(BaseModel):
    job_id: str
    status: str
    total_arquivos: int


class JobOut(_ComData):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    job_id: str = Field(validation_alias="id")
    status: str
    documento_id: Optional[int] = None
    erro_msg: Optional[str] = None
