"""Rotas de autenticação (FASE 2).

O login emite três cookies (ver `indoc/auth/cookies.py`) e também devolve o
access token no corpo, para clientes de API que não usam cookie.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import config
import models
import schemas
from database import get_db
from indoc.audit.actions import Action
from indoc.audit.service import registrar, snapshot
from indoc.auth import cookies
from indoc.auth.deps import get_current_user, get_session_id, require_admin
from indoc.auth.password import hash_password
from indoc.auth.providers import providers_ativos
from indoc.auth.schemas import (
    LoginFirebase,
    LoginOut,
    ProvidersOut,
    RevogacaoOut,
    SessaoOut,
)
from indoc.auth.service import AuthService
from indoc.permissions.seed import atribuir_perfil_padrao

router = APIRouter(prefix="/auth", tags=["auth"])


def _resposta_login(response: Response, emitida) -> dict:
    cookies.definir_sessao(
        response, emitida.access_token, emitida.refresh_token, emitida.csrf_token
    )
    return {
        "access_token": emitida.access_token,
        "token_type": "bearer",
        "expires_in": config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "csrf_token": emitida.csrf_token,
        "user": emitida.user,
    }


# ────────────────────────── login ──────────────────────────

@router.get("/providers", response_model=ProvidersOut)
def listar_providers():
    """Formas de login disponíveis. O front monta a tela a partir daqui."""
    ativos = providers_ativos()
    return {
        "providers": ativos,
        "firebase_project_id": config.FIREBASE_PROJECT_ID if "firebase" in ativos else None,
    }


@router.post("/login", response_model=LoginOut)
def login(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    emitida = AuthService(db).login("local", {
        "username": form.username, "password": form.password,
    })
    return _resposta_login(response, emitida)


@router.post("/login/firebase", response_model=LoginOut)
def login_firebase(
    dados: LoginFirebase,
    response: Response,
    db: Session = Depends(get_db),
):
    """Troca um ID token do Firebase por uma sessão do Indoc.

    O Firebase só prova quem é a pessoa. Papel, grupos e ACL continuam vindo do
    MySQL, e as claims de autorização nunca saem do servidor.
    """
    emitida = AuthService(db).login("firebase", {"id_token": dados.id_token})
    return _resposta_login(response, emitida)


# ────────────────────────── sessão ──────────────────────────

@router.post("/refresh", response_model=LoginOut)
def renovar(request: Request, response: Response, db: Session = Depends(get_db)):
    """Renova o par de tokens, rotacionando o refresh.

    Não exige access token válido — a razão de existir é justamente o access
    ter expirado. O refresh no cookie HttpOnly é a credencial aqui.
    """
    refresh = request.cookies.get(config.COOKIE_REFRESH)
    if not refresh:
        raise HTTPException(401, "Sessão ausente")
    emitida = AuthService(db).renovar(refresh)
    return _resposta_login(response, emitida)


@router.post("/logout", response_model=schemas.OkOut)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Encerra a sessão atual.

    Sem `get_current_user`: fazer logout tem que funcionar mesmo com o access
    token já expirado, senão a sessão ficaria viva no servidor.
    """
    refresh = request.cookies.get(config.COOKIE_REFRESH)
    AuthService(db).logout(refresh)
    cookies.limpar_sessao(response)
    return {"ok": True}


@router.get("/sessoes", response_model=list[SessaoOut])
def listar_sessoes(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Minhas sessões — de onde a minha conta está conectada."""
    atual = get_session_id(request)
    return [
        {
            "id": s.id, "provider": s.provider, "ip": s.ip, "user_agent": s.user_agent,
            "created_at": s.created_at, "last_used_at": s.last_used_at,
            "expires_at": s.expires_at, "revoked_at": s.revoked_at,
            "atual": s.id == atual, "ativa": s.ativa,
        }
        for s in AuthService(db).sessoes(user.id)
    ]


@router.delete("/sessoes/{sessao_id}", response_model=schemas.OkOut)
def revogar_sessao(
    sessao_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Encerra UMA sessão minha — o notebook esquecido no escritório."""
    if not AuthService(db).revogar_sessao(sessao_id, user.id):
        raise HTTPException(404, "Sessão não encontrada")
    return {"ok": True}


@router.post("/sessoes/revogar-todas", response_model=RevogacaoOut)
def revogar_todas(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Encerra todas as outras sessões, mantendo esta.

    Manter a atual é deliberado: quem acabou de trocar a senha não deveria ser
    deslogado do lugar de onde está fazendo isso.
    """
    total = AuthService(db).revogar_todas(
        user.id, motivo="logout_global", exceto=get_session_id(request)
    )
    return {"revogadas": total}


# ────────────────────────── usuários ──────────────────────────

@router.post("/registrar", response_model=schemas.UsuarioOut, status_code=201)
def registrar_usuario(
    data: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Criação de usuário restrita a Admin/Dev (evita escalação de privilégio)."""
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(400, "Username já existe")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(400, "Email já existe")
    user = models.User(
        username=data.username, email=data.email,
        hashed_password=hash_password(data.password), role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # A ACL é default-deny: sem perfil o usuário nasceria sem poder nada.
    atribuir_perfil_padrao(db, user)

    registrar(
        db, Action.CRIACAO, user=admin,
        entity_type="usuario", entity_id=user.id,
        after=snapshot(user, ("id", "username", "email", "role", "is_active")),
    )
    return user


@router.get("/me", response_model=schemas.UsuarioOut)
def me(user: models.User = Depends(get_current_user)):
    return user
