"""Emissão e verificação de tokens.

Dois tipos, com papéis distintos:

- **access token**: JWT HS256, curto. Carrega `sub` (usuário) e `sid` (sessão),
  para que revogar a sessão invalide o access na primeira verificação que
  consultar o banco. É o que autentica cada requisição.

- **refresh token**: string opaca aleatória, longa. Não é JWT de propósito —
  não precisa carregar informação e não deve ser inspecionável pelo cliente. É
  gravado só como SHA-256 em `UserSession.refresh_token_hash`.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

import config


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def criar_access_token(user_id: int, session_id: Optional[int] = None) -> str:
    dados = {
        "sub": str(user_id),
        "exp": _agora() + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": _agora(),
        "typ": "access",
    }
    if session_id is not None:
        dados["sid"] = session_id
    return jwt.encode(dados, config.SECRET_KEY, algorithm=config.ALGORITHM)


def ler_access_token(token: str) -> dict:
    """Decodifica e valida o access token. Levanta `jwt.PyJWTError` se inválido."""
    return jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])


def novo_refresh_token() -> str:
    """Segredo opaco. 32 bytes de entropia — não é adivinhável."""
    return secrets.token_urlsafe(32)


def hash_refresh(token: str) -> str:
    """SHA-256 do refresh token.

    Sem salt e sem KDF lento de propósito: diferente de senha, este é um
    segredo aleatório de alta entropia, não sujeito a ataque de dicionário. O
    hash serve para que o banco não guarde a credencial em claro, e precisa ser
    determinístico para permitir a busca por igualdade.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expiracao_refresh() -> datetime:
    """Naïve UTC, como o resto das colunas DATETIME."""
    return (_agora() + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)).replace(tzinfo=None)


def novo_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def comparar_seguro(a: str, b: str) -> bool:
    """Comparação em tempo constante — evita descobrir o token byte a byte."""
    return secrets.compare_digest(a or "", b or "")
