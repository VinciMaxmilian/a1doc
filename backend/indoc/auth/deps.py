"""Dependências de autenticação (FASE 2).

## Duas origens de credencial

O access token é aceito de duas formas:

1. **cookie `indoc_access`** (HttpOnly) — o navegador. É o caminho seguro: um
   XSS não consegue ler o cookie, ao contrário do `localStorage` de antes.
2. **header `Authorization: Bearer`** — clientes programáticos, scripts, CI.

Manter o header não reintroduz a falha que a FASE 2 corrige: o problema nunca
foi o cabeçalho, foi guardar a credencial num lugar legível por script dentro
do navegador. Um script que decide mandar `Authorization` já tem o token por
outro meio.

## CSRF

Aceitar cookie significa que o navegador anexa a credencial sozinho, inclusive
numa requisição disparada por outro site. `SameSite` barra a maior parte disso,
mas não tudo (e não em navegador antigo). Por isso, requisição que **muda
estado** e se autentica **por cookie** precisa ecoar o token CSRF no header
`X-CSRF-Token`.

Quem se autentica por `Authorization` não precisa: o navegador não injeta esse
header sozinho, então o ataque não existe ali.
"""
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import config
from database import get_db
from indoc.auth import tokens
from indoc.auth.models import UserSession
from indoc.users.models import User

# auto_error=False: a ausência do header não é erro — pode haver cookie.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class Credencial:
    """De onde veio a autenticação desta requisição."""

    def __init__(self, token: str, via_cookie: bool):
        self.token = token
        self.via_cookie = via_cookie


def _extrair(request: Request, header_token: Optional[str]) -> Credencial:
    cookie_token = request.cookies.get(config.COOKIE_ACCESS)
    # O header ganha do cookie quando os dois vêm: um cliente que se deu ao
    # trabalho de mandar Authorization está pedindo explicitamente por ele.
    if header_token:
        return Credencial(header_token, via_cookie=False)
    if cookie_token:
        return Credencial(cookie_token, via_cookie=True)
    raise HTTPException(401, "Não autenticado")


def _conferir_csrf(request: Request, credencial: Credencial) -> None:
    if not credencial.via_cookie or request.method in METODOS_SEGUROS:
        return
    enviado = request.headers.get(config.HEADER_CSRF)
    do_cookie = request.cookies.get(config.COOKIE_CSRF)
    if not enviado or not do_cookie or not tokens.comparar_seguro(enviado, do_cookie):
        raise HTTPException(403, "Token CSRF ausente ou inválido")


def get_current_user(
    request: Request,
    header_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credencial = _extrair(request, header_token)
    _conferir_csrf(request, credencial)

    try:
        payload = tokens.ler_access_token(credencial.token)
        uid = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        # `from None`: o motivo exato da falha do token não vai para o cliente.
        raise HTTPException(401, "Token inválido") from None

    if payload.get("typ") != "access":
        # Impede apresentar um token de outro propósito como se fosse access.
        raise HTTPException(401, "Token inválido")

    sid = payload.get("sid")
    if sid is not None and not _sessao_viva(db, sid, uid):
        # É isto que faz "encerrar sessão" valer de imediato, em vez de só
        # quando o access token expirasse.
        raise HTTPException(401, "Sessão encerrada")

    user = db.query(User).filter(User.id == uid, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(401, "Usuário não encontrado")
    if user.bloqueado_em is not None:
        raise HTTPException(403, user.motivo_bloqueio or "Usuário bloqueado")

    # Guardado no request para a auditoria amarrar o evento à sessão.
    request.state.session_id = sid
    return user


def _sessao_viva(db: Session, session_id: int, usuario_id: int) -> bool:
    sessao = db.query(UserSession).filter(
        UserSession.id == session_id, UserSession.usuario_id == usuario_id
    ).first()
    return bool(sessao and sessao.ativa)


def get_session_id(request: Request) -> Optional[int]:
    return getattr(request.state, "session_id", None)


def is_admin(user: User) -> bool:
    from indoc.permissions.service import ADMIN_ROLES

    return user.role in ADMIN_ROLES


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_admin(user):
        raise HTTPException(403, "Acesso restrito a Admin/Dev")
    return user
