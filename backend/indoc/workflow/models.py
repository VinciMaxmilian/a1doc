from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from indoc.core.database import Base
from indoc.core.time import utcnow


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
