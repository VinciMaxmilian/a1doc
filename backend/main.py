from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from database import engine, SessionLocal
from auth import hash_password
import models
from routers import auth, hierarquia, documentos, workflow, usuarios
from pathlib import Path
import os

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="A1Doc API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
                    print(f"[migrate] {table.name}.{col.name} ({col_type}) adicionado")
                except Exception as exc:
                    print(f"[migrate] Erro em {table.name}.{col.name}: {exc}")


@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
    migrate_db()
    db = SessionLocal()
    try:
        if not db.query(models.User).first():
            db.add(models.User(
                username="admin", email="admin@a1doc.local",
                hashed_password=hash_password("admin123"), role="dev"
            ))
            db.commit()
            print("Usuário padrão criado: admin / admin123")
    finally:
        db.close()


@app.get("/")
def root():
    return {"status": "A1Doc online"}
