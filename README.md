# Indoc

Sistema de Gestão Eletrônica de Documentos (GED) com workflow configurável.

Hierarquia **Ambiente → Área → Projeto → Documento**, formulários dinâmicos por tipo de documento, versionamento de revisões e workflow por transições (`aprovado`/`reprovado`) configuráveis.

## Stack

- **Backend:** FastAPI + SQLAlchemy 2.0 + MySQL
- **Fila assíncrona:** Celery + Redis (processamento de uploads)
- **Auth:** JWT + bcrypt
- **Frontend:** React 18 + Vite

## Requisitos

- Python 3.11+
- Node 18+
- MySQL 8
- Redis 6+

## Setup (local)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
copy .env.example .env           # e edite os valores
```

Edite o `.env`:

- `DATABASE_URL` — conexão MySQL
- `SECRET_KEY` — gere com `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `CORS_ORIGINS` — origem do frontend (ex.: `http://localhost:5173`)
- `ADMIN_PASSWORD` — senha do admin inicial (criado só se não houver nenhum usuário)

Suba os serviços (Windows — via `.bat` na raiz):

```
start-backend.bat          # API em http://localhost:8000
start-celery-worker.bat    # worker de uploads
start-celery-beat.bat      # scheduler (opcional)
```

Ou manualmente:

```bash
uvicorn main:app --reload --port 8000
celery -A celery_app worker --loglevel=info --pool=solo
```

### Frontend

```bash
cd frontend
npm install
npm run dev                # http://localhost:5173
```

O Vite faz proxy de `/api` e `/uploads` para o backend (`vite.config.js`).

## Setup (Docker)

```bash
docker compose up --build
```

Sobe MySQL, Redis, API, worker e frontend. Configure as variáveis no `docker-compose.yml` ou num `.env` na raiz.

## Notas de segurança

- Nunca commite o `.env` real (já ignorado).
- Troque `SECRET_KEY` e `ADMIN_PASSWORD` em produção.
- Restrinja `CORS_ORIGINS` às origens reais.
- Uploads: extensões permitidas em `backend/utils.py` (`ALLOWED_EXTENSIONS`).

## Estrutura

```
backend/
  main.py            # app, lifespan, auto-migração, seed admin
  models.py          # ORM
  schemas.py         # entrada (Pydantic) + validações
  auth.py            # JWT + bcrypt + guards
  routers/           # auth, hierarquia, documentos, workflow, usuarios
  tasks.py           # Celery: processar_upload
  utils.py           # paths, sanitização de arquivos
frontend/
  src/pages/         # telas
  src/components/    # UI compartilhada
```

## Melhorias futuras

Ver [ANALISE.md](ANALISE.md).
