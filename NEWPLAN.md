Você está trabalhando no projeto **Indoc**, disponível neste repositório.

O objetivo desta tarefa é transformar o Indoc em uma plataforma corporativa completa de **GED + EDMS + ECM + BPM**, alcançando paridade funcional, conceito por conceito, com plataformas maduras de gestão documental de engenharia como o Greendocs, mas:

* NÃO copie código proprietário.
* NÃO copie identidade visual, textos, nomes internos ou interface do Greendocs.
* NÃO tente criar um clone visual.
* Use o Greendocs apenas como referência funcional e de categoria de produto.
* Preserve a identidade e a arquitetura do Indoc.
* O código existente deve ser evoluído, e não refeito sem necessidade.

# 1. LEIA O PROJETO ANTES DE ALTERAR QUALQUER COISA

Comece estudando integralmente:

* `README.md`
* `ANALISE.md`
* `.claude/rules/`
* models existentes
* schemas
* routers
* migrations Alembic
* tasks Celery
* autenticação
* workflow
* frontend
* testes
* Docker
* CI

Mapeie a arquitetura atual.

O núcleo existente é aproximadamente:

Ambiente
→ Área
→ Projeto
→ Documento
→ Arquivos/Revisões
→ Valores de campos
→ Histórico de workflow

E:

Fluxo
→ Atividade
→ ConfigTransição

Tecnologias atuais:

Backend:

* Python
* FastAPI
* SQLAlchemy 2
* MySQL
* Alembic
* Celery
* Redis
* JWT
* bcrypt

Frontend:

* React 18
* Vite
* React Router
* Axios

Infra:

* Docker
* GitHub Actions

Não substitua essas tecnologias sem necessidade comprovada.

---

# 2. REGRA PRINCIPAL DE IMPLEMENTAÇÃO

Implemente o sistema em **fases independentes e funcionais**.

NÃO tente implementar tudo de uma vez.

Para cada fase:

1. analise o estado atual;
2. desenhe a alteração;
3. crie ou altere models;
4. crie migration Alembic;
5. implemente services/repositories quando necessário;
6. implemente API;
7. implemente autorização;
8. implemente frontend;
9. implemente testes;
10. rode testes existentes;
11. corrija regressões;
12. atualize documentação;
13. faça somente então a próxima fase.

Nunca deixe o banco dependendo de `create_all`.

Toda alteração estrutural deve possuir migration Alembic.

Não quebre os 97+ testes existentes.

Adicione novos testes.

---

# 3. OBJETIVO FUNCIONAL

Ao terminar, o Indoc deverá oferecer:

GED
+
EDMS
+
ECM
+
BPM
+
controle documental de engenharia
+
governança
+
auditoria
+
busca corporativa
+
colaboração
+
automação
+
dashboards
+
integrações
+
IA documental

O Indoc deverá se tornar uma **fonte única confiável de documentação técnica**.

---

# FASE 1 — RBAC + ACL GRANULAR

Atualmente autenticação e alguns papéis existem, mas precisamos transformar isso em controle de acesso corporativo.

Criar:

## Usuários

Manter usuários existentes.

Adicionar:

* ativo/inativo
* departamento
* cargo opcional
* último login
* data de bloqueio
* motivo de bloqueio

## Grupos

Criar:

`Grupo`

Exemplos:

* Engenharia Mecânica
* Engenharia Elétrica
* Controle Documental
* Administração
* Cliente
* Fornecedor A
* Fornecedor B

Relacionamento N:N:

`UsuarioGrupo`

---

## Perfis

Criar perfis configuráveis.

Exemplo:

`PerfilPermissao`

Perfis:

* administrador
* controle_documental
* projetista
* revisor
* aprovador
* fornecedor
* cliente
* consulta

Não hardcode esses nomes como única possibilidade.

Permita criar outros.

---

## ACL

Criar permissões para:

* Ambiente
* Área
* Projeto
* Documento

Modelo conceitual:

ACL

* subject_type
* subject_id
* resource_type
* resource_id
* permission
* allow/deny
* inherited

Subjects:

* usuário
* grupo
* perfil

Permissions:

* read
* create
* update
* delete
* download
* upload
* revise
* comment
* approve
* reject
* distribute
* manage_permissions
* manage_workflow
* manage_metadata

Implementar herança:

Ambiente
↓
Área
↓
Projeto
↓
Documento

Permissões específicas podem sobrescrever as herdadas.

Implementar `deny` explícito.

Criar serviço central:

`PermissionService`

Nenhum endpoint deve replicar lógica de autorização manualmente.

---

# FASE 2 — AUTENTICAÇÃO CORPORATIVA

Corrigir a pendência atual de token em `localStorage`.

Implementar:

* access token curto
* refresh token
* cookie `HttpOnly`
* `Secure`
* `SameSite`
* proteção CSRF quando aplicável
* rotação de refresh token
* revogação
* logout por sessão
* logout de todas as sessões

Criar:

`UserSession`

Registrar:

* usuário
* IP
* user-agent
* criação
* último uso
* expiração
* revogada_em

Adicionar:

* rate limiting no login
* proteção contra brute force
* bloqueio temporário progressivo
* logs de autenticação

Preparar arquitetura para futuramente suportar:

* LDAP
* Active Directory
* Microsoft Entra ID
* OAuth2/OIDC
* SSO

Não é obrigatório ativar integrações externas agora, mas a arquitetura deve estar preparada.

---

# FASE 3 — AUDITORIA COMPLETA

Criar sistema central de auditoria.

Modelo:

`AuditLog`

Campos:

* id
* timestamp
* user_id
* session_id
* action
* entity_type
* entity_id
* project_id
* document_id
* ip
* user_agent
* request_id
* before_json
* after_json
* metadata_json

Registrar no mínimo:

* login
* logout
* login inválido
* criação
* edição
* exclusão
* download
* visualização
* upload
* revisão
* alteração de metadata
* alteração de permissão
* comentário
* aprovação
* reprovação
* assinatura
* GRD
* alteração de workflow
* exportação

Logs não podem ser editados por usuários comuns.

Crie tela administrativa para consulta.

Filtros:

* usuário
* ação
* documento
* projeto
* intervalo de datas
* IP
* entidade

---

# FASE 4 — MODELO DOCUMENTAL PROFISSIONAL

Transformar Documento em uma entidade documental corporativa completa.

O arquivo deve ser apenas uma representação física do documento.

Adicionar ao Documento:

* código documental
* título
* descrição
* tipo
* disciplina
* categoria
* subcategoria
* projeto
* contrato
* fornecedor
* cliente
* sistema
* subsistema
* área física
* tag de equipamento
* classificação
* confidencialidade
* status documental
* status de workflow
* revisão atual
* data de emissão
* data prevista
* data real
* responsável
* originador
* aprovador
* idioma
* formato
* páginas
* notas

Nem todos devem ser colunas rígidas.

Usar corretamente o mecanismo existente de campos dinâmicos.

Criar distinção entre:

* campos sistêmicos
* campos configuráveis

---

# FASE 5 — TAXONOMIA CONFIGURÁVEL

Criar módulo de taxonomia.

Administradores devem conseguir criar classificações sem alterar código.

Exemplos:

Disciplina:

* Civil
* Mecânica
* Tubulação
* Elétrica
* Instrumentação
* Automação

Tipo:

* Desenho
* Memorial
* Especificação
* Lista
* Relatório
* Datasheet
* Procedimento

Criar:

`Taxonomy`

`TaxonomyItem`

Suportar:

* hierarquia pai/filho
* ativo/inativo
* código
* descrição
* ordenação

Campos dinâmicos podem referenciar uma taxonomia.

---

# FASE 6 — CODIFICAÇÃO DOCUMENTAL AUTOMÁTICA

Criar regras configuráveis para geração de códigos.

Exemplo:

A1-MEC-PROJ001-DWG-000123

Administrador deve configurar template:

`{empresa}-{disciplina}-{projeto}-{tipo}-{sequencial}`

Criar contador seguro contra concorrência.

Nunca gerar códigos duplicados.

Permitir códigos externos manuais quando autorizado.

---

# FASE 7 — REVISIONAMENTO AVANÇADO

Evoluir revisão existente.

Cada revisão deverá possuir:

* identificador
* número/letra
* descrição
* motivo
* criada_por
* criada_em
* emitida_em
* status
* arquivos
* checksum
* comentários
* workflow associado

Suportar esquemas:

* A/B/C
* 0/1/2
* P0/P1
* configurable

Nunca apagar histórico de revisão.

Permitir marcar uma revisão como obsoleta, mas manter histórico.

Criar comparação de metadata entre revisões.

---

# FASE 8 — CHECKSUM E INTEGRIDADE

Calcular SHA-256 para arquivos.

Salvar:

* checksum
* tamanho
* MIME
* extensão
* data

Ao baixar ou processar:

permitir validação de integridade.

Detectar uploads idênticos.

Não necessariamente bloquear duplicados, mas avisar.

---

# FASE 9 — WORKFLOW BPM 2.0

Evoluir o workflow atual.

Hoje existe:

Fluxo
→ Atividade
→ ConfigTransição

Preservar a base.

Adicionar tipos de nós:

* início
* atividade
* decisão
* aprovação
* revisão
* tarefa automática
* gateway
* fim

Transições deverão aceitar:

* condição
* ação
* prioridade
* prazo
* regra

Criar condições configuráveis sobre:

* metadata
* usuário
* grupo
* projeto
* documento
* status
* valor de campo

Exemplo:

Se disciplina == "Mecânica"
→ Engenharia Mecânica

Se valor_contrato > X
→ Aprovação gerencial

---

# FASE 10 — WORKFLOW VISUAL

Criar editor visual de workflow.

Utilizar biblioteca React adequada, preferencialmente algo como React Flow.

Usuário administrador poderá:

* criar nó
* arrastar
* conectar
* remover
* configurar
* definir responsáveis
* definir prazo
* configurar transição

Representação persistida no backend.

Não deixar regra crítica somente no frontend.

---

# FASE 11 — RESPONSÁVEIS E MATRIZ DE DISTRIBUIÇÃO

Criar regras de responsáveis.

Uma atividade pode possuir:

* usuário específico
* grupo
* perfil
* regra dinâmica

Criar matriz de distribuição documental.

Exemplo:

Disciplina Mecânica:
→ Mecânica
→ Controle Documental
→ Cliente X

Disciplina Elétrica:
→ Elétrica
→ Controle Documental

A distribuição deve ser configurável por projeto.

---

# FASE 12 — PRAZOS E SLA

Adicionar SLA ao workflow.

Cada atividade poderá possuir:

* prazo em horas/dias
* calendário utilizado
* aviso antecipado
* escalonamento

Criar:

`WorkflowDeadline`

Status:

* dentro_do_prazo
* próximo_do_prazo
* atrasado

Criar escalonamento:

Após X horas de atraso:
→ avisar responsável

Após Y:
→ avisar coordenador

Após Z:
→ avisar gerente

---

# FASE 13 — CALENDÁRIO CORPORATIVO

Para calcular prazos corretamente, criar:

`BusinessCalendar`

Suportar:

* dias úteis
* finais de semana
* feriados
* exceções
* calendário por projeto/empresa

---

# FASE 14 — CENTRAL DE TAREFAS

Criar página:

**Minha Caixa de Entrada**

Categorias:

* aguardando minha análise
* aguardando aprovação
* aguardando revisão
* devolvidos
* vencendo
* atrasados
* mencionados
* delegados

Filtros por:

* projeto
* disciplina
* atividade
* prazo
* prioridade

---

# FASE 15 — DELEGAÇÃO

Permitir delegar atividades.

Registrar:

* responsável original
* delegado
* início
* fim
* motivo

Toda delegação deve aparecer na auditoria.

Suportar férias/ausência futuramente.

---

# FASE 16 — COMENTÁRIOS

Criar comentários documentais.

`DocumentComment`

Campos:

* documento
* revisão
* usuário
* texto
* data
* resolvido
* resolvido_por

Suportar:

* respostas
* threads
* @menções
* anexos
* edição limitada

Nunca perder histórico de comentários.

---

# FASE 17 — COMENTÁRIOS TÉCNICOS E FOLHA DE COMENTÁRIOS

Criar módulo específico para engenharia.

Permitir registrar comentário:

* código
* disciplina
* página
* item
* descrição
* responsável
* resposta
* status

Status:

* aberto
* respondido
* aceito
* rejeitado
* encerrado

Gerar relatório PDF/XLSX posteriormente.

---

# FASE 18 — NOTIFICAÇÕES

Criar central interna.

Eventos:

* documento enviado
* documento atribuído
* aprovação
* reprovação
* comentário
* menção
* prazo próximo
* atraso
* nova revisão
* nova GRD
* assinatura

Criar:

`Notification`

Estados:

* não lida
* lida
* arquivada

Suportar posteriormente:

* email
* Teams
* webhook

---

# FASE 19 — PREFERÊNCIAS DE NOTIFICAÇÃO

Cada usuário deve decidir:

* notificações internas
* email
* digest diário
* eventos desejados

Evitar spam.

---

# FASE 20 — LD — LISTA DE DOCUMENTOS

Criar módulo de **Lista de Documentos de Engenharia**.

Uma LD deverá mostrar:

* código
* título
* disciplina
* tipo
* originador
* revisão
* status
* responsável
* data prevista
* data real
* avanço
* dias de atraso

Permitir:

* filtros
* ordenação
* colunas configuráveis
* exportação Excel
* salvar visualização

A LD deve poder ser congelada/versionada.

---

# FASE 21 — PLANEJAMENTO DOCUMENTAL

Adicionar datas planejadas:

* previsão inicial
* previsão atual
* emissão real
* aprovação prevista
* aprovação real

Guardar baseline.

Nunca sobrescrever baseline.

Calcular:

* atraso
* adiantamento
* desvio

---

# FASE 22 — AVANÇO DOCUMENTAL

Permitir configurar pesos.

Exemplo:

Criado = 10%
Emitido = 30%
Em análise = 50%
Aprovado = 80%
As-built = 100%

O avanço deve ser configurável por projeto ou tipo de documento.

Dashboards devem usar esses valores.

---

# FASE 23 — GRD / TRANSMITTAL

Criar módulo completo de Guia de Remessa de Documentos.

Entidade:

`Transmittal`

Campos:

* número
* projeto
* origem
* destino
* motivo
* finalidade
* data
* emissor
* observação
* status

Relacionamento:

`TransmittalDocument`

Registrar exatamente:

* documento
* revisão
* arquivo enviado

Uma GRD deve representar uma fotografia imutável das revisões enviadas naquele momento.

Finalidades:

* aprovação
* informação
* comentário
* construção
* proposta
* as-built
* outras configuráveis

---

# FASE 24 — NUMERAÇÃO AUTOMÁTICA DE GRD

Suportar template:

GRD-{PROJETO}-{ANO}-{SEQ}

Garantir unicidade e concorrência.

---

# FASE 25 — CONFIRMAÇÃO DE RECEBIMENTO

Permitir destinatário:

* visualizar
* baixar
* confirmar recebimento

Registrar:

* quem
* quando
* IP
* revisão

Criar comprovante.

---

# FASE 26 — PORTAL DE FORNECEDORES

Criar acesso externo seguro.

Fornecedor só poderá visualizar:

* seus projetos
* seus documentos
* suas tarefas
* GRDs relacionadas

Nunca deve conseguir navegar para recursos fora do seu escopo.

Fornecedor poderá:

* enviar documento
* enviar revisão
* responder comentário
* consultar status
* receber reprovação
* baixar versões autorizadas

---

# FASE 27 — PORTAL DO CLIENTE

Semelhante ao portal de fornecedores.

Cliente poderá possuir permissões como:

* consulta
* análise
* comentário
* aprovação
* download

Configurável por projeto.

---

# FASE 28 — BUSCA GLOBAL

Criar busca global no topo do sistema.

Pesquisar:

* código
* título
* metadata
* projeto
* revisão
* usuário
* comentários
* conteúdo

A busca deve respeitar ACL.

Nunca retornar documento sem permissão.

---

# FASE 29 — FULL-TEXT SEARCH

Adicionar motor dedicado.

Avaliar:

* OpenSearch
  ou
* Elasticsearch

Não substituir MySQL.

MySQL continua source of truth.

Pipeline:

arquivo
→ extração de texto
→ indexação
→ OpenSearch

Criar tarefas Celery para indexação.

---

# FASE 30 — EXTRAÇÃO DE TEXTO

Suportar inicialmente:

* PDF
* DOCX
* XLSX
* PPTX
* TXT

Criar arquitetura por adapters.

Não colocar tudo em uma função gigantesca.

---

# FASE 31 — OCR

Adicionar OCR.

Para PDFs digitalizados e imagens:

* detectar ausência de texto
* aplicar OCR
* armazenar texto extraído
* indexar

Avaliar:

* Tesseract
* PaddleOCR

OCR deve ser assíncrono.

---

# FASE 32 — PREVIEW DE ARQUIVOS

Criar visualizador interno.

Suportar:

* PDF
* imagens
* texto

Adicionar depois:

* Office
* CAD

Nunca exigir download para simples consulta.

---

# FASE 33 — CAD 2D

Criar arquitetura para preview de:

* DWG
* DXF

Não tente implementar parser DWG do zero.

Use biblioteca/serviço compatível com licenciamento apropriado.

Criar abstraction layer:

`DocumentViewerProvider`

---

# FASE 34 — CAD 3D / MODELOS

Preparar suporte para:

* IFC
* STEP
* modelos 3D relevantes

Visualização WebGL quando possível.

Tratar como módulo independente.

Não deixar essa fase bloquear o restante.

---

# FASE 35 — COMPARAÇÃO DE REVISÕES

Implementar comparação.

Inicialmente:

metadata:

Rev B × Rev C

Depois:

PDF:

* páginas adicionadas/removidas
* texto alterado

Posteriormente:

CAD:

* comparação gráfica se provider permitir

---

# FASE 36 — ASSINATURA ELETRÔNICA

Criar assinatura interna inicialmente.

Registrar:

* signatário
* documento
* revisão
* timestamp
* checksum
* IP

Preparar provider interface para:

* ICP-Brasil
* Clicksign
* DocuSign
* outros

Não implementar assinatura com alegação de validade jurídica sem provider adequado.

---

# FASE 37 — CONTROLE DE CÓPIA

Permitir:

* documento controlado
* documento não controlado

Downloads opcionais podem gerar watermark:

“CÓPIA NÃO CONTROLADA”

com:

* usuário
* data
* revisão

---

# FASE 38 — DOCUMENTOS OBSOLETOS

Adicionar ciclo:

* vigente
* substituído
* obsoleto
* cancelado

Documento obsoleto permanece disponível conforme permissão, mas claramente identificado.

---

# FASE 39 — RETENÇÃO DOCUMENTAL

Criar política configurável:

* prazo de retenção
* classe documental
* destino após prazo

Não excluir automaticamente inicialmente.

Gerar pendência para administrador.

---

# FASE 40 — LIXEIRA E SOFT DELETE

Entidades importantes não devem desaparecer imediatamente.

Adicionar:

* deleted_at
* deleted_by

Criar lixeira administrativa.

Auditar restauração.

---

# FASE 41 — DASHBOARD OPERACIONAL

Criar dashboard.

Cards:

* documentos ativos
* em aprovação
* aprovados
* rejeitados
* atrasados
* vencendo
* novas revisões
* tarefas minhas

Gráficos:

* por disciplina
* por projeto
* por status
* por fornecedor
* por responsável

---

# FASE 42 — DASHBOARD DE ENGENHARIA

Indicadores:

* avanço documental
* planejado × realizado
* documentos atrasados
* atraso médio
* revisão média
* turnaround
* backlog
* aprovação na primeira submissão

---

# FASE 43 — DASHBOARD DE FORNECEDORES

Indicadores:

* documentos entregues
* documentos atrasados
* taxa de reprovação
* tempo médio de resposta
* quantidade de revisões
* comentários pendentes

Não transformar esses números automaticamente em julgamento subjetivo do fornecedor.

---

# FASE 44 — RELATÓRIOS

Criar framework de relatórios.

Saídas:

* Excel
* CSV
* PDF

Relatórios iniciais:

* LD
* atraso
* workflow
* auditoria
* transmittals
* revisões
* documentos por disciplina
* fornecedor
* comentários

---

# FASE 45 — VIEWS SALVAS

Usuários poderão salvar:

* filtros
* ordenação
* colunas

Exemplo:

“Documentos mecânicos atrasados — Projeto X”

Criar:

`SavedView`

---

# FASE 46 — CUSTOMIZAÇÃO DE TELAS

Permitir que administrador configure:

* campos visíveis
* campos obrigatórios
* ordem
* seções
* labels

Baseado no tipo documental.

Esse é um primeiro passo para recursos low-code.

---

# FASE 47 — FORM BUILDER

Evoluir campos dinâmicos para criador visual de formulários.

Tipos:

* texto
* textarea
* número
* moeda
* data
* datetime
* select
* multiselect
* checkbox
* usuário
* grupo
* taxonomia
* documento relacionado

Permitir:

* obrigatório
* regex
* min/max
* valor padrão
* condição de visibilidade

---

# FASE 48 — REGRAS DE NEGÓCIO

Criar motor de regras simples.

Exemplo:

SE:
tipo == "Desenho"

ENTÃO:
disciplina obrigatório

SE:
valor X > Y

ENTÃO:
enviar para aprovação gerencial

Não usar `eval`.

Criar DSL ou estrutura JSON segura.

---

# FASE 49 — PROCESSOS ALÉM DE DOCUMENTOS

O BPM não deve ficar preso somente a documento.

Criar conceito:

`ProcessDefinition`

`ProcessInstance`

`ProcessTask`

Processos poderão ter:

* campos
* anexos
* workflow
* responsáveis

Isso permite usar Indoc para:

* qualidade
* contratos
* solicitações
* MOC
* não conformidade
* auditorias

---

# FASE 50 — RELACIONAMENTO ENTRE DOCUMENTOS

Criar:

`DocumentRelation`

Tipos:

* substitui
* complementa
* referência
* depende_de
* relacionado
* as-built_de

Permitir navegar graficamente.

---

# FASE 51 — TAGS DE EQUIPAMENTOS

Criar relacionamento:

Documento
↔
AssetTag

Exemplo:

P-101
→ datasheet
→ desenho
→ manual
→ relatório

Preparar Indoc para asset lifecycle.

---

# FASE 52 — DATABOOK

Criar conceito de pacote documental.

`DocumentPackage`

Exemplo:

Databook Bomba P-101

contendo:

* certificados
* desenhos
* manuais
* relatórios
* folha de dados

Permitir geração/exportação de pacote.

---

# FASE 53 — HANDOVER / AS-BUILT

Criar fechamento documental de projeto.

Definir requisitos:

* documentos obrigatórios
* revisão final
* status
* pendências

Gerar pacote de entrega.

---

# FASE 54 — API CORPORATIVA

Organizar APIs sob:

`/api/v1/`

Criar versionamento.

Gerar OpenAPI correto.

Adicionar:

* pagination consistente
* filtering
* sorting
* correlation/request id
* errors padronizados

---

# FASE 55 — WEBHOOKS

Criar webhooks configuráveis.

Eventos:

* documento_criado
* revisao_criada
* aprovado
* reprovado
* grd_emitida
* tarefa_criada

Segurança:

* assinatura HMAC
* retry
* logs
* dead-letter

---

# FASE 56 — INTEGRAÇÕES

Criar arquitetura:

`IntegrationProvider`

Preparar providers para:

* SAP
* SAP PM
* ERP
* CRM
* Teams
* SharePoint
* email

Não misturar lógica de integração com models centrais.

---

# FASE 57 — IMPORTAÇÃO EM MASSA

Criar importador.

Aceitar:

* CSV
* XLSX
* ZIP

Permitir mapear colunas.

Pré-visualizar antes de executar.

Validar erros linha a linha.

Executar em background.

---

# FASE 58 — EXPORTAÇÃO EM MASSA

Usuário autorizado poderá exportar:

* seleção
* projeto
* LD
* package

Gerar ZIP de forma assíncrona.

Registrar auditoria.

---

# FASE 59 — STORAGE ABSTRACTION

O sistema hoje usa `UPLOAD_DIR`.

Criar:

`StorageProvider`

Implementações:

* LocalStorageProvider
* S3Provider

Preparar para:

* AWS S3
* MinIO
* Azure Blob

Não alterar o restante da aplicação quando provider mudar.

---

# FASE 60 — ANTIVÍRUS

Criar pipeline opcional de malware scanning.

Provider inicial possível:

ClamAV.

Status:

* pending
* clean
* infected
* error

Documento infectado não pode ficar disponível.

---

# FASE 61 — PROCESSAMENTO ASSÍNCRONO ROBUSTO

Evoluir Celery.

Separar queues:

* upload
* OCR
* index
* preview
* report
* notification
* AI

Adicionar:

* retry
* exponential backoff
* timeout
* idempotência
* dead-letter handling

Preparar worker para múltiplos processos em produção.

---

# FASE 62 — OBSERVABILIDADE

Adicionar:

* structured logging
* request id
* job id
* métricas
* health check
* readiness
* worker health

Endpoints:

`/health`
`/ready`

Preparar integração com:

* Prometheus
* Grafana
* Sentry/OpenTelemetry

---

# FASE 63 — PERFORMANCE

Implementar:

* índices SQL
* análise de queries
* eager/select loading onde necessário
* paginação
* caching seletivo
* Redis

Evitar N+1.

Criar testes com volume simulado.

Meta arquitetural:

centenas de milhares de documentos sem degradação estrutural.

---

# FASE 64 — FRONTEND MODULAR

Corrigir pendências atuais.

Quebrar `index.css` monolítico.

Adotar:

* CSS Modules
  ou equivalente adequado.

Fazer:

* lazy loading
* code splitting
* chunks por rota

Reduzir bundle inicial.

---

# FASE 65 — DESIGN SYSTEM

Criar componentes consistentes:

* Button
* Input
* Select
* Modal
* Drawer
* Table
* Badge
* Tabs
* Dropdown
* Tooltip
* Toast
* Breadcrumb
* Pagination
* EmptyState
* Skeleton
* FilePreview

Manter identidade própria do Indoc.

Visual corporativo moderno, limpo e responsivo.

---

# FASE 66 — TABELAS CORPORATIVAS

Criar tabela avançada reutilizável.

Recursos:

* sorting
* filtering
* resizing
* reorder
* hide/show columns
* pin
* pagination
* bulk select
* export

Reutilizar em LD, documentos, tarefas, usuários etc.

---

# FASE 67 — TESTES FRONTEND

Adicionar:

* Vitest
* Testing Library

Testar componentes e fluxos críticos.

Posteriormente:

* Playwright

Fluxos E2E:

login
→ upload
→ workflow
→ aprovação
→ revisão
→ download

---

# FASE 68 — SEGURANÇA

Fazer hardening completo.

Adicionar:

* rate limiting
* CSP
* HSTS em produção
* secure cookies
* CSRF
* sanitização
* validação MIME real
* upload limit
* filename normalization
* SQL injection prevention
* XSS prevention
* brute force protection

Manter todas as proteções existentes contra path traversal.

---

# FASE 69 — LGPD E GOVERNANÇA

Criar capacidades administrativas para:

* rastreamento de acesso
* exportação de dados do usuário quando aplicável
* anonimização quando aplicável
* retenção
* consentimento quando necessário
* logs de tratamento

Não afirmar conformidade jurídica automaticamente.

A plataforma deve fornecer ferramentas técnicas para suportá-la.

---

# FASE 70 — MULTI-TENANCY OPCIONAL

Preparar arquitetura para múltiplas organizações.

`Organization`

Todos os recursos deverão possuir escopo organizacional quando multi-tenancy for ativado.

Não é necessário habilitar imediatamente.

Evite arquitetar algo que impossibilite isso no futuro.

---

# FASE 71 — IA DOCUMENTAL / INDOC AI

Somente após GED e governança estarem sólidos.

Criar serviço independente:

`AIService`

Nunca colocar chamadas ao LLM diretamente nos routers.

---

# FASE 72 — RAG

Pipeline:

Documento
→ extração
→ chunking
→ embedding
→ vector DB
→ retrieval
→ LLM

Avaliar:

* pgvector, se PostgreSQL for introduzido futuramente
* Qdrant
* LanceDB
* outra solução justificável

O MySQL atual não precisa ser substituído apenas por causa do RAG.

---

# FASE 73 — IA COM ACL

REQUISITO ABSOLUTO:

A IA nunca poderá recuperar informações que o usuário não possui permissão para acessar.

Fluxo:

User
→ PermissionService
→ Retrieval filter
→ vector search
→ authorized chunks
→ LLM

ACL deve ser aplicada ANTES da resposta.

---

# FASE 74 — CHAT COM DOCUMENTOS

Permitir perguntas como:

“Qual é a revisão atual do documento X?”

“Resuma este memorial.”

“Quais documentos citam P-101?”

Mostrar sempre fontes:

* documento
* revisão
* página quando possível

Não responder factualidade documental sem referência recuperada.

---

# FASE 75 — IA SOBRE DADOS ESTRUTURADOS

Além de RAG, permitir consultas como:

“Quantos documentos mecânicos estão atrasados?”

“Quais fornecedores possuem comentários abertos?”

“Quais documentos aguardam aprovação há mais de 7 dias?”

Nessas perguntas, consultar banco estruturado, e não embeddings.

Criar tools internas seguras.

---

# FASE 76 — COMPARAÇÃO DE REVISÕES COM IA

Permitir:

“Resuma o que mudou da revisão B para C.”

Entrada:

* texto Rev B
* texto Rev C

Saída:

* itens adicionados
* removidos
* alterados

Sempre fornecer referência.

---

# FASE 77 — EXTRAÇÃO DE METADADOS COM IA

Durante upload, IA pode sugerir:

* título
* disciplina
* tipo
* tags
* equipamento
* fornecedor

Nunca gravar automaticamente campos importantes sem confirmação, salvo regra explicitamente habilitada.

---

# FASE 78 — CLASSIFICAÇÃO AUTOMÁTICA

Criar classificação assistida.

Documento:
→ extração
→ modelo
→ sugestão

Mostrar confiança.

Usuário confirma.

Registrar sugestão e decisão para auditoria.

---

# FASE 79 — INDICADORES COM IA

Permitir linguagem natural:

“Mostre atraso documental do Projeto X por disciplina.”

IA converte pergunta em chamada a ferramentas internas autorizadas.

Nunca permitir SQL arbitrário produzido pelo LLM contra produção.

---

# FASE 80 — ADMINISTRAÇÃO LOW-CODE

Criar painel onde administradores possam configurar:

* taxonomias
* tipos de documento
* formulários
* campos
* workflows
* SLAs
* notificações
* regras
* dashboards
* permissões

A meta é reduzir dependência de alterações no código para adaptar Indoc a novos projetos.

---

# FASE 81 — TEMPLATES DE PROJETO

Permitir criar templates.

Exemplo:

Template “Projeto EPC”

já cria:

* disciplinas
* tipos documentais
* workflow
* perfis
* campos
* SLA
* LD

Criar projeto novo clonando template.

---

# FASE 82 — VERSIONAMENTO DE CONFIGURAÇÃO

Configurações críticas também precisam de versão.

Exemplo:

Workflow v1
Workflow v2

Instâncias antigas continuam vinculadas à configuração utilizada originalmente.

Nunca alterar retroativamente histórico.

---

# FASE 83 — IMPORTAÇÃO/MIGRAÇÃO DE SISTEMAS ANTIGOS

Criar ferramentas para migração.

Mapear:

source
→ Indoc

Suportar:

* código
* metadata
* revisão
* datas
* arquivos
* status

Criar relatório de inconsistências.

---

# FASE 84 — BI

Criar camada de dados adequada para BI.

Permitir integração segura e read-only com:

* Power BI
* Metabase
* Grafana
* ferramentas equivalentes

Não expor banco operacional inteiro sem controle.

Criar views específicas para analytics.

---

# FASE 85 — KPIs

Criar biblioteca de indicadores:

* turnaround time
* atraso médio
* documentos por status
* approval cycle
* first-pass approval
* revisões por documento
* backlog
* SLA compliance
* avanço planejado × realizado

Indicadores devem permitir filtro temporal.

---

# FASE 86 — ACESSIBILIDADE

Frontend deverá seguir boas práticas WCAG.

Implementar:

* teclado
* focus
* labels
* ARIA
* contraste
* leitor de tela

---

# FASE 87 — RESPONSIVIDADE

Sistema deverá funcionar adequadamente em:

* desktop
* notebook
* tablet

Mobile deverá permitir ao menos:

* consulta
* aprovação
* comentário
* tarefas
* download/preview

---

# FASE 88 — PWA

Avaliar PWA.

Permitir:

* instalação
* notificações
* shell offline

Não permitir edição conflitante offline de documentos sem estratégia de sincronização.

---

# FASE 89 — DOCUMENTAÇÃO

Manter documentação atualizada.

Criar:

`docs/architecture.md`

`docs/database.md`

`docs/auth.md`

`docs/permissions.md`

`docs/workflow.md`

`docs/edms.md`

`docs/transmittals.md`

`docs/search.md`

`docs/ai.md`

`docs/deployment.md`

---

# FASE 90 — ADRs

Para decisões importantes, criar:

`docs/adr/`

Architecture Decision Records.

Exemplos:

* storage escolhido
* search engine
* ACL
* vector database
* auth
* workflow engine

---

# FASE 91 — SEEDS DE DEMONSTRAÇÃO

Criar ambiente demo.

Empresa fictícia.

Projeto fictício.

Disciplinas.

Documentos.

Revisões.

Workflow.

Fornecedores.

GRDs.

Nunca usar dados reais/confidenciais.

---

# FASE 92 — TESTE DE CARGA

Criar cenário artificial de:

* 100 mil documentos
* 500 mil revisões
* milhões de eventos de auditoria

Avaliar:

* busca
* listagem
* dashboard
* upload
* ACL

Não precisa armazenar arquivos gigantes reais.

---

# FASE 93 — BACKUP E RECUPERAÇÃO

Documentar e automatizar estratégia para:

* MySQL
* Redis quando necessário
* storage
* OpenSearch
* vector DB

Definir source of truth.

Testar restauração.

---

# FASE 94 — RECUPERAÇÃO DE DESASTRE

Documentar:

* RPO
* RTO
* recuperação
* redundância
* verificação de backups

Não criar falsa alta disponibilidade apenas no papel.

---

# FASE 95 — ADMIN HEALTH DASHBOARD

Administradores deverão visualizar:

* API
* banco
* Redis
* Celery
* filas
* storage
* search
* OCR
* IA

Mostrar erros recentes e backlog.

---

# FASE 96 — FEATURE FLAGS

Criar sistema de feature flags.

Permitir habilitar gradualmente:

* OCR
* IA
* CAD
* supplier portal
* assinatura

---

# FASE 97 — LICENCIAMENTO DE DEPENDÊNCIAS

Antes de adicionar biblioteca:

* verificar licença
* evitar dependências incompatíveis comercialmente
* registrar decisão quando relevante

Especial atenção:

* CAD
* OCR
* conversores Office
* assinatura

---

# FASE 98 — CRITÉRIO FINAL DE PARIDADE FUNCIONAL

Ao concluir, elaborar matriz:

| Capacidade            | Indoc        | Status   |
| --------------------- | ------------ | -------- |
| GED                   | sim          | completo |
| ECM                   | sim          | completo |
| BPM                   | sim          | completo |
| Workflow configurável | sim          | completo |
| Versionamento         | sim          | completo |
| Metadata dinâmica     | sim          | completo |
| Taxonomia             | sim          | completo |
| ACL                   | sim          | completo |
| Auditoria             | sim          | completo |
| Busca full-text       | sim          | completo |
| OCR                   | sim          | completo |
| LD                    | sim          | completo |
| GRD/Transmittal       | sim          | completo |
| Fornecedores          | sim          | completo |
| SLA                   | sim          | completo |
| Comentários           | sim          | completo |
| Assinatura            | sim/provider | completo |
| CAD                   | sim/provider | completo |
| Dashboards            | sim          | completo |
| BI                    | sim          | completo |
| Integrações           | sim          | completo |
| Low-code              | sim          | completo |
| IA documental         | sim          | completo |
| RAG                   | sim          | completo |
| Asset lifecycle       | sim          | completo |

Para cada linha, indicar:

* implementado
* parcialmente implementado
* não implementado
* dependência externa
* testes
* documentação

---

# FASE 99 — NÃO CRIAR MONÓLITO DESORGANIZADO

À medida que crescer:

não coloque tudo em:

`models.py`

`schemas.py`

`utils.py`

Refatore gradualmente para estrutura modular.

Exemplo:

backend/
core/
auth/
users/
organizations/
permissions/
documents/
revisions/
workflows/
comments/
transmittals/
search/
notifications/
reports/
integrations/
storage/
audit/
ai/

Cada módulo pode possuir:

* models
* schemas
* service
* repository
* router
* permissions
* tests

Faça a migração gradualmente para não quebrar imports.

---

# FASE 100 — REGRA DE QUALIDADE

Ao final de CADA fase:

Execute:

* Ruff
* pytest
* Alembic check
* frontend build
* frontend tests

Se existir Playwright:

* E2E crítico

Não avance com testes quebrados.

---

# ORDEM REAL DE PRIORIDADE

Apesar de a lista ser extensa, implemente nesta sequência macro:

## P0 — GOVERNANÇA

1. ACL
2. autenticação
3. auditoria
4. modelo documental
5. revisão
6. segurança

## P1 — EDMS

7. workflow avançado
8. tarefas
9. SLA
10. comentários
11. LD
12. GRD
13. fornecedores
14. clientes

## P2 — INFORMAÇÃO

15. taxonomia
16. pesquisa
17. full-text
18. OCR
19. preview
20. revisão/comparação

## P3 — GESTÃO

21. dashboards
22. indicadores
23. relatórios
24. BI
25. planejamento documental

## P4 — PLATAFORMA

26. low-code
27. formulários
28. BPM genérico
29. integrações
30. webhooks

## P5 — ENGENHARIA AVANÇADA

31. CAD
32. asset tags
33. databooks
34. handover
35. as-built

## P6 — IA

36. RAG
37. chat
38. consulta estruturada
39. classificação
40. comparação de revisões

---

# IMPORTANTE SOBRE ESCOPO

Não tente gerar as 100 fases numa única alteração.

Antes de iniciar cada macrofase:

1. faça diagnóstico;
2. apresente plano técnico curto;
3. implemente;
4. teste;
5. documente;
6. continue.

Caso encontre algo que já existe no Indoc:

NÃO duplique.

Avalie e evolua.

Caso encontre uma implementação melhor que a sugerida neste prompt:

pode utilizá-la, desde que explique a decisão.

---

# REQUISITO DE COMPATIBILIDADE

Não quebrar dados existentes.

Migrations deverão ser compatíveis com bancos já existentes.

Para campos novos obrigatórios:

1. criar nullable ou default;
2. migrar dados;
3. somente depois restringir.

Evitar migrations destrutivas.

---

# REQUISITO DE SEGURANÇA

Nenhuma nova funcionalidade deve contornar:

* ACL
* auditoria
* autenticação
* validação

Especialmente:

Busca
IA
exportação
preview
download
relatórios
BI

Todos devem aplicar autorização.

---

# RESULTADO FINAL ESPERADO

O Indoc deverá deixar de ser somente:

“um GED com workflow”

e se tornar:

**uma plataforma corporativa completa de governança da informação e controle documental de engenharia, combinando GED, EDMS, ECM e BPM, com workflows configuráveis, gestão completa do ciclo de vida documental, colaboração interna e externa, rastreabilidade, busca avançada, automação, BI, integrações e IA.**

Sua arquitetura deverá permitir que:

Engenharia
↕
Fornecedores
↕
Controle Documental
↕
Cliente
↕
Operação/Manutenção

trabalhem sobre uma única fonte documental confiável.

O ciclo deverá cobrir:

Planejamento
→ criação
→ submissão
→ revisão
→ comentários
→ aprovação
→ distribuição
→ construção
→ as-built
→ databook
→ handover
→ operação
→ retenção

Tudo com:

* revisão controlada
* segurança
* rastreabilidade
* histórico
* responsabilidades
* prazos
* evidências

---

# PRIMEIRA AÇÃO

NÃO comece programando imediatamente.

Primeiro:

1. leia todo o repositório;
2. compare o estado real com este roadmap;
3. marque cada item como:

   * existente;
   * parcial;
   * ausente;
4. identifique dependências entre fases;
5. produza `ROADMAP_EDMS.md`;
6. produza uma matriz de paridade funcional;
7. identifique dívidas técnicas que precisam ser resolvidas antes;
8. então inicie **P0 — Governança**, pela ACL.

Durante todo o trabalho:

* preserve funcionalidades existentes;
* escreva código modular;
* crie migrations;
* escreva testes;
* atualize documentação;
* não invente funcionalidades que já existam;
* não remova recursos sem justificativa;
* evite breaking changes;
* mantenha segurança como requisito transversal.

Só considere uma fase concluída quando backend, banco, frontend, autorização, testes e documentação estiverem coerentes.
