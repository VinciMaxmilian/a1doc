"""Correlação e contexto da requisição.

Um identificador por requisição, mais quem/de onde, propagados via `ContextVar`
para que qualquer log ou registro de auditoria emitido durante o tratamento —
router, service, repositório — possa ser amarrado à chamada que o originou.

Sem isto, `AuditLog.request_id`, `.ip` e `.user_agent` nasceriam vazios, ou
cada função da pilha teria que receber o `Request` só para repassá-lo adiante.
"""
import re
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

SEM_REQUISICAO = "-"

_request_id: ContextVar[str] = ContextVar("request_id", default=SEM_REQUISICAO)

# Um id vindo do cliente é ecoado no header da resposta e vai para os logs.
# Sem restringir o alfabeto, um valor com \r\n permitiria injeção de header, e
# um valor gigante poluiria o log. Fora deste formato, geramos um id próprio.
_ID_ACEITO = re.compile(r"\A[A-Za-z0-9._-]{1,64}\Z")


@dataclass(frozen=True)
class OrigemRequisicao:
    ip: Optional[str] = None
    user_agent: Optional[str] = None


SEM_ORIGEM = OrigemRequisicao()

# Default None, não a instância: mesmo sendo um dataclass frozen, um objeto como
# default de ContextVar é compartilhado por todo o processo. `get_origem`
# devolve o singleton vazio quando não há requisição.
_origem: ContextVar[Optional[OrigemRequisicao]] = ContextVar("origem", default=None)


def novo_request_id() -> str:
    return uuid.uuid4().hex


def request_id_valido(valor: Optional[str]) -> bool:
    return bool(valor and _ID_ACEITO.match(valor))


def get_request_id() -> str:
    """Id da requisição atual, ou "-" fora de uma (worker Celery, script)."""
    return _request_id.get()


def set_request_id(valor: str):
    """Define o id e devolve o token para restaurar o valor anterior."""
    return _request_id.set(valor)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def get_origem() -> OrigemRequisicao:
    """IP e user-agent da requisição atual, ou vazio fora de uma."""
    return _origem.get() or SEM_ORIGEM


def set_origem(ip: Optional[str], user_agent: Optional[str]):
    # user_agent cabe em VARCHAR(400) na auditoria e na sessão; cortar aqui
    # evita estourar a coluna com um header absurdo.
    ua = (user_agent or "")[:400] or None
    return _origem.set(OrigemRequisicao(ip=ip, user_agent=ua))


def reset_origem(token) -> None:
    _origem.reset(token)
