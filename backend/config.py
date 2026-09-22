"""Configuração central da aplicação.

Único ponto que lê variáveis de ambiente. Importar daqui em vez de chamar
os.getenv() espalhado — evita defaults divergentes entre API e worker
(ex.: UPLOAD_DIR apontando para árvores diferentes).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ── Banco ──
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/indoc")

# ── Segurança ──
INSECURE_SECRET_KEYS = {"", "change-me", "troque-em-producao", "troque-em-producao-chave-muito-secreta"}
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = "HS256"

# O access token ficou curto porque agora existe refresh token (FASE 2). Um
# token de 8h era a única credencial e vivia em localStorage; hoje ele dura
# minutos e a sessão longa é o refresh, em cookie HttpOnly.
ACCESS_TOKEN_EXPIRE_MINUTES = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 15)
REFRESH_TOKEN_EXPIRE_DAYS = _int("REFRESH_TOKEN_EXPIRE_DAYS", 14)

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

# ── Cookies de sessão ──
# `Secure` liga por padrão: cookie de sessão não deve trafegar em claro.
# Em dev sobre http://localhost isso impede o navegador de guardar o cookie —
# defina COOKIE_SECURE=false no .env local.
COOKIE_SECURE = _bool("COOKIE_SECURE", True)
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN") or None

# Confiar em X-Forwarded-For para determinar o IP do cliente. Só ligue se a API
# estiver atrás de um proxy que reescreve esse header — caso contrário qualquer
# cliente forja o IP que vai para a auditoria e para o bloqueio de login.
TRUST_PROXY_HEADERS = _bool("TRUST_PROXY_HEADERS", False)

COOKIE_ACCESS = "indoc_access"
COOKIE_REFRESH = "indoc_refresh"
COOKIE_CSRF = "indoc_csrf"
HEADER_CSRF = "X-CSRF-Token"

# ── Proteção contra força bruta no login ──
# Após LOGIN_MAX_FALHAS erros, bloqueia por LOGIN_BLOQUEIO_BASE_SEGUNDOS e
# dobra a cada novo bloqueio, até o teto.
LOGIN_MAX_FALHAS = _int("LOGIN_MAX_FALHAS", 5)
LOGIN_BLOQUEIO_BASE_SEGUNDOS = _int("LOGIN_BLOQUEIO_BASE_SEGUNDOS", 60)
LOGIN_BLOQUEIO_MAX_SEGUNDOS = _int("LOGIN_BLOQUEIO_MAX_SEGUNDOS", 3600)
LOGIN_JANELA_FALHAS_MINUTOS = _int("LOGIN_JANELA_FALHAS_MINUTOS", 15)

# ── Firebase (provider de identidade — FASE 2) ──
# Só prova QUEM é o usuário. Papel, grupos e ACL continuam no MySQL, e a
# criação/bloqueio de usuários é do Indoc (não exige service account).
FIREBASE_ENABLED = _bool("FIREBASE_ENABLED", False)
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
FIREBASE_JWKS_URL = os.getenv(
    "FIREBASE_JWKS_URL",
    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com",
)
# Usuário do Firebase sem correspondente no Indoc: criar na hora (com o perfil
# padrão) ou recusar o login. Recusar é o default — numa instalação corporativa
# quem entra é quem foi cadastrado.
FIREBASE_AUTO_PROVISIONAR = _bool("FIREBASE_AUTO_PROVISIONAR", False)

# ── Armazenamento ──
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads")).resolve()
MAX_UPLOAD_BYTES = _int("MAX_UPLOAD_MB", 100) * 1024 * 1024

# ── Fila ──
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── Admin inicial ──
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@indoc.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# ── Comportamento ──
# Executa create_all no startup. O default é `false`: o schema pertence ao
# Alembic (`alembic upgrade head`). Ligar isso faz o banco divergir das
# migrations silenciosamente. Os testes ligam explicitamente no conftest.
AUTO_CREATE_TABLES = _bool("AUTO_CREATE_TABLES", False)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# "text" (legível) ou "json" (uma linha por evento, para agregadores).
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").strip().lower()

# Paginação
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def secret_key_is_insecure() -> bool:
    return SECRET_KEY.strip() in INSECURE_SECRET_KEYS


def setup_logging() -> None:
    """Configura o logging raiz. Idempotente.

    Import tardio: `indoc.core.logging` não depende de `config`, mas manter a
    importação dentro da função deixa `config` livre de qualquer acoplamento
    com o pacote da aplicação.
    """
    from indoc.core.logging import setup_logging as _setup

    _setup(level=LOG_LEVEL, formato=LOG_FORMAT)
