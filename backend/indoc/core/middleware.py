"""Middlewares de infraestrutura."""
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

from indoc.core.request_context import (
    get_request_id,
    novo_request_id,
    request_id_valido,
    reset_origem,
    reset_request_id,
    set_origem,
    set_request_id,
)

HEADER = "X-Request-ID"

logger = logging.getLogger("indoc.request")


def ip_do_cliente(request) -> str | None:
    """IP de origem.

    `X-Forwarded-For` só é considerado quando há proxy confiável à frente —
    caso contrário qualquer cliente forjaria o IP que vai para a auditoria e
    para o bloqueio por força bruta. Ligue com TRUST_PROXY_HEADERS=true apenas
    se a API estiver de fato atrás de um proxy que reescreve esse header.
    """
    import config

    if getattr(config, "TRUST_PROXY_HEADERS", False):
        encaminhado = request.headers.get("X-Forwarded-For")
        if encaminhado:
            # O primeiro da lista é o cliente original.
            return encaminhado.split(",")[0].strip()[:45]
    return request.client.host if request.client else None


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Atribui um id a cada requisição, ecoa no header e loga o desfecho.

    Também publica IP e user-agent no contexto, para a auditoria (FASE 3) não
    precisar receber o `Request` em cada camada.

    Reaproveita o `X-Request-ID` enviado pelo cliente quando ele respeita o
    formato aceito — isso permite correlacionar com um proxy/gateway à frente.
    Caso contrário gera um id novo: nunca confiamos no valor recebido às cegas.
    """

    async def dispatch(self, request, call_next):
        recebido = request.headers.get(HEADER)
        rid = recebido if request_id_valido(recebido) else novo_request_id()
        token = set_request_id(rid)
        token_origem = set_origem(ip_do_cliente(request), request.headers.get("User-Agent"))
        inicio = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # O log sai aqui porque o handler de exceção do Starlette roda fora
            # deste escopo — lá o ContextVar já teria sido resetado.
            logger.exception(
                "%s %s -> erro nao tratado", request.method, request.url.path
            )
            raise
        else:
            response.headers[HEADER] = rid
            logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - inicio) * 1000,
            )
            return response
        finally:
            reset_origem(token_origem)
            reset_request_id(token)


class RequestIdFilter(logging.Filter):
    """Injeta `request_id` em todo LogRecord que passa pelo handler.

    É um filtro de handler, não de logger: assim vale para os registros de
    bibliotecas de terceiros também, e o formatter pode usar %(request_id)s
    sem risco de KeyError.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True
