"""Models de autenticação (FASE 2)."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from indoc.core.database import Base
from indoc.core.time import utcnow


class UserSession(Base):
    """Uma sessão viva de um usuário — o lastro do refresh token.

    O refresh token NUNCA é gravado em claro: guardamos o SHA-256 dele. Um
    vazamento do banco não entrega sessões utilizáveis, do mesmo jeito que não
    entrega senhas.

    Cada refresh ROTACIONA o token: o antigo morre, um novo nasce na mesma
    sessão. Se o token ANTERIOR reaparecer, é sinal de roubo — todas as sessões
    do usuário são revogadas (ver `AuthService.renovar`).

    A detecção guarda uma geração (`previous_token_hash`), que é o que cobre o
    ataque real: quem copiou o token e quem é o dono legítimo disputam a
    próxima rotação, e o perdedor apresenta o token já rotacionado. Um token de
    várias gerações atrás não é rastreável — cai como sessão inválida, sem
    alarme.
    """

    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    refresh_token_hash = Column(String(64), nullable=False, unique=True)
    # Hash do token imediatamente anterior. A rotação sobrescreve
    # `refresh_token_hash`, então sem isto o token antigo ficaria
    # inencontrável e o reuso passaria como um 401 qualquer, sem alarme.
    previous_token_hash = Column(String(64), nullable=True, index=True)
    # Quem autenticou: 'local' (senha) ou 'firebase'. Preparado para 'oidc'.
    provider = Column(String(30), nullable=False, default="local")

    ip = Column(String(45), nullable=True)          # 45 = IPv6 textual
    user_agent = Column(String(400), nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_used_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(100), nullable=True)

    usuario = relationship("User")

    __table_args__ = (
        Index("ix_user_sessions_usuario_revoked", "usuario_id", "revoked_at"),
    )

    @property
    def ativa(self) -> bool:
        return self.revoked_at is None and self.expires_at > utcnow()


class LoginThrottle(Base):
    """Contador de falhas de login, por username e por IP.

    Duas linhas independentes protegem coisas diferentes: a chave `username`
    impede adivinhar a senha de UMA conta; a chave `ip` impede varrer MUITAS
    contas a partir do mesmo lugar.

    O bloqueio é progressivo — dobra a cada novo bloqueio da mesma chave.
    """

    __tablename__ = "login_throttle"
    id = Column(Integer, primary_key=True)
    tipo = Column(String(20), nullable=False)       # 'username' | 'ip'
    chave = Column(String(200), nullable=False)
    falhas = Column(Integer, nullable=False, default=0)
    bloqueios = Column(Integer, nullable=False, default=0)
    primeira_falha = Column(DateTime, nullable=True)
    ultima_falha = Column(DateTime, nullable=True)
    bloqueado_ate = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("tipo", "chave", name="uq_login_throttle_chave"),
    )


class IdentidadeExterna(Base):
    """Vínculo entre um usuário do Indoc e um provider externo.

    Tabela própria em vez de coluna em `usuarios` porque um mesmo usuário pode
    vir a ter mais de uma identidade (Firebase hoje, Entra ID depois) sem nova
    migration estrutural.
    """

    __tablename__ = "identidades_externas"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    provider = Column(String(30), nullable=False)
    subject = Column(String(200), nullable=False)   # uid no provider
    email = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    ultimo_login = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)

    usuario = relationship("User")

    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_identidade_provider_subject"),
    )
