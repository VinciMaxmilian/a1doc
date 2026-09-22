"""Registro de auditoria (FASE 3).

Uma função: `registrar(...)`. Ela pega sozinha o que dá para pegar do contexto
da requisição (IP, user-agent, request_id), e o chamador informa o que só ele
sabe (ação, entidade, antes/depois).

## Por que não é um middleware automático

Um middleware sabe o método HTTP e a rota, mas não sabe *o que mudou*. Os
campos `before_json`/`after_json` exigem conhecimento do domínio, e uma
auditoria que só diz "houve um PUT em /documentos/7" não responde à pergunta
que a auditoria existe para responder. Por isso o registro é explícito nos
pontos que importam.

## Por que a falha de auditoria não derruba a operação

Se gravar o log falhar, a operação de negócio que já aconteceu não é desfeita —
o erro vai para o log da aplicação. A alternativa (falhar a requisição) tornaria
a auditoria um ponto único de indisponibilidade do sistema inteiro. A FASE 62
(observabilidade) deve alarmar sobre esses erros.
"""
import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from indoc.audit.actions import Action
from indoc.audit.models import AuditLog
from indoc.core.request_context import get_origem, get_request_id
from indoc.core.time import utcnow

logger = logging.getLogger("indoc.audit")

# Nunca gravar credencial na auditoria, venha de onde vier.
_CAMPOS_SENSIVEIS = frozenset({
    "password", "senha", "hashed_password", "token", "access_token",
    "refresh_token", "id_token", "csrf_token", "secret", "authorization",
})
_OCULTO = "***"


# Profundidade máxima ao sanitizar. Um payload aninhado além disto é evidência
# ruim de qualquer jeito, e a poda evita estourar a pilha.
_PROFUNDIDADE_MAX = 20


def _limpar(valor: Any, _profundidade: int = 0, _vistos: Optional[set[int]] = None) -> Any:
    """Remove segredos recursivamente antes de serializar.

    Detecta ciclos e limita a profundidade: sem isso, um payload com referência
    circular estouraria `RecursionError` — que não é `TypeError`/`ValueError` e
    portanto escaparia do fallback, fazendo o evento inteiro se perder. Nenhum
    formato de payload pode custar um registro de auditoria.
    """
    if _profundidade > _PROFUNDIDADE_MAX:
        return "<profundidade máxima excedida>"

    if isinstance(valor, (dict, list, tuple)):
        _vistos = set() if _vistos is None else _vistos
        if id(valor) in _vistos:
            return "<referência circular>"
        _vistos = _vistos | {id(valor)}

    if isinstance(valor, dict):
        return {
            k: (
                _OCULTO if str(k).lower() in _CAMPOS_SENSIVEIS
                else _limpar(v, _profundidade + 1, _vistos)
            )
            for k, v in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [_limpar(v, _profundidade + 1, _vistos) for v in valor]
    return valor


def _json(valor: Optional[Any]) -> Optional[str]:
    if valor is None:
        return None
    try:
        return json.dumps(_limpar(valor), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps({"_erro": "valor não serializável", "_repr": repr(valor)[:500]})


def snapshot(obj: Any, campos: tuple[str, ...]) -> dict:
    """Fotografia dos campos de um objeto ORM, para before/after.

    Campos explícitos em vez do objeto inteiro: evita arrastar relações,
    `hashed_password` e o `_sa_instance_state` para dentro do log.
    """
    return {c: getattr(obj, c, None) for c in campos}


def registrar(
    db: Session,
    action: Action | str,
    *,
    user=None,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    project_id: Optional[int] = None,
    document_id: Optional[int] = None,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
    metadata: Optional[dict] = None,
    commit: bool = True,
) -> Optional[AuditLog]:
    """Grava um evento. Nunca levanta exceção para o chamador."""
    try:
        origem = get_origem()
        registro = AuditLog(
            timestamp=utcnow(),
            user_id=user.id if user is not None else user_id,
            # Username congelado: o log precisa continuar legível depois que o
            # usuário for excluído ou renomeado.
            username=getattr(user, "username", None),
            session_id=session_id,
            action=str(action),
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            document_id=document_id,
            ip=origem.ip,
            user_agent=origem.user_agent,
            request_id=get_request_id(),
            before_json=_json(before),
            after_json=_json(after),
            metadata_json=_json(metadata),
        )
        db.add(registro)
        if commit:
            db.commit()
        else:
            db.flush()
        return registro
    except Exception:
        logger.exception("Falha ao gravar auditoria (action=%s)", action)
        # `rollback` só quando somos donos da transação (commit=True). Com
        # commit=False quem manda é o chamador: desfazer a transação dele aqui
        # apagaria silenciosamente a operação de negócio que ele já fez. Se a
        # sessão ficou de fato quebrada, o commit dele falha e o erro aparece
        # onde deve aparecer, em vez de sumir dentro da auditoria.
        if commit:
            try:
                db.rollback()
            except Exception:
                logger.exception("Falha no rollback após erro de auditoria")
        return None


__all__ = ["registrar", "snapshot", "Action"]
