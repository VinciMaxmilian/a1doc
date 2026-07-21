# Análise do Projeto — Indoc (ex-A1Doc)

Sistema de Gestão Eletrônica de Documentos (GED) com workflow configurável.

> Atualizado em 2026-07-21, após a rodada de hardening descrita abaixo.

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + SQLAlchemy 2.0 |
| Banco | MySQL (PyMySQL) |
| Migrations | Alembic |
| Fila assíncrona | Celery + Redis |
| Auth | JWT (PyJWT) + bcrypt |
| Frontend | React 18 + Vite + React Router + Axios |

## Arquitetura

```
Ambiente → Área → Projeto → Documento → Arquivos (revisões)
                                       → Histórico de workflow
                                       → Valores de campos (form dinâmico)

Fluxo → Atividade → ConfigTransição (origem + ação → destino)
```

- Upload processado em background via Celery (`tasks.processar_upload`).
- Workflow por transições configuráveis; `aprovado`/`reprovado` movem o documento entre atividades, opcionalmente gerando nova revisão.
- Papéis: `dev`, `admin`, `user`. Autorização de workflow por `Atividade.role_requerido`.

---

## Correções aplicadas

### Segurança

1. **`/uploads` era público** — `StaticFiles` servia todos os documentos sem token, em caminhos previsíveis (`Ambiente/Área/Projeto/Documento/Rev N/`). Removido. O download agora passa por `GET /documentos/arquivos/{id}/download`, autenticado, e o caminho físico não é mais devolvido pela API.
2. **Workflow sem autorização** — `transitar` e `upload-revisao` exigiam apenas estar logado. Adicionado `Atividade.role_requerido`: vazio = qualquer autenticado, preenchido = só aquele papel; admin/dev sempre podem; o responsável sempre envia revisão.
3. **`docker-compose` reintroduzia senhas padrão** — `ADMIN_PASSWORD=admin123` e `SECRET_KEY=troque-em-producao` como defaults desfaziam o hardening do `main.py`. Agora são obrigatórias (`${VAR:?}`). As portas de MySQL e Redis deixaram de ser publicadas no host.
4. **Path traversal via `slugify`** — `slugify("..")` devolvia `..`, e o nome do documento é controlado pelo usuário: o arquivo era gravado acima de `UPLOAD_DIR`. Sanitização reforçada (`.`, `..`, nomes reservados do Windows) + `ensure_within()` validando o resultado.
5. **`nginx` sem `client_max_body_size`** — o default de 1 MB rejeitava uploads muito antes do limite de 100 MB da API.

### Correção

6. **Arquivos de mesmo nome no mesmo envio** — o segundo sobrescrevia o primeiro na área temporária e o job morria no `shutil.move`. `unique_path()` agora reserva o caminho atomicamente (`O_EXCL`) e é usado também no tmp.
7. **`UPLOAD_DIR` com defaults divergentes** — `C:/A1Doc/files` no worker e `./uploads` na API. Toda leitura de env passou para `config.py`.
8. **Reenvio dependia da ordem dos IDs** — o fallback "próxima atividade por id" quebrava se as atividades fossem recriadas, e a busca de transição nem filtrava por ação (num nó com `aprovado` e `reprovado` pegava um dos dois de forma indeterminada). Agora usa exclusivamente a transição `aprovado`; sem ela, o documento fica onde está e o motivo vai para o log.
9. **Fluxo 0 ausente falhava em silêncio** — documento nascia sem atividade e sem histórico. Agora o job termina em `erro` com mensagem explícita.
10. **`atualizar_campos` aceitava `campo_id` de outro tipo de documento** — gravava valores órfãos. Passou a validar contra o tipo do documento.
11. **Exclusões estouravam 500** — apagar ambiente/área/projeto/tipo/atividade/fluxo com documentos ligados violava FK `NOT NULL`. Agora retorna 400 com mensagem.
12. **Datas sem fuso** — gravadas em UTC e serializadas sem offset, o `new Date()` do navegador as lia como hora local. Passaram a sair com `+00:00`.
13. **`limit` sem teto** — `?limit=1000000` era aceito. Limitado a 100.
14. **Ordem das atividades** — `Atividade.ordem` explícita, em vez da ordenação implícita por `id`.
15. **Temporários vazavam em caso de erro** — a limpeza do `tmp/` foi para o `finally`.

### Estrutura

16. **Alembic** substituiu o `migrate_db()` que só adicionava colunas e engolia erros em log. `alembic check` roda na CI e garante que models e migrations não divergem.
17. **`response_model` em todos os endpoints** — as ~15 funções que montavam dicts à mão foram substituídas por schemas de saída. OpenAPI passou a refletir a API de verdade.
18. **97 testes (pytest)** cobrindo auth, hierarquia, workflow, upload, download, autorização e sanitização de caminhos. Rodam em SQLite, sem MySQL nem Redis.
19. **CI (GitHub Actions)** — ruff + pytest + `alembic check` + build do frontend.
20. **`requirements.txt` pinado**; `python-jose` (sem manutenção, usa `utcnow()` deprecado) trocado por `PyJWT`.
21. **`logging` no lugar de `print()`**, com nível configurável por `LOG_LEVEL`.
22. **Validação de entrada** — `EmailStr`, senha mínima de 8 caracteres, `Literal` para papéis/ações/tipos de campo, verificação de consistência da hierarquia no upload.

### Frontend

23. **Download autenticado** via blob, em vez de link direto para `/uploads`.
24. **Redirect de 401 pelo router**, não mais `window.location.href` (que recarregava a página e descartava o estado do SPA).
25. **Erros 422 não quebram mais a tela** — o `detail` do FastAPI vira array de objetos na validação; `mensagemErro()` normaliza.
26. **UI de `ordem` e `role_requerido`** na tela de atividades.

---

## Pendências conhecidas

| # | Item | Nota |
|---|------|------|
| 1 | **Token em `localStorage`** | Vulnerável a XSS. Migrar para cookie `httpOnly` exige repensar o fluxo de auth (CSRF, refresh token). Mudança de arquitetura, não um patch. |
| 2 | **Sem controle de acesso por documento** | Todo usuário autenticado lê todos os documentos. Se houver requisito de confidencialidade por ambiente/área, precisa de modelo de permissão. |
| 3 | **`index.css` monolítico (799 linhas)** | Dividir por componente ou adotar CSS modules. |
| 4 | **Bundle de 568 kB** | Code-splitting por rota. |
| 5 | **Renomear ambiente/área/projeto** | Não move os arquivos já gravados. Os antigos continuam acessíveis (o caminho está no banco), mas a árvore no disco fica inconsistente. |
| 6 | **Sem teste de frontend** | Só o build roda na CI. |
| 7 | **Sem rate limiting no login** | Força bruta não tem freio. |
| 8 | **Worker com `--pool=solo`** | Um upload por vez. Suficiente hoje; revisar se o volume crescer. |
