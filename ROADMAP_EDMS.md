# ROADMAP_EDMS — Indoc

Diagnóstico do estado atual frente ao roadmap de 100 fases (`NEWPLAN.md`) e plano de
execução. Documento vivo: atualize o status de cada fase ao concluí-la.

## Estado da execução

| Etapa | Status |
|---|---|
| Etapa 0 — Preparo | **concluída** |
| FASE 1 — ACL | **concluída** |
| FASE 2 — Autenticação + Firebase | **concluída** |
| FASE 3 — Auditoria | **concluída** |
| FASE 4/5/7/8 — Modelo documental | próxima |

**Gate em 2026-09-22, após a FASE 3:**

| Verificação | Resultado |
|---|---|
| `pytest` | 203 passed |
| `ruff check .` | All checks passed |
| `alembic upgrade head` + `alembic check` | No new upgrade operations detected |
| `npm test` | 23 passed |
| `npm run build` | OK |
| Migrations | `0001`…`0005_audit_log` |
| Backend | 24 models, 7 routers, pacote `indoc/` modular |
| Frontend | 10 páginas, 5 componentes, 3 suítes de teste |

Baseline de partida, para comparação: 97 testes de backend, 0 de frontend,
14 models, 2 migrations.

---

## 1. Arquitetura de partida (diagnóstico inicial)

> Fotografia do código **antes** da Etapa 0. Mantida como registro do ponto de
> partida — o que mudou desde então está na seção 6 e em `docs/permissions.md`.

### Modelo de dados (14 tabelas)

```
User
Ambiente -> Area -> Projeto -> Documento -> DocumentoArquivo
                                         -> ValorCampo -> CampoFormulario -> TipoDocumento
                                         -> HistoricoWorkflow
Fluxo -> Atividade -> ConfigTransicao
UploadJob
```

### Autenticação e autorização (situação de partida)

- JWT HS256 (PyJWT), expiração única de 480 min, sem refresh token.
- bcrypt com truncamento explícito em 72 bytes.
- Três papéis hardcoded: `dev`, `admin`, `user` — `ADMIN_ROLES = ("admin", "dev")`.
- Token guardado em `localStorage` no frontend (`frontend/src/api.js`).
- Autorização = `require_admin` (tudo ou nada) + duas funções locais em
  `routers/documentos.py`: `_pode_transitar` e `_pode_enviar_revisao`.

### Fluxo de upload

`POST /documentos/upload` grava em `UPLOAD_DIR/tmp/{job_id}`, cria `UploadJob`,
despacha `processar_upload` (Celery). A task faz upsert por `(nome, projeto_id)`,
resolve a atividade inicial pelo **Fluxo 0**, move os arquivos para
`{UPLOAD_DIR}/{Ambiente}/{Area}/{Projeto}/{Documento}/Rev {N}/` e grava histórico.

### Workflow

`Fluxo -> Atividade (ordem, role_requerido) -> ConfigTransicao (origem + ação -> destino,
gera_nova_revisao)`. Ações limitadas às strings `aprovado` / `reprovado`.

---

## 2. Decisão de arquitetura: Firebase apenas para autenticação

`NEWDATABASE.md` introduz um projeto Firebase (`indoc-71c52`). **Decisão tomada: Firebase
fica restrito à autenticação. MySQL permanece como source of truth de todo o domínio.**

Isso preserva integralmente `NEWPLAN.md` — migrations Alembic, integridade referencial,
ACL com herança em SQL, views para BI, índices e testes de carga continuam válidos.

### Como encaixa

1. Frontend usa o Firebase Web SDK (config já fornecida) e obtém um **ID token** (JWT
   RS256 assinado pelo Google).
2. Backend **verifica** o ID token contra as chaves públicas do Google, conferindo
   `iss = https://securetoken.google.com/indoc-71c52` e `aud = indoc-71c52`.
   Isso **não exige service account** — apenas as chaves públicas.
3. Verificado o token, o backend emite **a própria sessão Indoc** (cookie `HttpOnly`,
   `Secure`, `SameSite`) conforme a FASE 2. As claims de ACL nunca saem do servidor.
4. A tabela `usuarios` continua sendo o registro autoritativo (papel, grupos, ACL, FKs).
   Ganha uma coluna `firebase_uid` (unique, nullable) como elo.
5. O login local por senha (bcrypt) **permanece** como provider alternativo — os 97
   testes e o seed do admin não podem depender de rede externa.

### Abstração a criar (FASE 2)

```
AuthProvider (interface)
├── LocalPasswordProvider    # bcrypt, já existe — vira um provider
├── FirebaseProvider         # verifica ID token
└── (futuro) OIDCProvider    # LDAP / AD / Entra ID / SSO
```

Isso é exatamente o que a FASE 2 pede ao exigir arquitetura preparada para SSO.

### Pendências a resolver antes de implementar

- **Service account: decidido pela opção (b)** — o Firebase só prova identidade;
  criação e bloqueio de usuários ficam no Indoc. Nada depende do Admin SDK. Se o
  service account for gerado depois, entra como incremento (revogar refresh do
  lado do Firebase, custom claims).
- **Firestore não é usado.** O banco criado no projeto `indoc-71c52` fica vazio:
  a decisão é Firebase só para Auth. Pode ser removido.
- **Providers habilitados no Firebase:** e-mail/senha e Google. Os dois emitem o
  mesmo tipo de ID token e são tratados igual pelo `FirebaseProvider`.
- **Chaves expostas.** As credenciais em `NEWDATABASE.md` já estão no histórico do git.
  Apagar o arquivo não as remove. Se `indoc-71c52` deixar de ser descartável, rotacionar.

Registrar como ADR quando a FASE 90 for executada: `docs/adr/0001-firebase-auth.md`.

---

## 3. Matriz de paridade funcional

Legenda: OK = existente · PARCIAL · AUSENTE

### P0 — Governança

| Fase | Capacidade | Status | Evidência / lacuna |
|---|---|---|---|
| 1 | RBAC + ACL granular | **OK** | `PermissionService` central, grupos, perfis configuráveis, ACL por recurso com herança `global→ambiente→área→projeto→documento` e deny explícito. Listagem, detalhe e download com escopo. Tela `/admin/permissoes`. Ver `docs/permissions.md`. |
| 2 | Autenticação corporativa | **OK** | Access token curto em cookie `HttpOnly` + refresh rotativo com detecção de reuso, `UserSession` rastreável, revogação imediata (uma ou todas), CSRF double-submit, bloqueio progressivo por usuário e IP. `AuthProvider` com local + Firebase; preparado para OIDC/SSO. Ver `docs/auth.md`. |
| 3 | Auditoria completa | **OK** | `AuditLog` append-only com before/after, IP, user-agent, `request_id` e sessão. Login, acesso, download, revisão, aprovação, metadado e permissão instrumentados. Tela `/admin/auditoria` com filtros. Ver `docs/auditoria.md`. |
| 4 | Modelo documental profissional | PARCIAL | `Documento` tem 10 colunas. Faltam ~25 atributos documentais (disciplina, status, confidencialidade, datas, originador, aprovador…). Campos dinâmicos existem mas sem distinção sistêmico x configurável. |
| 7 | Revisionamento avançado | PARCIAL | Revisão é um `Integer` (`revisao_indice`) — não existe entidade `Revisao`. Sem descrição, motivo, status, datas, esquemas configuráveis (A/B/C, 0/1/2). |
| 8 | Checksum e integridade | AUSENTE | `DocumentoArquivo` não guarda checksum, tamanho, MIME nem extensão. |
| 68 | Segurança / hardening | PARCIAL | Path traversal, download autorizado, CORS restrito, allowlist de extensão, limite de upload, **cookies HttpOnly/Secure, CSRF, rate limiting de login**. Faltam CSP, HSTS e validação de MIME real. |

### P1 — EDMS

| Fase | Capacidade | Status | Evidência / lacuna |
|---|---|---|---|
| 9 | Workflow BPM 2.0 | PARCIAL | Base `Fluxo/Atividade/ConfigTransicao` existe e é preservável. Sem tipos de nó, condições, ações, prioridade, prazo. Ações limitadas a `aprovado`/`reprovado`. |
| 10 | Workflow visual | AUSENTE | `AdminWorkflow.jsx` é formulário. Sem editor gráfico. |
| 11 | Responsáveis / matriz de distribuição | PARCIAL | Só `Atividade.role_requerido`. Sem grupo, perfil, regra dinâmica ou matriz por projeto. |
| 12 | Prazos e SLA | AUSENTE | Nenhum conceito de prazo. |
| 13 | Calendário corporativo | AUSENTE | — |
| 14 | Central de tarefas | AUSENTE | Não há inbox. |
| 15 | Delegação | AUSENTE | — |
| 16 | Comentários | AUSENTE | `observacao` em arquivo/histórico é o mais próximo. |
| 17 | Folha de comentários técnicos | AUSENTE | — |
| 18 | Notificações | AUSENTE | — |
| 19 | Preferências de notificação | AUSENTE | — |
| 20 | LD — Lista de Documentos | AUSENTE | `Documentos.jsx` lista, mas sem colunas configuráveis, export, congelamento ou versionamento. |
| 21 | Planejamento documental | AUSENTE | Nenhuma data planejada ou baseline. |
| 22 | Avanço documental | AUSENTE | — |
| 23 | GRD / Transmittal | AUSENTE | — |
| 24 | Numeração de GRD | AUSENTE | — |
| 25 | Confirmação de recebimento | AUSENTE | — |
| 26 | Portal de fornecedores | AUSENTE | Depende inteiramente da FASE 1. |
| 27 | Portal do cliente | AUSENTE | Idem. |

### P2 — Informação

| Fase | Capacidade | Status | Evidência / lacuna |
|---|---|---|---|
| 5 | Taxonomia configurável | PARCIAL | `CampoFormulario.opcoes` (JSON) é o único mecanismo. Sem hierarquia, código, ativo/inativo, ordenação. |
| 6 | Codificação automática | AUSENTE | `codigo = DOC-{uuid[:8]}` em `tasks.py` — aleatório, não é código documental. Sem template nem contador. |
| 28 | Busca global | PARCIAL | Só `nome ILIKE %…%` na listagem. Não respeita ACL (não há ACL). |
| 29 | Full-text search | AUSENTE | Sem OpenSearch/Elasticsearch. |
| 30 | Extração de texto | AUSENTE | — |
| 31 | OCR | AUSENTE | — |
| 32 | Preview de arquivos | AUSENTE | Só download. |
| 33 | CAD 2D | AUSENTE | `.dwg`/`.dxf` são aceitos no upload, mas sem preview. |
| 34 | CAD 3D / modelos | AUSENTE | — |
| 35 | Comparação de revisões | AUSENTE | — |
| 36 | Assinatura eletrônica | AUSENTE | — |
| 37 | Controle de cópia | AUSENTE | — |
| 38 | Documentos obsoletos | AUSENTE | Sem ciclo vigente/substituído/obsoleto/cancelado. |
| 39 | Retenção documental | AUSENTE | — |
| 40 | Lixeira e soft delete | AUSENTE | Todos os deletes são físicos. Nenhuma tabela tem `deleted_at`. |

### P3 — Gestão

| Fase | Capacidade | Status |
|---|---|---|
| 41–43 | Dashboards (operacional, engenharia, fornecedores) | AUSENTE |
| 44 | Framework de relatórios | AUSENTE |
| 45 | Views salvas | AUSENTE |
| 84 | Camada de BI | AUSENTE |
| 85 | Biblioteca de KPIs | AUSENTE |

### P4 — Plataforma

| Fase | Capacidade | Status | Evidência / lacuna |
|---|---|---|---|
| 46 | Customização de telas | AUSENTE | — |
| 47 | Form builder | PARCIAL | `CampoFormulario` suporta `text/number/date/select` com `ordem` e `opcoes`. Falta obrigatoriedade, regex, min/max, default, visibilidade condicional, tipos usuário/grupo/taxonomia. |
| 48 | Motor de regras | AUSENTE | — |
| 49 | BPM genérico (ProcessDefinition) | AUSENTE | Workflow é preso a documento. |
| 54 | API corporativa `/api/v1/` | PARCIAL | Paginação existe em documentos (`skip/limit/total`). Sem prefixo de versão, sem request-id, sem erros padronizados. |
| 55 | Webhooks | AUSENTE | — |
| 56 | Integrações | AUSENTE | — |
| 57 | Importação em massa | AUSENTE | — |
| 58 | Exportação em massa | AUSENTE | — |
| 59 | Storage abstraction | AUSENTE | `UPLOAD_DIR` local acoplado em `utils.py`, `tasks.py` e `routers/documentos.py`. |
| 60 | Antivírus | AUSENTE | — |
| 61 | Celery robusto | PARCIAL | Uma task, uma fila, sem retry/backoff/timeout/idempotência/dead-letter. |
| 62 | Observabilidade | PARCIAL | `X-Request-ID` por requisição (propagado até a auditoria), logging com `request_id` e formato `text`/`json`. Faltam métricas, `/ready` e health de worker. |
| 63 | Performance | PARCIAL | `joinedload` bem usado em documentos/hierarquia, índices nas FKs, paginação. Sem análise de query, cache ou teste de volume. |
| 70 | Multi-tenancy | AUSENTE | Nenhum escopo organizacional. |
| 80 | Administração low-code | AUSENTE | — |
| 81 | Templates de projeto | AUSENTE | — |
| 82 | Versionamento de configuração | AUSENTE | — |
| 96 | Feature flags | AUSENTE | — |

### P5 — Engenharia avançada

| Fase | Capacidade | Status |
|---|---|---|
| 50 | Relacionamento entre documentos | AUSENTE |
| 51 | Tags de equipamento | AUSENTE |
| 52 | Databook | AUSENTE |
| 53 | Handover / as-built | AUSENTE |
| 83 | Migração de sistemas antigos | AUSENTE |

### P6 — IA

| Fase | Capacidade | Status |
|---|---|---|
| 71–79 | AIService, RAG, IA com ACL, chat, consulta estruturada, classificação, comparação | AUSENTE |

### Transversais

| Fase | Capacidade | Status | Evidência / lacuna |
|---|---|---|---|
| 64 | Frontend modular | AUSENTE | `index.css` monolítico, sem lazy loading nem code splitting. (Não tocado na Etapa 0.) |
| 65 | Design system | PARCIAL | 5 componentes (`Modal`, `ConfirmModal`, `GlassTabs`, `Layout`, `PrivateRoute`). Faltam ~13 dos listados. |
| 66 | Tabelas corporativas | AUSENTE | — |
| 67 | Testes frontend | PARCIAL | Vitest + Testing Library instalados, 14 testes, passo no CI. Falta Playwright/E2E. |
| 69 | LGPD e governança | AUSENTE | — |
| 86 | Acessibilidade | AUSENTE | Não auditado. |
| 87 | Responsividade | PARCIAL | Não verificado sistematicamente. |
| 88 | PWA | AUSENTE | — |
| 89 | Documentação | PARCIAL | `docs/permissions.md`, `docs/auth.md`, `docs/auditoria.md`. Faltam architecture, database, workflow, edms, transmittals, search, ai, deployment. |
| 90 | ADRs | AUSENTE | — |
| 91 | Seeds de demonstração | AUSENTE | Só o seed do admin. |
| 92 | Teste de carga | AUSENTE | — |
| 93 | Backup e recuperação | AUSENTE | — |
| 94 | Recuperação de desastre | AUSENTE | — |
| 95 | Admin health dashboard | AUSENTE | Só `/health` trivial. |
| 97 | Licenciamento de dependências | PARCIAL | Versões fixas em `requirements.txt`, sem registro de licenças. |
| 98 | Critério final de paridade | PARCIAL | Este documento. |
| 99 | Estrutura modular | PARCIAL | Pacote `indoc/` com `core/users/hierarchy/documents/workflow/permissions/audit/auth`. `permissions`, `auth` e `audit` já completos (models+schemas+service+router). Falta mover `schemas.py` legado e os routers de documentos/hierarquia/workflow. |
| 100 | Gate de qualidade | OK | CI roda ruff + pytest + alembic check + `npm test` + build. |

### Resumo

| Status | Fases | Antes da Etapa 0 |
|---|---|---|
| OK | 5 | 1 |
| PARCIAL | 21 | 22 |
| AUSENTE | 74 | 77 |

P0 — Governança está concluído, exceto o modelo documental (fases 4/5/7/8), que
é a próxima etapa.

O núcleo é pequeno mas de boa qualidade: sanitização de path bem feita, download
autenticado, `unique_path` atômico com `O_EXCL`, migrations reais, testes verdes,
comentários que explicam o *porquê*. A base é evoluível — não há motivo para reescrever.

---

## 4. Dívidas técnicas a resolver antes / junto de P0

Ordenadas por impacto no que vem depois.

| # | Dívida | Por que bloqueia | Onde |
|---|---|---|---|
| ~~D1~~ | ~~**Listagem de documentos sem escopo de acesso**~~ — **resolvida na FASE 1.** `_somente_legiveis` filtra na query; `GET /{id}` e o download passaram a exigir permissão. Por compatibilidade, o perfil semente `usuario_padrao` ainda concede leitura global: fechar de fato é remover essa atribuição (ver `docs/permissions.md`). | Qualquer usuário autenticado lista todos os documentos de todos os projetos. É o problema que a FASE 1 existe para resolver — e o mesmo vale para a árvore de hierarquia. | `routers/documentos.py:99`, `routers/hierarquia.py:22` |
| ~~D2~~ | ~~**Autorização espalhada nos routers**~~ — **resolvida.** Tudo passa pelo `PermissionService`; o que restou em `documentos.py` é a restrição de workflow (`role_requerido`), que é outra coisa. | A FASE 1 exige `PermissionService` central e proíbe lógica replicada. Hoje `_pode_transitar`/`_pode_enviar_revisao` vivem dentro do router de documentos. | `routers/documentos.py:31-49` |
| D3 | **`schemas.py` monolítico** (models: resolvido na Etapa 0) | P0 sozinha adiciona ~8 models (Grupo, UsuarioGrupo, Perfil, ACL, UserSession, AuditLog, Revisao…). Fazer a FASE 99 *depois* significa mover 50 models. Fazer o esqueleto modular *antes* custa pouco. | `backend/models.py`, `backend/schemas.py` |
| ~~D4~~ | ~~**`AUTO_CREATE_TABLES` default `True`**~~ — **resolvida.** Default `false`; o conftest liga explicitamente. | `NEWPLAN.md` é explícito: "nunca deixe o banco dependendo de `create_all`". O default deveria ser `false`, com os testes ligando explicitamente. | `config.py:52` |
| D5 | **Caminho de arquivo derivado de nomes mutáveis** | `doc_rev_dir()` monta o path com os nomes de ambiente/área/projeto/documento. Renomear qualquer um órfã os arquivos já gravados — não há rename handling. Resolver junto da FASE 59 (`StorageProvider`), usando IDs. | `utils.py:89`, `tasks.py:110` |
| D6 | **`Documento.codigo` é UUID aleatório** | `DOC-3F2A9B1C` não é código documental. A FASE 6 substitui isso por template configurável — e precisa de estratégia de migração para os códigos já emitidos. | `tasks.py:85` |
| D7 | **Revisão é um inteiro, não uma entidade** | GRD (23) precisa fotografar *qual revisão* foi enviada; checksum (8), comparação (35) e confirmação de recebimento (25) todos dependem de `Revisao` existir. É a mudança estrutural mais cara de P0. | `models.py` (`Documento.revisao_indice`) |
| D8 | **Sem soft delete em lugar nenhum** (atenuada: a auditoria já preserva o histórico de exclusões, mas a entidade some) | Deletes são físicos e as FKs são `NOT NULL`, por isso os endpoints bloqueiam exclusão quando há documentos. A FASE 40 muda isso — mas auditoria (3) e retenção (39) já pressupõem que nada desaparece. | `routers/hierarquia.py` |
| ~~D9~~ | ~~**Sem request_id / structured logging**~~ — **resolvida.** `RequestIdMiddleware` + `LOG_FORMAT=text\|json`. | `AuditLog` tem campo `request_id`. Sem middleware de correlação, ele nasce vazio. Fazer antes da FASE 3. | `main.py`, `config.py` |
| ~~D10~~ | ~~**Zero testes de frontend**~~ — **resolvida.** Vitest + Testing Library, 14 testes, passo no CI. Playwright fica para a FASE 67. | A FASE 100 exige rodar testes de frontend ao fim de cada fase. Hoje esse gate não existe e o CI só faz `npm run build`. | `frontend/`, `.github/workflows/ci.yml` |
| ~~D11~~ | ~~**`ANALISE.md` referenciado mas inexistente**~~ — **resolvida.** README aponta para este roadmap. | O README aponta para ele. Ou recriar, ou substituir o link por este roadmap. | `README.md` (última linha) |
| D12 | **Celery sem retry/idempotência** | `processar_upload` re-executada duplicaria arquivos: o upsert é por `(nome, projeto_id)`, mas os `DocumentoArquivo` seriam inseridos de novo. Resolver antes de multiplicar as filas (FASE 61). | `tasks.py:68` |

| D13 | **react-router com open-redirect conhecido** | GHSA-wrjc-x8rr-h8h6 afeta todo o 6.x e 7.x até 7.17.0; só é corrigido no 7.18.4, que é mudança de major. `npm audit fix` subiu 6.21→6.30.6 mas **não** limpa o advisory. Risco prático baixo enquanto nenhum destino de navegação vier de entrada do usuário. Decidir na FASE 68 (hardening) ou 64 (frontend modular). | `frontend/package.json` |

---

## 5. Dependências entre fases

Arestas que determinam a ordem real de execução:

```
D3 (modularizar) --> 1 ACL --+--> 26 portal fornecedor
                             +--> 27 portal cliente
                             +--> 28 busca global
                             +--> 58 exportação
                             +--> 73 IA com ACL --> 74..79

2 auth --> UserSession --+
D9 request_id -----------+--> 3 auditoria --> 15 delegação, 40 lixeira, 69 LGPD

5 taxonomia --> 4 modelo documental --+--> 6 codificação
                                      +--> 20 LD --> 21 planejamento --> 22 avanço --> 42 dashboard eng.

D7 Revisao --+--> 8 checksum --> 60 antivírus
             +--> 23 GRD --> 24 numeração --> 25 recebimento
             +--> 35 comparação --> 76 comparação com IA

9 BPM 2.0 --+--> 10 editor visual
            +--> 11 responsáveis --> 12 SLA --> 13 calendário
            +--> 14 inbox --> 15 delegação

59 storage --> 32 preview --> 33 CAD 2D --> 34 CAD 3D
30 extração --> 29 full-text --> 31 OCR --> 72 RAG
16 comentários --> 17 folha de comentários --> 18 notificações --> 19 preferências
```

**Consequência prática:** a FASE 5 (taxonomia) é pré-requisito da FASE 4, embora esteja
listada depois. E a FASE 59 (storage) aparece só na posição 59, mas resolve D5 e destrava
todo o P2 de preview — vale antecipá-la para o fim de P0.

---

## 6. Plano de execução

### Etapa 0 — Preparo (antes da ACL)

Resolve D3, D4, D9, D11 e monta o gate que a FASE 100 exige.

1. Esqueleto modular: `backend/app/{core,auth,users,permissions,documents,workflow,audit}/`
   com re-export a partir de `models.py`/`schemas.py` para não quebrar imports.
2. `AUTO_CREATE_TABLES` default `false`; `conftest.py` liga explicitamente.
3. Middleware de request-id + logging estruturado.
4. Vitest + Testing Library no frontend, com um teste de fumaça, e o passo no CI.
5. Recriar `ANALISE.md` ou repontar o README para este arquivo.

Gate: 97 testes continuam verdes, ruff limpo, `alembic check` sem diff.

### Etapa 1 — FASE 1: ACL

Models: `Grupo`, `UsuarioGrupo`, `PerfilPermissao`, `PerfilUsuario`, `ACLEntry`.
Colunas novas em `usuarios`: `departamento`, `cargo`, `ultimo_login`, `bloqueado_em`,
`motivo_bloqueio` — todas nullable (requisito de compatibilidade do plano).

`PermissionService` central, com resolução hierárquica
Ambiente -> Área -> Projeto -> Documento e `deny` explícito vencendo `allow`.
Aplicar em **todos** os endpoints, incluindo D1 (listagem e árvore).

Os papéis `dev`/`admin`/`user` atuais viram perfis-semente — ninguém perde acesso.

### Etapa 2 — FASE 2: autenticação + Firebase

`AuthProvider` com `LocalPasswordProvider` e `FirebaseProvider`, `UserSession`,
refresh token rotativo, cookie `HttpOnly`, rate limiting, `firebase_uid` em `usuarios`.

### Etapa 3 — FASE 3: auditoria

`AuditLog` + dependency de auditoria + tela administrativa de consulta.

### Etapa 4 — FASES 4/5/7/8: modelo documental

Taxonomia primeiro, depois atributos de documento, depois a entidade `Revisao`
(a migração mais delicada: `revisao_indice` vira linhas em `revisoes` preservando
o histórico existente), depois checksum.

Só então começa P1.

### Regra de encerramento de fase (FASE 100)

```bash
cd backend && ruff check . && pytest
DATABASE_URL="sqlite:///./tmp-check.db" alembic upgrade head && alembic check
cd ../frontend && npm run build && npm test
```

Nenhuma fase é considerada concluída com teste vermelho, migration pendente
ou documentação desatualizada.
