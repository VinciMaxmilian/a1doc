from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from database import engine, SessionLocal
from auth import hash_password
import models
from routers import auth, hierarquia, documentos, workflow, usuarios
from pathlib import Path
import logging
import os

logger = logging.getLogger("indoc")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Origens permitidas para CORS (separadas por vírgula no .env)
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]


def migrate_db():
    """Detecta colunas novas nos models e aplica ALTER TABLE automaticamente."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in models.Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # tabela nova: create_all cuida

            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}

            for col in table.columns:
                if col.name in existing_cols:
                    continue
                try:
                    col_type = col.type.compile(dialect=engine.dialect)
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    conn.execute(text(
                        f"ALTER TABLE `{table.name}` ADD COLUMN `{col.name}` {col_type} {nullable}"
                    ))
                    logger.info("[migrate] %s.%s (%s) adicionado", table.name, col.name, col_type)
                except Exception as exc:
                    logger.error("[migrate] Erro em %s.%s: %s", table.name, col.name, exc)


def seed_admin():
    """Cria o usuário admin inicial a partir de variáveis de ambiente."""
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD")
    email = os.getenv("ADMIN_EMAIL", "admin@indoc.local")

    db = SessionLocal()
    try:
        if db.query(models.User).first():
            return
        if not password:
            logger.warning(
                "Nenhum usuário existe e ADMIN_PASSWORD não definido. "
                "Defina ADMIN_PASSWORD no .env para criar o admin inicial."
            )
            return
        db.add(models.User(
            username=username, email=email,
            hashed_password=hash_password(password), role="dev",
        ))
        db.commit()
        logger.info("Usuário admin inicial criado: %s", username)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    migrate_db()
    seed_admin()
    if os.getenv("SECRET_KEY", "change-me") in ("change-me", ""):
        logger.warning("SECRET_KEY usando valor padrão inseguro. Defina SECRET_KEY no .env.")
    yield


app = FastAPI(title="Indoc API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(auth.router)
app.include_router(hierarquia.router)
app.include_router(documentos.router)
app.include_router(workflow.router)
app.include_router(usuarios.router)


@app.get("/")
def root():
    return {"status": "Indoc online"}
