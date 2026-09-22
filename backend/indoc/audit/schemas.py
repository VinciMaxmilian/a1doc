"""Schemas da auditoria (FASE 3)."""
import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, computed_field, field_serializer


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    username: Optional[str] = None
    session_id: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    project_id: Optional[int] = None
    document_id: Optional[int] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    before_json: Optional[str] = None
    after_json: Optional[str] = None
    metadata_json: Optional[str] = None

    @field_serializer("timestamp")
    def _serialize_timestamp(self, dt: datetime) -> str:
        """Gravado em UTC naïve; explicita o fuso para o cliente."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    # Os três campos JSON são devolvidos também já decodificados, para o front
    # não precisar fazer JSON.parse de string dentro de JSON.
    @computed_field
    @property
    def before(self) -> Optional[Any]:
        return _decodificar(self.before_json)

    @computed_field
    @property
    def after(self) -> Optional[Any]:
        return _decodificar(self.after_json)

    @computed_field
    @property
    def detalhes(self) -> Optional[Any]:
        return _decodificar(self.metadata_json)


def _decodificar(bruto: Optional[str]) -> Optional[Any]:
    if not bruto:
        return None
    try:
        return json.loads(bruto)
    except ValueError:
        # Conteúdo antigo ou corrompido não pode derrubar a consulta.
        return {"_bruto": bruto}


class PaginaAuditoriaOut(BaseModel):
    total: int
    skip: int
    limit: int
    itens: list[AuditLogOut]


class CatalogoAuditoriaOut(BaseModel):
    acoes: list[str]
