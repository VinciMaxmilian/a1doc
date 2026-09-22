"""Correlação de requisições.

Um identificador por requisição, propagado via `ContextVar` para que qualquer
log emitido durante o tratamento — router, service, repositório — possa ser
amarrado à chamada que o originou.

O `AuditLog` da FASE 3 grava `request_id`. Sem isto ele nasceria vazio.
"""
import re
import uuid
from contextvars import ContextVar

SEM_REQUISICAO = "-"

_request_id: ContextVar[str] = ContextVar("request_id", default=SEM_REQUISICAO)

# Um id vindo do cliente é ecoado no header da resposta e vai para os logs.
# Sem restringir o alfabeto, um valor com \r\n permitiria injeção de header, e
# um valor gigante poluiria o log. Fora deste formato, geramos um id próprio.
_ID_ACEITO = re.compile(r"\A[A-Za-z0-9._-]{1,64}\Z")


def novo_request_id() -> str:
    return uuid.uuid4().hex


def request_id_valido(valor: str | None) -> bool:
    return bool(valor and _ID_ACEITO.match(valor))


def get_request_id() -> str:
    """Id da requisição atual, ou "-" fora de uma (worker Celery, script)."""
    return _request_id.get()


def set_request_id(valor: str):
    """Define o id e devolve o token para restaurar o valor anterior."""
    return _request_id.set(valor)


def reset_request_id(token) -> None:
    _request_id.reset(token)
