"""Consulta de auditoria (FASE 3).

Só leitura. **Não existe** endpoint de alteração ou exclusão — a ausência é a
garantia de que o log é append-only, e por isso "logs não podem ser editados
por usuários comuns" vale também para os administradores pela API.

Acesso restrito a admin/dev: a auditoria mostra quem acessou o quê em toda a
instalação, inclusive em projetos que o consultante não pode ver. Um filtro por
ACL aqui daria uma visão inconsistente e vazaria a existência de documentos
pelo próprio registro. A FASE 26/27 (portais) deve trazer uma visão de
auditoria restrita ao projeto, quando houver quem precise.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import config
from database import get_db
from indoc.audit.actions import ACOES
from indoc.audit.models import AuditLog
from indoc.audit.schemas import AuditLogOut, CatalogoAuditoriaOut, PaginaAuditoriaOut
from indoc.auth.deps import require_admin

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("/catalogo", response_model=CatalogoAuditoriaOut)
def catalogo(_=Depends(require_admin)):
    """Ações registráveis — a tela monta o filtro a partir daqui."""
    return {"acoes": list(ACOES)}


@router.get("", response_model=PaginaAuditoriaOut)
def listar(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    project_id: Optional[int] = None,
    document_id: Optional[int] = None,
    ip: Optional[str] = None,
    request_id: Optional[str] = None,
    de: Optional[datetime] = Query(None, description="Início do intervalo (ISO 8601)"),
    ate: Optional[datetime] = Query(None, description="Fim do intervalo (ISO 8601)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(config.DEFAULT_PAGE_SIZE, ge=1, le=config.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    q = db.query(AuditLog)

    if user_id is not None:      q = q.filter(AuditLog.user_id == user_id)
    if action:                   q = q.filter(AuditLog.action == action)
    if entity_type:              q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:    q = q.filter(AuditLog.entity_id == entity_id)
    if project_id is not None:   q = q.filter(AuditLog.project_id == project_id)
    if document_id is not None:  q = q.filter(AuditLog.document_id == document_id)
    if ip:                       q = q.filter(AuditLog.ip == ip)
    if request_id:               q = q.filter(AuditLog.request_id == request_id)
    if de:                       q = q.filter(AuditLog.timestamp >= _naive(de))
    if ate:                      q = q.filter(AuditLog.timestamp <= _naive(ate))

    total = q.count()
    itens = q.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()) \
             .offset(skip).limit(limit).all()
    return {"total": total, "skip": skip, "limit": limit, "itens": itens}


@router.get("/{log_id}", response_model=AuditLogOut)
def detalhe(log_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    from fastapi import HTTPException

    registro = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not registro:
        raise HTTPException(404, "Registro não encontrado")
    return registro


def _naive(dt: datetime) -> datetime:
    """As colunas DATETIME guardam UTC naïve; converte o filtro para o mesmo."""
    if dt.tzinfo is None:
        return dt
    from datetime import timezone

    return dt.astimezone(timezone.utc).replace(tzinfo=None)
