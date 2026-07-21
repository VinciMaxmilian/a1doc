import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
import models
from auth import hash_password
from database import SessionLocal, engine
from routers import auth, documentos, hierarquia, usuarios, workflow

config.setup_logging()
logger = logging.getLogger("indoc")

config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def seed_admin() -> None:
    """Cria o usuário admin inicial a partir de variáveis de ambiente."""
    db = SessionLocal()
    try:
        if db.query(models.User).first():
            return
        if not config.ADMIN_PASSWORD:
            logger.warning(
                "Nenhum usuário existe e ADMIN_PASSWORD não definido. "
                "Defina ADMIN_PASSWORD no .env para criar o admin inicial."
            )
            return
        db.add(models.User(
            username=config.ADMIN_USERNAME,
            email=config.ADMIN_EMAIL,
            hashed_password=hash_password(config.ADMIN_PASSWORD),
            role="dev",
        ))
        db.commit()
        logger.info("Usuário admin inicial criado: %s", config.ADMIN_USERNAME)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if config.AUTO_CREATE_TABLES:
        # Conveniência para dev/testes. Em produção use Alembic
        # (`alembic upgrade head`) e defina AUTO_CREATE_TABLES=false.
        models.Base.metadata.create_all(bind=engine)
    seed_admin()
    if config.secret_key_is_insecure():
        logger.warning("SECRET_KEY usando valor padrão inseguro. Defina SECRET_KEY no .env.")
    yield


app = FastAPI(title="Indoc API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Atenção: os arquivos NÃO são servidos como estáticos públicos.
# O download passa por GET /documentos/arquivos/{id}/download, que exige token.

app.include_router(auth.router)
app.include_router(hierarquia.router)
app.include_router(documentos.router)
app.include_router(workflow.router)
app.include_router(usuarios.router)


@app.get("/")
def root():
    return {"status": "Indoc online"}


@app.get("/health")
def health():
    return {"status": "ok"}
