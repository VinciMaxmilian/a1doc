# Indoc

Sistema de Gestão Eletrônica de Documentos (GED) com workflow configurável.

Hierarquia **Ambiente → Área → Projeto → Documento**, formulários dinâmicos por tipo de documento, versionamento de revisões e workflow por transições (`aprovado`/`reprovado`) configuráveis.

## Stack

- **Backend:** FastAPI + SQLAlchemy 2.0 + MySQL
- **Migrations:** Alembic
- **Fila assíncrona:** Celery + Redis (processamento de uploads)
- **Auth:** access token curto + refresh rotativo em cookie HttpOnly; provider Firebase opcional
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
| `AUTO_CREATE_TABLES` | Mantenha `false` — o schema é do Alembic |

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
pytest              # 203 testes, SQLite em diretório temporário
ruff check .
```

```bash
cd frontend
npm test            # Vitest + Testing Library
npm run test:watch  # modo interativo
```

Os testes de backend não precisam de MySQL nem de Redis: o Celery roda em modo *eager*.

O CI roda os dois lados, mais `alembic check` e o build do frontend. Nenhuma fase
do roadmap é dada por concluída com qualquer um desses vermelho.

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
  auth.py            # JWT + bcrypt + guards
  routers/           # auth, hierarquia, documentos, workflow, usuarios
  tasks.py           # Celery: processar_upload
  utils.py           # paths, sanitização de arquivos
  migrations/        # Alembic
  tests/             # pytest
  models.py          # shim: reexporta indoc/*/models.py
  schemas.py         # entrada (validação) + saída (response_model)
  database.py        # shim: reexporta indoc/core/database.py
  indoc/             # pacote modular (o código novo nasce aqui)
    core/            # database, time, request_context, middleware, logging
    users/           # models de usuário
    hierarchy/       # ambiente, área, projeto
    documents/       # documento, arquivo, tipo, campo, valor, upload job
    workflow/        # fluxo, atividade, transição, histórico
    permissions/     # ACL: constants, models, service, deps, router, seed
    audit/           # auditoria: actions, models, service, router
    auth/            # sessões, tokens, cookies, CSRF, throttle, providers
frontend/
  src/pages/         # telas
  src/components/    # UI compartilhada
  src/**/*.test.jsx  # Vitest
```

`models.py`, `schemas.py` e `database.py` na raiz são **shims de compatibilidade**:
reexportam o que vive em `indoc/`. Importar `models` continua funcionando — e é o
que garante que todas as classes estejam registradas em `Base.metadata` antes do
SQLAlchemy resolver as `relationship()`. Código novo deve importar de `indoc.*`.

## Autenticação

Access token curto em cookie `HttpOnly` + refresh token rotativo, com detecção
de reuso, revogação imediata por sessão e bloqueio progressivo contra força
bruta. O token **não** fica mais em `localStorage`.

`COOKIE_SECURE` é `true` por padrão — em dev sobre `http://localhost` defina
`COOKIE_SECURE=false`, senão o navegador descarta o cookie e o login não
persiste.

Firebase é suportado como provider de **identidade** (e-mail/senha e Google),
sem service account. O Firestore não é usado: o MySQL continua sendo o source
of truth. Ver [docs/auth.md](docs/auth.md).

## Auditoria

Registro append-only de login, acesso, download, revisão, aprovação, alteração
de metadado e de permissão, com IP, dispositivo e `request_id`. Consulta em
**Administração → Auditoria**. Ver [docs/auditoria.md](docs/auditoria.md).

## Observabilidade

Toda requisição recebe um `X-Request-ID` (reaproveitado do cliente quando vem em
formato aceito, gerado caso contrário) que é ecoado na resposta e aparece em todo
log emitido durante o tratamento. `LOG_FORMAT=json` troca o formato de texto por
um objeto por linha, para agregadores.

## Permissões

Controle de acesso por ACL com herança `global → ambiente → área → projeto →
documento`, grupos, perfis configuráveis e negação explícita. Toda a política é
dado: nenhum endpoint replica lógica de autorização.

Ver [docs/permissions.md](docs/permissions.md) — inclui a nota de
compatibilidade sobre como fechar o acesso amplo herdado da versão anterior.

## Roadmap e estado atual

Ver [ROADMAP_EDMS.md](ROADMAP_EDMS.md) — diagnóstico do estado atual frente ao
roadmap EDMS, matriz de paridade funcional, dívidas técnicas e ordem de execução.
