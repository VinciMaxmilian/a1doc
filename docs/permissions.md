# Permissões (FASE 1 — RBAC + ACL)

Como o Indoc decide quem pode o quê.

## Princípio

**Toda a política é dado, não código.** Existe um único caminho de avaliação —
`indoc/permissions/service.py` — e quem decide o que cada usuário pode são as
linhas das tabelas de permissão. Apertar ou afrouxar o acesso de uma instalação
não exige tocar no código.

Nenhum endpoint replica lógica de autorização. Quem precisa checar algo declara
uma dependência de `indoc/permissions/deps.py`.

## Os três eixos

| Eixo | Valores |
|---|---|
| **Sujeito** | `usuario`, `grupo`, `perfil` |
| **Recurso** | `global`, `ambiente`, `area`, `projeto`, `documento` |
| **Permissão** | `read`, `create`, `update`, `delete`, `download`, `upload`, `revise`, `comment`, `approve`, `reject`, `distribute`, `manage_permissions`, `manage_workflow`, `manage_metadata` |

O vocabulário aceito está em `GET /permissoes/catalogo` — a UI monta os selects
a partir dele em vez de duplicar as listas.

## Duas formas de conceder

**Perfil** é o caminho normal: um pacote nomeado de permissões (`Perfil` +
`PerfilPermissao`), atribuído a um usuário por `UsuarioPerfil`, opcionalmente
restrito a um recurso.

```
Fornecedor A recebe o perfil "fornecedor" NO projeto Ponte
-> pode ler/enviar dentro do projeto Ponte e nada fora dele
```

**ACL** (`ACLEntry`) é a exceção pontual: conceder ou negar UMA permissão a UM
sujeito sobre UM recurso. É o que permite "este fornecedor não vê este
documento" sem inventar um perfil novo.

## Ordem de resolução

O recurso é expandido para a cadeia de ancestrais:

```
global -> ambiente -> area -> projeto -> documento
```

A avaliação percorre **do mais específico para o mais amplo** e para no primeiro
nível que tenha alguma regra aplicável. Dentro de um nível:

1. negação explícita (`ACLEntry.allow=False`) → **negado**
2. concessão explícita (`ACLEntry.allow=True`) → **permitido**
3. perfil atribuído nesse escopo que concede → **permitido**
4. nada → sobe um nível

Esgotada a cadeia sem regra alguma: **negado** (default deny).

Consequências:

- o mais específico sobrescreve o herdado — um `deny` no documento derruba um
  `allow` no projeto, e um `allow` no documento fura um `deny` no projeto;
- dentro do mesmo nível, negar vence conceder;
- uma negação explícita vence o perfil no mesmo nível.

### Exemplo

```
ambiente Engenharia   : grupo Mecânica  allow read
projeto  Ponte        : grupo Mecânica  deny  read
documento MEM-001     : usuário ana     allow read
```

Ana, do grupo Mecânica:
- lê documentos de outros projetos do ambiente (herda do ambiente);
- não lê o projeto Ponte (deny mais específico);
- lê o MEM-001 mesmo estando na Ponte (allow ainda mais específico).

## Admin/dev

`role in ("admin", "dev")` passa por tudo, sem consultar a ACL. É uma válvula de
segurança deliberada: um erro de configuração não pode deixar a instalação sem
ninguém capaz de consertá-la.

## Compatibilidade — leia antes de apertar o acesso

A ACL é default-deny. Aplicada crua num banco existente, trancaria todos os
usuários para fora de todos os documentos.

Por isso a migration `0003` **semeia o acesso que já existia**:

| Papel legado | Perfil recebido (escopo global) |
|---|---|
| `admin`, `dev` | `administrador` (`*`) |
| `user` | `usuario_padrao` |

`usuario_padrao` concede exatamente o que qualquer usuário autenticado já podia
fazer antes da FASE 1: `read`, `create`, `upload`, `download`, `revise`,
`approve`, `reject`. O que era restrito a admin (`manage_metadata`,
`manage_workflow`, `manage_permissions`) continua restrito.

**Ninguém ganha nem perde acesso ao aplicar a migration.**

### Como fechar o acesso amplo

A visibilidade irrestrita de documentos (a dívida D1 do roadmap) deixou de ser
comportamento embutido e virou uma linha de dados removível:

1. remova a atribuição global de `usuario_padrao` dos usuários
   (`DELETE /permissoes/usuarios/{id}/perfis/{atribuicao_id}`);
2. atribua perfis com escopo por projeto, ou conceda ACL por recurso.

A partir daí a listagem, o detalhe e o download passam a mostrar só o que cada
um pode. O filtro da listagem é aplicado na query (`_somente_legiveis`), não na
serialização — um documento sem permissão nunca chega a ser carregado.

## Quem administra o quê

| Operação | Exigência |
|---|---|
| Criar/editar grupos e perfis, atribuir perfis | admin/dev |
| Conceder/negar ACL sobre um recurso | `manage_permissions` **naquele recurso** |
| Configurar workflow | `manage_workflow` |
| Tipos de documento e campos do formulário | `manage_metadata` |
| Valores de campo de um documento | `manage_metadata` **no documento** |
| Criar/excluir Ambiente/Área/Projeto | admin/dev (ver nota) |

**Nota sobre a hierarquia:** a lista de permissões da FASE 1 não tem uma que
signifique "administrar a estrutura da hierarquia". Reaproveitar `create` seria
errado — `create` é concedida a todo usuário para criar documentos, então usá-la
ali deixaria qualquer um criar ambientes. A permissão específica chega com o
painel low-code da FASE 80; até lá a checagem `require_admin` existente é a
correta e não foi afrouxada.

A separação entre administrar perfis (admin) e conceder ACL
(`manage_permissions` no recurso) é deliberada: o coordenador de um projeto
distribui acesso dentro dele sem virar administrador do sistema.

## Decisões de projeto

### Não existe coluna `inherited`

O roadmap sugere um campo `inherited` na ACL. Materializar as linhas herdadas
exigiria reescrever todos os descendentes a cada mudança e conviver com o risco
de ficarem dessincronizadas. Aqui a herança é **calculada na resolução**: existe
linha só onde alguém de fato concedeu ou negou algo. O efeito observável é o
mesmo e não há estado derivado para corromper.

### `role` continua existindo

O campo legado sobrevive por dois motivos: `Atividade.role_requerido` ainda o usa
como restrição de workflow, e ele é o que a migration traduz em perfis. A FASE 11
(responsáveis e matriz de distribuição) deve aposentá-lo.

Enquanto isso, ACL e workflow são checagens **independentes e cumulativas** em
documentos: a ACL responde "pode aprovar documentos deste projeto?", o
`role_requerido` responde "a bola está com você agora?". Ambas precisam passar.

## Desempenho

`PermissionService` vive por requisição e carrega sujeitos, perfis e linhas de
ACL de uma vez só; as cadeias de herança são memorizadas. Verificar 200
documentos não dispara 200 queries.

A listagem resolve o escopo em duas consultas (`projetos_legiveis` e
`documentos_com_regra_propria`) e aplica o resultado como filtro SQL. Com muitos
projetos isso vira um `IN` grande — a FASE 63 (performance) deve trocar por um
`EXISTS` correlacionado quando o volume justificar.

## API

```
GET    /permissoes/catalogo                       vocabulário aceito
GET    /permissoes/efetivas                       o que EU posso num recurso
GET    /permissoes/efetivas/{usuario_id}          o que OUTRO pode (admin)

GET    /permissoes/grupos                         CRUD de grupos
POST   /permissoes/grupos
PUT    /permissoes/grupos/{id}
DELETE /permissoes/grupos/{id}
GET    /permissoes/grupos/{id}/membros
POST   /permissoes/grupos/{id}/membros/{usuario_id}
DELETE /permissoes/grupos/{id}/membros/{usuario_id}

GET    /permissoes/perfis                         CRUD de perfis
POST   /permissoes/perfis
PUT    /permissoes/perfis/{id}
DELETE /permissoes/perfis/{id}

GET    /permissoes/usuarios/{id}/perfis           atribuições
POST   /permissoes/usuarios/{id}/perfis
DELETE /permissoes/usuarios/{id}/perfis/{atribuicao_id}

GET    /permissoes/acl?resource_type=&resource_id= regras de um recurso
POST   /permissoes/acl                             conceder ou negar
DELETE /permissoes/acl/{id}
```

`GET /permissoes/efetivas/{usuario_id}` é a ferramenta de suporte: responde
"por que fulano não consegue abrir isso?" sem precisar entrar no banco.

## Tela

**Administração → Permissões** (`/admin/permissoes`), com três abas: Grupos,
Perfis e Permissões por recurso.
