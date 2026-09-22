"""Shim de compatibilidade — a implementação vive em `indoc/core/database.py`.

Mantido para não quebrar `from database import get_db` espalhado pelos routers.
Código novo deve importar de `indoc.core.database`.
"""
from indoc.core.database import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
