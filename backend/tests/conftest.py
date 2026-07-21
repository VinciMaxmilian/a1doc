"""Fixtures da suíte.

O ambiente é preparado ANTES de importar a aplicação: `config` lê as variáveis
no import, então os testes precisam apontar DATABASE_URL/UPLOAD_DIR para um
diretório temporário antes de qualquer `import main`.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = Path(tempfile.mkdtemp(prefix="indoc-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["SECRET_KEY"] = "chave-de-teste-nao-usar-em-producao"
os.environ["ADMIN_PASSWORD"] = ""          # sem seed automático
os.environ["AUTO_CREATE_TABLES"] = "false"  # as fixtures controlam o schema
os.environ["MAX_UPLOAD_MB"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

import celery_app as celery_module  # noqa: E402
import models  # noqa: E402
from auth import hash_password  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402

# Executa as tasks inline, sem broker. `eager_propagates=False` mantém o
# comportamento de produção: a falha da task vira status "erro" no job, e não
# uma exceção no request que enfileirou.
celery_module.celery_app.conf.task_always_eager = True
celery_module.celery_app.conf.task_eager_propagates = False


@pytest.fixture(autouse=True)
def _schema_limpo():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    yield
    models.Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def criar_usuario(db, username="user1", role="user", senha="senha-forte-123"):
    u = models.User(
        username=username,
        email=f"{username}@indoc.local",
        hashed_password=hash_password(senha),
        role=role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def token_de(client, username, senha="senha-forte-123"):
    r = client.post("/auth/login", data={"username": username, "password": senha})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(db):
    return criar_usuario(db, "admin1", role="admin")


@pytest.fixture
def comum(db):
    return criar_usuario(db, "comum1", role="user")


@pytest.fixture
def h_admin(client, admin):
    return auth(token_de(client, admin.username))


@pytest.fixture
def h_comum(client, comum):
    return auth(token_de(client, comum.username))


@pytest.fixture
def hierarquia(client, h_admin):
    """Ambiente → Área → Projeto + Tipo de documento. Devolve os ids."""
    amb = client.post("/hierarquia/ambientes", json={"nome": "Eng"}, headers=h_admin).json()
    area = client.post("/hierarquia/areas",
                       json={"nome": "Civil", "ambiente_id": amb["id"]},
                       headers=h_admin).json()
    proj = client.post("/hierarquia/projetos",
                       json={"nome": "Ponte", "area_id": area["id"]},
                       headers=h_admin).json()
    tipo = client.post("/hierarquia/tipos-documento",
                       json={"nome": "Memorial"}, headers=h_admin).json()
    return {"ambiente_id": amb["id"], "area_id": area["id"],
            "projeto_id": proj["id"], "tipo_documento_id": tipo["id"]}


@pytest.fixture
def fluxo_inicial(client, h_admin):
    """Fluxo 0 com 'Elaboração' → 'Aprovação'. Devolve os ids das atividades."""
    fluxo = client.post("/workflow/fluxos",
                        json={"nome": "Padrão"}, headers=h_admin).json()
    assert fluxo["numero"] == 0
    elab = client.post("/workflow/atividades",
                       json={"nome": "Elaboração", "fluxo_id": fluxo["id"], "ordem": 1},
                       headers=h_admin).json()
    aprov = client.post("/workflow/atividades",
                        json={"nome": "Aprovação", "fluxo_id": fluxo["id"], "ordem": 2},
                        headers=h_admin).json()
    client.post("/workflow/transicoes", headers=h_admin, json={
        "atividade_origem_id": elab["id"], "acao": "aprovado",
        "atividade_destino_id": aprov["id"], "gera_nova_revisao": False,
    })
    client.post("/workflow/transicoes", headers=h_admin, json={
        "atividade_origem_id": aprov["id"], "acao": "reprovado",
        "atividade_destino_id": elab["id"], "gera_nova_revisao": True,
    })
    return {"fluxo_id": fluxo["id"], "elaboracao_id": elab["id"], "aprovacao_id": aprov["id"]}


def enviar_documento(client, headers, hierarquia, nome="Memorial Descritivo",
                     arquivos=None, observacao=None):
    """Faz upload e espera o processamento (Celery em modo eager)."""
    files = arquivos or [("arquivos", ("plano.pdf", b"conteudo-pdf", "application/pdf"))]
    dados = {**hierarquia, "nome": nome}
    if observacao:
        dados["observacao"] = observacao
    r = client.post("/documentos/upload", headers=headers, data=dados, files=files)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    job = client.get(f"/documentos/jobs/{job_id}", headers=headers).json()
    assert job["status"] == "concluido", job
    return client.get(f"/documentos/{job['documento_id']}", headers=headers).json()


@pytest.fixture
def documento(client, h_comum, hierarquia, fluxo_inicial):
    return enviar_documento(client, h_comum, hierarquia)
