from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


def utcnow() -> datetime:
    """UTC naïve (compatível com coluna DATETIME do MySQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # dev, admin, user
    is_active = Column(Boolean, default=True)


class Ambiente(Base):
    __tablename__ = "ambientes"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    areas = relationship("Area", back_populates="ambiente", cascade="all, delete-orphan")


class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    ambiente_id = Column(Integer, ForeignKey("ambientes.id"), nullable=False)
    ambiente = relationship("Ambiente", back_populates="areas")
    projetos = relationship("Projeto", back_populates="area", cascade="all, delete-orphan")


class Projeto(Base):
    __tablename__ = "projetos"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)
    area = relationship("Area", back_populates="projetos")


class TipoDocumento(Base):
    __tablename__ = "tipos_documento"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    campos = relationship(
        "CampoFormulario", back_populates="tipo_documento",
        cascade="all, delete-orphan", order_by="CampoFormulario.ordem"
    )


class CampoFormulario(Base):
    __tablename__ = "campos_formulario"
    id = Column(Integer, primary_key=True)
    tipo_documento_id = Column(Integer, ForeignKey("tipos_documento.id"), nullable=False)
    nome = Column(String(200), nullable=False)
    tipo = Column(String(50), default="text")  # text, number, date, select
    opcoes = Column(JSON, nullable=True)
    ordem = Column(Integer, default=0)
    tipo_documento = relationship("TipoDocumento", back_populates="campos")


class Fluxo(Base):
    __tablename__ = "fluxos"
    id = Column(Integer, primary_key=True)
    numero = Column(Integer, nullable=False, unique=True)
    nome = Column(String(200), nullable=False)
    descricao = Column(Text, nullable=True)
    atividades = relationship(
        "Atividade", back_populates="fluxo",
        cascade="all, delete-orphan", order_by="(Atividade.ordem, Atividade.id)"
    )


class Atividade(Base):
    __tablename__ = "atividades"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    fluxo_id = Column(Integer, ForeignKey("fluxos.id"), nullable=False, index=True)
    ordem = Column(Integer, default=0, nullable=False)
    # Papel exigido para transitar a partir desta atividade.
    # NULL = qualquer usuário autenticado. Admin/dev sempre podem.
    role_requerido = Column(String(20), nullable=True)
    fluxo = relationship("Fluxo", back_populates="atividades")
    transicoes = relationship(
        "ConfigTransicao", foreign_keys="ConfigTransicao.atividade_origem_id",
        back_populates="atividade_origem", cascade="all, delete-orphan"
    )


class ConfigTransicao(Base):
    __tablename__ = "config_transicoes"
    id = Column(Integer, primary_key=True)
    atividade_origem_id = Column(Integer, ForeignKey("atividades.id"), nullable=False)
    acao = Column(String(20), nullable=False)  # aprovado, reprovado
    atividade_destino_id = Column(Integer, ForeignKey("atividades.id"), nullable=False)
    gera_nova_revisao = Column(Boolean, default=False)
    atividade_origem = relationship("Atividade", foreign_keys=[atividade_origem_id], back_populates="transicoes")
    atividade_destino = relationship("Atividade", foreign_keys=[atividade_destino_id])
    __table_args__ = (UniqueConstraint("atividade_origem_id", "acao", name="uq_transicao_origem_acao"),)


class Documento(Base):
    __tablename__ = "documentos"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(100), unique=True, nullable=False)
    nome = Column(String(500), nullable=False, index=True)
    ambiente_id = Column(Integer, ForeignKey("ambientes.id"), nullable=False, index=True)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id"), nullable=False, index=True)
    tipo_documento_id = Column(Integer, ForeignKey("tipos_documento.id"), nullable=False, index=True)
    responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    atividade_atual_id = Column(Integer, ForeignKey("atividades.id"), nullable=True)
    revisao_indice = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    ambiente = relationship("Ambiente")
    area = relationship("Area")
    projeto = relationship("Projeto")
    tipo_documento = relationship("TipoDocumento")
    responsavel = relationship("User", foreign_keys=[responsavel_id])
    atividade_atual = relationship("Atividade", foreign_keys=[atividade_atual_id])
    arquivos = relationship("DocumentoArquivo", back_populates="documento", order_by="DocumentoArquivo.created_at")
    historico = relationship("HistoricoWorkflow", back_populates="documento", order_by="HistoricoWorkflow.created_at")
    valores_campos = relationship("ValorCampo", back_populates="documento")


class DocumentoArquivo(Base):
    __tablename__ = "documento_arquivos"
    id = Column(Integer, primary_key=True)
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=False, index=True)
    arquivo_nome = Column(String(500), nullable=False)
    arquivo_path = Column(String(1000), nullable=False)
    revisao_indice = Column(Integer, default=0)
    observacao = Column(Text, nullable=True)
    atividade_id = Column(Integer, ForeignKey("atividades.id"), nullable=True)
    uploaded_by_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    documento = relationship("Documento", back_populates="arquivos")
    uploaded_by = relationship("User")
    atividade = relationship("Atividade")


class HistoricoWorkflow(Base):
    __tablename__ = "historico_workflow"
    id = Column(Integer, primary_key=True)
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=False, index=True)
    atividade_origem_id = Column(Integer, ForeignKey("atividades.id"), nullable=True)
    atividade_destino_id = Column(Integer, ForeignKey("atividades.id"), nullable=False)
    acao = Column(String(50))
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    observacao = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    documento = relationship("Documento", back_populates="historico")
    user = relationship("User")
    atividade_origem = relationship("Atividade", foreign_keys=[atividade_origem_id])
    atividade_destino = relationship("Atividade", foreign_keys=[atividade_destino_id])


class ValorCampo(Base):
    __tablename__ = "valores_campo"
    id = Column(Integer, primary_key=True)
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=False, index=True)
    campo_id = Column(Integer, ForeignKey("campos_formulario.id"), nullable=False)
    valor = Column(Text, nullable=True)
    documento = relationship("Documento", back_populates="valores_campos")
    campo = relationship("CampoFormulario")
    __table_args__ = (UniqueConstraint("documento_id", "campo_id", name="uq_valor_campo"),)


class UploadJob(Base):
    __tablename__ = "upload_jobs"
    id = Column(String(36), primary_key=True)
    status = Column(String(20), default="pendente")  # pendente, processando, concluido, erro
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=True)
    erro_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    documento = relationship("Documento")
