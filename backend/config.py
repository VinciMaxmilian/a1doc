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
ACCESS_TOKEN_EXPIRE_MINUTES = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 480)

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

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
# Executa create_all/migrate no startup. Deixe desligado em produção e use Alembic.
AUTO_CREATE_TABLES = _bool("AUTO_CREATE_TABLES", True)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Paginação
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def secret_key_is_insecure() -> bool:
    return SECRET_KEY.strip() in INSECURE_SECRET_KEYS


def setup_logging() -> None:
    """Configura o logging raiz. Idempotente."""
    import logging

    if logging.getLogger().handlers:
        logging.getLogger().setLevel(LOG_LEVEL)
        return
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
