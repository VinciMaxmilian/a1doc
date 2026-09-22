"""AuditLog (FASE 3).

Registro append-only: a aplicação escreve e lê, nunca atualiza nem apaga. Não
existe endpoint de UPDATE ou DELETE — a ausência é a garantia.

Os campos `project_id` e `document_id` são desnormalizados de propósito: a
consulta de auditoria quase sempre pergunta "o que aconteceu neste projeto /
neste documento", e reconstruir isso por join com `entity_type/entity_id`
exigiria um join diferente por tipo de entidade.

Sem FK em `user_id`, `project_id` e `document_id`: o log tem que sobreviver à
exclusão da entidade que ele descreve. Um registro de "documento X excluído"
que some junto com o documento não serve para nada.
"""
from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from indoc.core.database import Base
from indoc.core.time import utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)

    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(100), nullable=True)   # congelado: o usuário pode sumir
    session_id = Column(Integer, nullable=True)

    action = Column(String(60), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)

    project_id = Column(Integer, nullable=True, index=True)
    document_id = Column(Integer, nullable=True, index=True)

    ip = Column(String(45), nullable=True)
    user_agent = Column(String(400), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)

    # JSON em Text, não JSON nativo: a consulta nunca filtra por dentro desses
    # campos — eles são evidência para leitura humana, e Text não impõe o
    # limite de tamanho que a coluna JSON do MySQL impõe.
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)

    __table_args__ = (
        # A tela de auditoria filtra por entidade e ordena por data.
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_user_ts", "user_id", "timestamp"),
    )
