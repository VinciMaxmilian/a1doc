"""AuthService — login, renovação e revogação de sessão (FASE 2)."""
import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from indoc.audit.actions import Action
from indoc.audit.service import registrar
from indoc.auth import throttle, tokens
from indoc.auth.models import UserSession
from indoc.auth.providers import CredencialInvalida, Identidade, get_provider
from indoc.core.request_context import get_origem
from indoc.core.time import utcnow
from indoc.users.models import User

logger = logging.getLogger("indoc.auth")


class SessaoEmitida:
    def __init__(self, user: User, sessao: UserSession, access: str, refresh: str, csrf: str):
        self.user = user
        self.sessao = sessao
        self.access_token = access
        self.refresh_token = refresh
        self.csrf_token = csrf


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    # ── login ────────────────────────────────────────────────────────────

    def login(self, provider_nome: str, credenciais: dict) -> SessaoEmitida:
        origem = get_origem()
        # Só o provider local sofre throttle por username: no Firebase a senha
        # não é verificada aqui, então não há o que adivinhar contra nós.
        username = (credenciais.get("username") or "").strip() if provider_nome == "local" else ""

        try:
            throttle.verificar(self.db, username, origem.ip)
        except throttle.Bloqueado as bloqueio:
            registrar(
                self.db, Action.LOGIN_BLOQUEADO,
                metadata={"username": username, "segundos": bloqueio.segundos},
            )
            raise HTTPException(429, str(bloqueio),
                                headers={"Retry-After": str(bloqueio.segundos)}) from None

        try:
            identidade = get_provider(provider_nome).autenticar(self.db, credenciais)
        except CredencialInvalida as erro:
            throttle.registrar_falha(self.db, username, origem.ip)
            registrar(
                self.db, Action.LOGIN_INVALIDO,
                metadata={"username": username, "provider": provider_nome, "motivo": str(erro)},
            )
            raise HTTPException(401, str(erro)) from None

        self._exigir_conta_utilizavel(identidade.user, username, origem.ip)

        throttle.registrar_sucesso(self.db, username, origem.ip)
        emitida = self._abrir_sessao(identidade)

        identidade.user.ultimo_login = utcnow()
        self.db.commit()

        registrar(
            self.db, Action.LOGIN, user=identidade.user,
            session_id=emitida.sessao.id,
            metadata={"provider": identidade.provider},
        )
        return emitida

    def _exigir_conta_utilizavel(self, user: User, username: str, ip: Optional[str]) -> None:
        """Conta inativa ou bloqueada não abre sessão.

        Conta a falha no throttle também: senão a conta desativada viraria um
        alvo de força bruta sem custo.
        """
        if user.bloqueado_em is not None:
            throttle.registrar_falha(self.db, username, ip)
            registrar(self.db, Action.LOGIN_INVALIDO, user=user,
                      metadata={"motivo": "conta bloqueada", "username": user.username})
            raise HTTPException(403, user.motivo_bloqueio or "Usuário bloqueado")
        if not user.is_active:
            throttle.registrar_falha(self.db, username, ip)
            registrar(self.db, Action.LOGIN_INVALIDO, user=user,
                      metadata={"motivo": "conta inativa", "username": user.username})
            raise HTTPException(403, "Usuário inativo")

    def _abrir_sessao(self, identidade: Identidade) -> SessaoEmitida:
        origem = get_origem()
        refresh = tokens.novo_refresh_token()
        sessao = UserSession(
            usuario_id=identidade.user.id,
            refresh_token_hash=tokens.hash_refresh(refresh),
            provider=identidade.provider,
            ip=origem.ip,
            user_agent=origem.user_agent,
            expires_at=tokens.expiracao_refresh(),
        )
        self.db.add(sessao)
        self.db.commit()
        self.db.refresh(sessao)

        return SessaoEmitida(
            user=identidade.user,
            sessao=sessao,
            access=tokens.criar_access_token(identidade.user.id, sessao.id),
            refresh=refresh,
            csrf=tokens.novo_csrf_token(),
        )

    # ── renovação ────────────────────────────────────────────────────────

    def renovar(self, refresh_token: str) -> SessaoEmitida:
        """Troca o refresh por um par novo, rotacionando o token.

        Detecção de reuso: se chegar um refresh que já foi rotacionado (ou
        seja, pertence a uma sessão revogada), é sinal de que alguém copiou o
        token. Revogar todas as sessões do usuário é a resposta correta — não
        dá para saber qual das duas partes é a legítima.
        """
        if not refresh_token:
            raise HTTPException(401, "Sessão ausente")

        apresentado = tokens.hash_refresh(refresh_token)
        sessao = self.db.query(UserSession).filter(
            UserSession.refresh_token_hash == apresentado
        ).first()

        if sessao is None:
            # Não é o token vigente de ninguém. Se for o token ANTERIOR de
            # alguma sessão, houve reuso: o legítimo já rotacionou e este aqui
            # é uma cópia. Não dá para saber qual das duas partes é a
            # verdadeira, então derruba todas as sessões do usuário.
            suspeita = self.db.query(UserSession).filter(
                UserSession.previous_token_hash == apresentado
            ).first()
            if suspeita is not None:
                self._alarmar_reuso(suspeita)
            raise HTTPException(401, "Sessão inválida")

        if sessao.revoked_at is not None:
            self._alarmar_reuso(sessao)
            raise HTTPException(401, "Sessão inválida")

        if sessao.expires_at <= utcnow():
            raise HTTPException(401, "Sessão expirada")

        user = self.db.query(User).filter(User.id == sessao.usuario_id).first()
        if not user or not user.is_active or user.bloqueado_em is not None:
            self._revogar(sessao, "conta_indisponivel")
            raise HTTPException(401, "Sessão inválida")

        novo = tokens.novo_refresh_token()
        origem = get_origem()
        sessao.previous_token_hash = sessao.refresh_token_hash
        sessao.refresh_token_hash = tokens.hash_refresh(novo)
        sessao.last_used_at = utcnow()
        # A sessão acompanha de onde está sendo usada agora.
        sessao.ip = origem.ip or sessao.ip
        sessao.user_agent = origem.user_agent or sessao.user_agent
        self.db.commit()

        return SessaoEmitida(
            user=user,
            sessao=sessao,
            access=tokens.criar_access_token(user.id, sessao.id),
            refresh=novo,
            csrf=tokens.novo_csrf_token(),
        )

    def _alarmar_reuso(self, sessao: UserSession) -> None:
        logger.warning(
            "Refresh token reusado na sessão %s (usuário %s) — revogando tudo",
            sessao.id, sessao.usuario_id,
        )
        self.revogar_todas(sessao.usuario_id, motivo="reuso_de_token")
        registrar(self.db, Action.SESSAO_REUSO_DETECTADO,
                  user_id=sessao.usuario_id, session_id=sessao.id)

    # ── revogação ────────────────────────────────────────────────────────

    def _revogar(self, sessao: UserSession, motivo: str) -> None:
        if sessao.revoked_at is None:
            sessao.revoked_at = utcnow()
            sessao.revoked_reason = motivo
            self.db.commit()

    def logout(self, refresh_token: str, user: Optional[User] = None) -> None:
        if not refresh_token:
            return
        sessao = self.db.query(UserSession).filter(
            UserSession.refresh_token_hash == tokens.hash_refresh(refresh_token)
        ).first()
        if sessao:
            self._revogar(sessao, "logout")
            registrar(self.db, Action.LOGOUT, user=user,
                      user_id=sessao.usuario_id, session_id=sessao.id)

    def revogar_sessao(self, sessao_id: int, usuario_id: int, motivo: str = "revogada") -> bool:
        sessao = self.db.query(UserSession).filter(
            UserSession.id == sessao_id, UserSession.usuario_id == usuario_id
        ).first()
        if not sessao:
            return False
        self._revogar(sessao, motivo)
        registrar(self.db, Action.SESSAO_REVOGADA, user_id=usuario_id, session_id=sessao_id)
        return True

    def revogar_todas(self, usuario_id: int, motivo: str = "logout_global",
                      exceto: Optional[int] = None) -> int:
        q = self.db.query(UserSession).filter(
            UserSession.usuario_id == usuario_id, UserSession.revoked_at.is_(None)
        )
        if exceto is not None:
            q = q.filter(UserSession.id != exceto)
        agora = utcnow()
        total = 0
        for sessao in q.all():
            sessao.revoked_at = agora
            sessao.revoked_reason = motivo
            total += 1
        self.db.commit()
        if total:
            registrar(self.db, Action.SESSAO_REVOGADA, user_id=usuario_id,
                      metadata={"total": total, "motivo": motivo})
        return total

    def sessoes(self, usuario_id: int) -> list[UserSession]:
        return (
            self.db.query(UserSession)
            .filter(UserSession.usuario_id == usuario_id)
            .order_by(UserSession.last_used_at.desc())
            .all()
        )


def limpar_sessoes_expiradas(db: Session) -> int:
    """Remove sessões vencidas há mais de 30 dias.

    Sessão revogada ou expirada ainda é evidência por um tempo (a auditoria
    referencia `session_id`), mas não para sempre.
    """
    from datetime import timedelta

    corte = utcnow() - timedelta(days=30)
    total = db.query(UserSession).filter(UserSession.expires_at < corte).delete(
        synchronize_session=False
    )
    db.commit()
    return total


__all__ = ["AuthService", "SessaoEmitida", "limpar_sessoes_expiradas"]
