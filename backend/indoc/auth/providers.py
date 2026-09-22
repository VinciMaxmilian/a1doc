"""Providers de identidade.

Um provider responde uma única pergunta: **quem é este usuário?** Ele não
decide o que a pessoa pode — isso é da ACL (FASE 1) e continua no MySQL.

    AuthProvider (protocolo)
    ├── LocalPasswordProvider   bcrypt, o que já existia
    ├── FirebaseProvider        verifica ID token do Firebase
    └── (futuro) OIDCProvider   LDAP / AD / Entra ID / SSO

Essa separação é o que a FASE 2 pede ao exigir arquitetura preparada para SSO
sem obrigar a ativar integração externa agora.
"""
import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from sqlalchemy.orm import Session

import config
from indoc.auth.models import IdentidadeExterna
from indoc.core.time import utcnow
from indoc.users.models import User

logger = logging.getLogger("indoc.auth")


class CredencialInvalida(Exception):
    """Falha de autenticação. A mensagem vai para o cliente — nunca revela se
    o usuário existe, para não virar um oráculo de enumeração de contas."""


@dataclass
class Identidade:
    """Resultado de uma autenticação bem-sucedida."""

    user: User
    provider: str


class AuthProvider(Protocol):
    nome: str

    def autenticar(self, db: Session, credenciais: dict) -> Identidade:
        ...


# ── local ───────────────────────────────────────────────────────────────

class LocalPasswordProvider:
    """Usuário e senha com bcrypt. O caminho que já existia, agora como provider."""

    nome = "local"

    def autenticar(self, db: Session, credenciais: dict) -> Identidade:
        from indoc.auth.password import verify_password

        username = (credenciais.get("username") or "").strip()
        senha = credenciais.get("password") or ""

        user = db.query(User).filter(User.username == username).first()

        # Verifica a senha mesmo sem usuário, contra um hash descartável, para
        # que o tempo de resposta não diga se a conta existe.
        if not user:
            verify_password(senha, "$2b$12$" + "x" * 53)
            raise CredencialInvalida("Credenciais inválidas")

        if not verify_password(senha, user.hashed_password):
            raise CredencialInvalida("Credenciais inválidas")

        return Identidade(user=user, provider=self.nome)


# ── Firebase ────────────────────────────────────────────────────────────

class FirebaseProvider:
    """Verifica um ID token do Firebase Authentication.

    Só precisa das chaves PÚBLICAS do Google — não exige service account. O
    Admin SDK seria necessário apenas para operações administrativas (criar
    usuário pelo servidor, custom claims, revogar refresh do Firebase), e essas
    ficam do lado do Indoc: quem cadastra e bloqueia usuário aqui é o Indoc.

    O vínculo é por `IdentidadeExterna(provider='firebase', subject=uid)`, com
    o e-mail como ponte no primeiro login de um usuário já cadastrado.
    """

    nome = "firebase"

    def __init__(self):
        self._jwk_client = None

    def _cliente_chaves(self):
        # Import e rede só quando o provider é de fato usado: com Firebase
        # desligado (o default), nada disto é tocado — inclusive nos testes.
        if self._jwk_client is None:
            from jwt import PyJWKClient

            self._jwk_client = PyJWKClient(config.FIREBASE_JWKS_URL, cache_keys=True)
        return self._jwk_client

    def verificar_token(self, id_token: str) -> dict:
        import jwt

        if not config.FIREBASE_PROJECT_ID:
            raise CredencialInvalida("Firebase não configurado")

        try:
            chave = self._cliente_chaves().get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                chave.key,
                algorithms=["RS256"],
                audience=config.FIREBASE_PROJECT_ID,
                issuer=f"https://securetoken.google.com/{config.FIREBASE_PROJECT_ID}",
            )
        except Exception as exc:
            logger.warning("ID token do Firebase recusado: %s", exc)
            raise CredencialInvalida("Token de identidade inválido") from None

        # `sub` é o uid estável. O Firebase também manda `user_id`, igual.
        if not claims.get("sub"):
            raise CredencialInvalida("Token de identidade sem 'sub'")
        return claims

    def autenticar(self, db: Session, credenciais: dict) -> Identidade:
        if not config.FIREBASE_ENABLED:
            raise CredencialInvalida("Autenticação Firebase desabilitada")

        claims = self.verificar_token(credenciais.get("id_token") or "")
        uid = claims["sub"]
        email = (claims.get("email") or "").strip().lower() or None

        user = self._resolver_usuario(db, uid, email, claims)
        return Identidade(user=user, provider=self.nome)

    def _resolver_usuario(self, db: Session, uid: str, email: Optional[str], claims: dict) -> User:
        vinculo = db.query(IdentidadeExterna).filter(
            IdentidadeExterna.provider == self.nome,
            IdentidadeExterna.subject == uid,
        ).first()

        if vinculo:
            if not vinculo.ativo:
                raise CredencialInvalida("Identidade externa desativada")
            vinculo.ultimo_login = utcnow()
            db.commit()
            return vinculo.usuario

        # Primeiro login deste uid: liga ao usuário já cadastrado com o mesmo
        # e-mail. Só aceitamos e-mail verificado — senão bastaria criar uma
        # conta Firebase com o e-mail de alguém para assumir a identidade dela.
        if email and claims.get("email_verified"):
            user = db.query(User).filter(User.email == email).first()
            if user:
                db.add(IdentidadeExterna(
                    usuario_id=user.id, provider=self.nome, subject=uid, email=email,
                    ultimo_login=utcnow(),
                ))
                db.commit()
                logger.info("Identidade Firebase vinculada ao usuário %s", user.username)
                return user

        if config.FIREBASE_AUTO_PROVISIONAR and email and claims.get("email_verified"):
            return self._provisionar(db, uid, email, claims)

        raise CredencialInvalida("Usuário não cadastrado no Indoc")

    def _provisionar(self, db: Session, uid: str, email: str, claims: dict) -> User:
        import secrets

        from indoc.auth.password import hash_password
        from indoc.permissions.seed import atribuir_perfil_padrao

        base = email.split("@")[0][:80] or "usuario"
        username = base
        sufixo = 1
        while db.query(User).filter(User.username == username).first():
            sufixo += 1
            username = f"{base}{sufixo}"

        user = User(
            username=username,
            email=email,
            # Senha local impossível de usar: quem entra por Firebase não tem
            # senha no Indoc. Um hash aleatório evita deixar o campo vazio.
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            role="user",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        db.add(IdentidadeExterna(usuario_id=user.id, provider=self.nome,
                                 subject=uid, email=email, ultimo_login=utcnow()))
        db.commit()
        atribuir_perfil_padrao(db, user)
        logger.info("Usuário provisionado via Firebase: %s", username)
        return user


# ── registro ────────────────────────────────────────────────────────────

_PROVIDERS: dict[str, AuthProvider] = {
    LocalPasswordProvider.nome: LocalPasswordProvider(),
    FirebaseProvider.nome: FirebaseProvider(),
}


def get_provider(nome: str) -> AuthProvider:
    provider = _PROVIDERS.get(nome)
    if provider is None:
        raise CredencialInvalida(f"Provider de autenticação desconhecido: '{nome}'")
    return provider


def providers_ativos() -> list[str]:
    ativos = [LocalPasswordProvider.nome]
    if config.FIREBASE_ENABLED and config.FIREBASE_PROJECT_ID:
        ativos.append(FirebaseProvider.nome)
    return ativos
