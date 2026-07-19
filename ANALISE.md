# Análise do Projeto — Indoc (ex-A1Doc)

Sistema de Gestão Eletrônica de Documentos (GED) com workflow configurável.

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + SQLAlchemy 2.0 |
| Banco | MySQL (PyMySQL) |
| Fila assíncrona | Celery + Redis |
| Auth | JWT (python-jose) + bcrypt |
| Frontend | React 18 + Vite + React Router + Axios |

## Arquitetura (visão geral)

```
Ambiente → Área → Projeto → Documento → Arquivos (revisões)
                                       → Histórico de workflow
                                       → Valores de campos (form dinâmico)

Fluxo → Atividade → ConfigTransição (origem + ação → destino)
```

- Upload processado assíncrono via Celery (`tasks.processar_upload`).
- Workflow por transições configuráveis; ação `aprovado`/`reprovado` move documento entre atividades, opcionalmente gerando nova revisão.
- Auto-migração de colunas no startup (`migrate_db` faz `ALTER TABLE` detectando colunas novas).
- Papéis: `dev`, `admin`, `user`.

---

## O que dá para melhorar

### 🔴 Segurança (prioridade alta)

1. **CORS liberado total** — `main.py` usa `allow_origins=["*"]` com `allow_credentials=True`. Combinação inválida/insegura. Restringir a origens conhecidas.
2. **`SECRET_KEY` fraca e versionada por padrão** — default `"change-me"` e `.env` real com chave previsível (`a1doc-secret-key-2026-...`). Gerar chave forte aleatória; garantir que `.env` nunca vá pro git (já está no `.gitignore`, ok — mas conferir histórico).
3. **Credenciais reais no `.env`** — senha de banco em texto no repositório de trabalho. Confirmar que nunca foi commitado (`git log --all -- backend/.env`).
4. **Usuário admin padrão hardcoded** — `admin / admin123` criado no startup. Forçar troca no primeiro login ou criar via seed controlado.
5. **`/auth/registrar` aberto** — qualquer um registra usuário e **escolhe o próprio `role`** (inclusive `admin`/`dev`). Escalação de privilégio trivial. Remover endpoint ou travar role para `user` e exigir admin.
6. **Upload sem validação de tipo/nome** — aceita qualquer extensão; `arquivo.filename` usado direto no path. Risco de path traversal (`../`) e upload de executáveis. Sanitizar filename (já existe `slugify`, mas não aplicado ao nome do arquivo salvo) e validar extensões permitidas.
7. **Permissões de escrita em documentos** — `transitar` e `upload-revisao` só exigem usuário logado, sem checar se é responsável/autorizado pela atividade.

### 🟠 Robustez / Correção

8. **`@app.on_event("startup")` deprecado** — FastAPI recomenda `lifespan`. Migrar.
9. **`datetime.utcnow()` deprecado** (Python 3.12+) — usar `datetime.now(timezone.utc)`.
10. **Auto-migração frágil** — `migrate_db` só adiciona colunas; não trata renomeações, tipos alterados, índices, drops. Silencia erros com `print`. Migrar para **Alembic**.
11. **Lógica de reenvio em `tasks.py` ambígua** — no upsert, se não há transição configurada faz fallback "próxima atividade por ID". Depende de ordem de ID, quebra se atividades forem recriadas. Documentar/refatorar regra de negócio.
12. **`upload-revisao` usa `shutil.copyfileobj` síncrono** dentro de rota `async` — bloqueia event loop. Ler em chunks ou rodar em threadpool.
13. **Sem tratamento de arquivo duplicado no mesmo dir** — dois uploads com mesmo filename na mesma revisão sobrescrevem silenciosamente.
14. **`Documento` sem índice em campos de filtro** — `nome`, `projeto_id` etc. usados em queries/upsert sem índice. Adicionar índices.

### 🟡 Qualidade de código

15. **Serialização manual repetida** — funções `_doc_base`, `_ativ`, `_u`, `_fluxo` montam dicts à mão. Usar `response_model` Pydantic (schemas de saída) → menos bug, doc automática.
16. **Schemas de saída ausentes** — só há schemas de entrada. Respostas não tipadas.
17. **`print()` para log** — trocar por `logging` estruturado.
18. **Sem testes** — nenhum teste automatizado. Adicionar pytest (auth, workflow, upload).
19. **Validação de e-mail fraca** — `email: str`. Usar `EmailStr` do Pydantic.
20. **`config_transicoes` sem validação de ação** — `acao` é string livre; restringir a enum (`aprovado`/`reprovado`).

### 🟢 Frontend

21. **Token em `localStorage`** — vulnerável a XSS. Considerar cookie httpOnly (exige mudança no fluxo auth).
22. **Redirect via `window.location.href`** no interceptor 401 — perde estado SPA. Usar navegação do router.
23. **`index.css` monolítico (799 linhas)** — considerar CSS modules ou dividir por componente.
24. **Sem tratamento de estado de erro/loading global** — verificar cobertura nas páginas.

### ⚙️ DevOps / Infra

25. **`celerybeat-schedule*` versionados** — arquivos binários de runtime no git. Adicionar ao `.gitignore` e remover do tracking.
26. **`venv/` commitado** — não deve estar no repo (conferir; `.gitignore` cobre `backend/venv/`, mas há arquivos rastreados? validar `git ls-files`).
27. **Sem Dockerfile / docker-compose** — subir MySQL + Redis + backend + worker manualmente via `.bat`. Compose simplificaria muito.
28. **Sem CI** — adicionar pipeline (lint + testes).
29. **`requirements.txt` com `>=` aberto** — sem lock. Usar versões fixas ou `pip-tools`/`poetry`.
30. **Sem README** — falta doc de setup/execução.

---

## Prioridade sugerida

1. Fechar buracos de segurança 1–7 (crítico).
2. Alembic + remover auto-migração (10, 25).
3. `response_model` Pydantic + testes (15–18).
4. Docker Compose + README (27, 30).
