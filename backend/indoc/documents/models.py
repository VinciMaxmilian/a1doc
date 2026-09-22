from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from indoc.core.database import Base
from indoc.core.time import utcnow


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
