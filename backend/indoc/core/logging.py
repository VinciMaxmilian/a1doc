"""Configuração de logging da aplicação.

Dois formatos, escolhidos por `LOG_FORMAT`:

- `text` (default): legível no terminal, com o request_id entre colchetes.
- `json`: um objeto por linha, para Loki/CloudWatch/Elastic — a forma que a
  FASE 62 (observabilidade) vai consumir.

Em ambos, `request_id` vem do ContextVar preenchido pelo RequestIdMiddleware.
"""
import json
import logging

from indoc.core.middleware import RequestIdFilter

TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Atributos que o logging já põe em todo LogRecord; o resto é contexto extra
# passado pelo chamador via `logger.info(..., extra={...})`.
_PADRAO = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "asctime", "message", "taskName", "request_id",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        evento = {
            "ts": self.formatTime(record, DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            evento["exc"] = self.formatException(record.exc_info)
        for chave, valor in record.__dict__.items():
            if chave not in _PADRAO:
                evento[chave] = valor
        return json.dumps(evento, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", formato: str = "text") -> None:
    """Configura o logger raiz. Idempotente — reaplica nível e filtro."""
    root = logging.getLogger()
    handler = root.handlers[0] if root.handlers else logging.StreamHandler()

    if formato == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT, datefmt=DATE_FORMAT))

    if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
        handler.addFilter(RequestIdFilter())

    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(level)
