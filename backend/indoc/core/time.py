"""Relógio da aplicação.

Todos os `default=` de coluna usam `utcnow`. Centralizado para que o dia em que
for preciso trocar por um clock injetável (testes de SLA, FASE 12) haja um
único ponto a mudar.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """UTC naïve (compatível com coluna DATETIME do MySQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
