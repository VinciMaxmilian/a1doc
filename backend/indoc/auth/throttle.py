"""Bloqueio progressivo de login (FASE 2).

Duas chaves independentes, porque protegem coisas diferentes:

- `username` — impede adivinhar a senha de UMA conta;
- `ip` — impede varrer MUITAS contas a partir do mesmo lugar.

Basta uma delas estar bloqueada para recusar a tentativa.

O bloqueio dobra a cada reincidência (60s, 120s, 240s…) até o teto. A contagem
de falhas zera sozinha depois de `LOGIN_JANELA_FALHAS_MINUTOS` sem erro, para
que um engano ocasional não se acumule por dias.

Estado no banco, não em memória: precisa valer para todos os workers e
sobreviver a um restart — senão reiniciar o processo limpa o bloqueio.
"""
from datetime import timedelta
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import config
from indoc.auth.models import LoginThrottle
from indoc.core.time import utcnow


class Bloqueado(Exception):
    def __init__(self, segundos: int):
        self.segundos = segundos
        super().__init__(f"Muitas tentativas. Tente novamente em {segundos}s.")


def _linha(db: Session, tipo: str, chave: str, criar: bool = False) -> Optional[LoginThrottle]:
    chave = (chave or "")[:200]
    if not chave:
        return None
    linha = db.query(LoginThrottle).filter(
        LoginThrottle.tipo == tipo, LoginThrottle.chave == chave
    ).first()
    if linha or not criar:
        return linha

    linha = LoginThrottle(tipo=tipo, chave=chave, falhas=0, bloqueios=0)
    db.add(linha)
    try:
        db.commit()
    except IntegrityError:
        # Corrida com outro worker: a linha dele serve.
        db.rollback()
        linha = db.query(LoginThrottle).filter(
            LoginThrottle.tipo == tipo, LoginThrottle.chave == chave
        ).first()
    return linha


def verificar(db: Session, username: str, ip: Optional[str]) -> None:
    """Levanta `Bloqueado` se username ou IP estiverem de castigo."""
    agora = utcnow()
    for tipo, chave in (("username", username), ("ip", ip or "")):
        linha = _linha(db, tipo, chave)
        if linha and linha.bloqueado_ate and linha.bloqueado_ate > agora:
            raise Bloqueado(int((linha.bloqueado_ate - agora).total_seconds()) + 1)


def registrar_falha(db: Session, username: str, ip: Optional[str]) -> None:
    agora = utcnow()
    janela = timedelta(minutes=config.LOGIN_JANELA_FALHAS_MINUTOS)

    for tipo, chave in (("username", username), ("ip", ip or "")):
        linha = _linha(db, tipo, chave, criar=True)
        if linha is None:
            continue

        # Janela expirada sem novas falhas: recomeça a contagem (mas mantém
        # `bloqueios`, para que o reincidente continue pegando castigo maior).
        if linha.ultima_falha and agora - linha.ultima_falha > janela:
            linha.falhas = 0
            linha.primeira_falha = None

        linha.falhas += 1
        linha.ultima_falha = agora
        if linha.primeira_falha is None:
            linha.primeira_falha = agora

        if linha.falhas >= config.LOGIN_MAX_FALHAS:
            linha.bloqueios += 1
            segundos = min(
                config.LOGIN_BLOQUEIO_BASE_SEGUNDOS * (2 ** (linha.bloqueios - 1)),
                config.LOGIN_BLOQUEIO_MAX_SEGUNDOS,
            )
            linha.bloqueado_ate = agora + timedelta(seconds=segundos)
            linha.falhas = 0

    db.commit()


def registrar_sucesso(db: Session, username: str, ip: Optional[str]) -> None:
    """Zera a contagem. `bloqueios` também: quem lembrou a senha não é atacante."""
    for tipo, chave in (("username", username), ("ip", ip or "")):
        linha = _linha(db, tipo, chave)
        if linha:
            linha.falhas = 0
            linha.bloqueios = 0
            linha.bloqueado_ate = None
            linha.primeira_falha = None
    db.commit()
