# Indoc

Sistema de Gestão Eletrônica de Documentos (GED) com workflow configurável.

Hierarquia **Ambiente → Área → Projeto → Documento**, formulários dinâmicos por tipo de documento, versionamento de revisões e workflow por transições (`aprovado`/`reprovado`) configuráveis.

## Stack

- **Backend:** FastAPI + SQLAlchemy 2.0 + MySQL
- **Migrations:** Alembic
- **Fila assíncrona:** Celery + Redis (processamento de uploads)
- **Auth:** JWT (PyJWT) + bcrypt
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
alembic upgrade head             # cria/atualiza o schema
```

Variáveis obrigatórias no `.env`:

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | Conexão MySQL |
| `SECRET_KEY` | Gere com `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | Origem do frontend (ex.: `http://localhost:5173`). Nunca use `*` |
| `UPLOAD_DIR` | Onde os arquivos ficam. **Precisa ser o mesmo valor na API e no worker** |
| `ADMIN_PASSWORD` | Senha do admin inicial (criado só se não houver nenhum usuário) |
| `AUTO_CREATE_TABLES` | `false` em produção — o schema é do Alembic |

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

O Vite faz proxy de `/api` para o backend (`vite.config.js`).

## Setup (Docker)

Crie um `.env` na raiz com as variáveis obrigatórias (o compose falha se faltarem):

```env
MYSQL_ROOT_PASSWORD=...
SECRET_KEY=...
ADMIN_PASSWORD=...
```

```bash
docker compose up --build
```

Sobe MySQL, Redis, API (com `alembic upgrade head` no boot), worker e frontend.

## Migrations

O schema é gerenciado pelo Alembic. **Não** há mais auto-`ALTER TABLE` no startup.

```bash
alembic upgrade head                          # aplica
alembic revision --autogenerate -m "mensagem" # nova migration a partir dos models
alembic check                                 # models e migrations divergiram?
```

Banco pré-existente (criado pelo antigo `create_all`): marque a baseline sem executar nada e siga daí.

```bash
alembic stamp 0001
alembic upgrade head
```

## Testes

```bash
cd backend
pip install -r requirements-dev.txt
pytest              # 97 testes, SQLite em diretório temporário
ruff check .
```

Os testes não precisam de MySQL nem de Redis: o Celery roda em modo *eager*.

## Segurança

- **Arquivos não são públicos.** O download passa por `GET /documentos/arquivos/{id}/download`, que exige token. Não exponha `UPLOAD_DIR` via servidor estático.
- Nunca commite o `.env` real (já ignorado).
- `SECRET_KEY` no valor padrão emite aviso no startup — troque.
- Restrinja `CORS_ORIGINS` às origens reais.
- Criação de usuário é restrita a admin/dev (`POST /auth/registrar`).
- Uploads: extensões permitidas em `backend/utils.py` (`ALLOWED_EXTENSIONS`), limite por `MAX_UPLOAD_MB`.
- Se usar nginx na frente, `client_max_body_size` precisa acompanhar `MAX_UPLOAD_MB`.

## Workflow

```
Fluxo → Atividade → ConfigTransição (origem + ação → destino)
```

- **Fluxo 0** é o estado inicial: todo documento novo entra na primeira atividade dele. Sem Fluxo 0 configurado, o upload falha com erro explícito no job.
- `Atividade.ordem` define a sequência (não o `id`).
- `Atividade.role_requerido` define quem pode aprovar/reprovar ali. Vazio = qualquer usuário autenticado; admin/dev sempre podem.
- **Reenvio** (upload de documento que já existe no mesmo projeto) segue a transição `aprovado` da atividade atual. Sem transição configurada, o documento fica onde está.

## Estrutura

```
backend/
  config.py          # única leitura de env vars
  main.py            # app, lifespan, seed admin
  models.py          # ORM
  schemas.py         # entrada (validação) + saída (response_model)
  auth.py            # JWT + bcrypt + guards
  routers/           # auth, hierarquia, documentos, workflow, usuarios
  tasks.py           # Celery: processar_upload
  utils.py           # paths, sanitização de arquivos
  migrations/        # Alembic
  tests/             # pytest
frontend/
  src/pages/         # telas
  src/components/    # UI compartilhada
```

## Análise técnica

Ver [ANALISE.md](ANALISE.md) — estado atual e pendências conhecidas.
