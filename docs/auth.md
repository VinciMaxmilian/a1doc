# Autenticação (FASE 2)

## O que mudou e por quê

Antes: um JWT de 8 horas, guardado em `localStorage`, era a única credencial.
Qualquer JavaScript que rodasse na página conseguia lê-lo — um único XSS
entregava a sessão inteira, e não havia como revogá-la antes do vencimento.

Agora:

| | Antes | Agora |
|---|---|---|
| Access token | 8h, em `localStorage` | 15 min, em cookie `HttpOnly` |
| Sessão longa | — | refresh token rotativo, 14 dias |
| Revogação | impossível | imediata, por sessão ou todas |
| Força bruta | sem proteção | bloqueio progressivo por usuário e por IP |
| Rastreio | — | `UserSession` com IP, dispositivo e uso |

## Os três cookies

| Cookie | HttpOnly | Path | Para quê |
|---|---|---|---|
| `indoc_access` | sim | `/` | autentica cada requisição |
| `indoc_refresh` | sim | `/auth` | renova o access; só trafega nas rotas que o usam |
| `indoc_csrf` | **não** | `/` | o front precisa ler para reenviar no header |

Todos com `Secure` e `SameSite` configuráveis. **`COOKIE_SECURE` é `true` por
padrão** — em dev sobre `http://localhost` o navegador descarta o cookie, então
defina `COOKIE_SECURE=false` no `.env` local.

## CSRF

Usar cookie significa que o navegador anexa a credencial sozinho, inclusive
numa requisição disparada por outro site. `SameSite=Lax` barra a maior parte,
mas não tudo.

Proteção por double-submit: o `indoc_csrf` é legível por JS de propósito, o
front o ecoa em `X-CSRF-Token`, e o servidor confere se batem.

Exigido apenas quando **as duas** condições valem:

1. a requisição se autenticou **por cookie**, e
2. o método **muda estado** (não é GET/HEAD/OPTIONS/TRACE).

Quem usa `Authorization: Bearer` não precisa — o navegador não injeta esse
header sozinho, então o ataque não existe ali.

## Por que o header Bearer continua aceito

O problema que a FASE 2 corrige não era o cabeçalho: era guardar a credencial
num lugar legível por script **dentro do navegador**. Clientes programáticos
(scripts, CI, integrações) precisam de um caminho sem cookie, e um script que
manda `Authorization` já obteve o token por outro meio.

Nos testes isso importa: o `TestClient` guarda cookies, então omitir o header
**não** simula um cliente anônimo. Use `sem_sessao(client)` do `conftest`.

## Rotação e detecção de reuso

Cada `/auth/refresh` gera um refresh novo e invalida o anterior. O token é
gravado só como SHA-256 (`UserSession.refresh_token_hash`) — vazamento do banco
não entrega sessões utilizáveis.

`previous_token_hash` guarda uma geração. Se o token anterior reaparecer, houve
cópia: o legítimo já rotacionou e alguém está usando o antigo. Como não dá para
saber qual das duas partes é a verdadeira, **todas as sessões do usuário são
revogadas** e o evento vai para a auditoria como `sessao_reuso_detectado`.

Limite honesto: a detecção cobre **uma** geração. Um token de várias rotações
atrás não é rastreável e cai como sessão inválida comum, sem alarme. Isso cobre
o ataque real (ladrão e dono disputando a próxima rotação); um histórico
completo exigiria uma tabela de tokens por sessão.

## Revogação imediata

O access token carrega `sid` (id da sessão). `get_current_user` confere se a
sessão continua viva — por isso encerrar uma sessão vale na hora, em vez de
esperar o access token expirar.

## Força bruta

Duas chaves independentes em `login_throttle`:

- `username` — impede adivinhar a senha de **uma** conta;
- `ip` — impede varrer **muitas** contas do mesmo lugar.

Basta uma bloqueada para recusar. Após `LOGIN_MAX_FALHAS` erros o bloqueio é de
`LOGIN_BLOQUEIO_BASE_SEGUNDOS` e **dobra a cada reincidência**, até o teto. A
contagem zera sozinha após `LOGIN_JANELA_FALHAS_MINUTOS` sem erro, e zera de
vez no primeiro login correto. A resposta é `429` com `Retry-After`.

Estado no banco, não em memória: precisa valer para todos os workers e
sobreviver a um restart.

Conta inativa ou bloqueada também conta falha — senão viraria alvo sem custo.
E o login de usuário inexistente verifica a senha contra um hash descartável,
para o tempo de resposta não revelar se a conta existe.

## Providers

```
AuthProvider (protocolo)
├── LocalPasswordProvider   bcrypt — o que já existia
├── FirebaseProvider        verifica ID token do Firebase
└── (futuro) OIDCProvider   LDAP / AD / Entra ID / SSO
```

Um provider responde **uma** pergunta: quem é este usuário? Ele não decide o
que a pessoa pode — isso é da ACL, e continua no MySQL.

### Firebase

Projeto `indoc-71c52`, com e-mail/senha e Google habilitados. Os dois métodos
emitem o mesmo tipo de ID token e são tratados igual.

**Não usamos o Firestore.** A decisão é Firebase só para identidade; MySQL
continua sendo o source of truth de todo o domínio.

**Não exige service account.** Verificar um ID token precisa só das chaves
públicas do Google (`FIREBASE_JWKS_URL`), conferindo `iss` e `aud` contra
`FIREBASE_PROJECT_ID`. O Admin SDK só seria necessário para operações
administrativas — criar usuário pelo servidor, custom claims, revogar refresh
do Firebase — e essas ficam do lado do Indoc.

Vínculo: `IdentidadeExterna(provider='firebase', subject=<uid>)`. No primeiro
login, liga ao usuário já cadastrado com o mesmo e-mail — **só se o e-mail
estiver verificado**. Sem essa condição, bastaria criar uma conta Firebase com
o e-mail de alguém para assumir a conta dela.

Quem não tem cadastro no Indoc é recusado. `FIREBASE_AUTO_PROVISIONAR=true`
muda isso e cria o usuário na hora, com o perfil padrão — útil num ambiente
aberto, perigoso num corporativo, por isso vem desligado.

Para ativar:

```env
FIREBASE_ENABLED=true
FIREBASE_PROJECT_ID=indoc-71c52
```

O front descobre o que oferecer em `GET /auth/providers`.

## API

```
GET    /auth/providers                formas de login disponíveis
POST   /auth/login                    usuário e senha
POST   /auth/login/firebase           troca ID token por sessão Indoc
POST   /auth/refresh                  renova e rotaciona
POST   /auth/logout                   encerra a sessão atual
GET    /auth/sessoes                  minhas sessões
DELETE /auth/sessoes/{id}             encerra uma
POST   /auth/sessoes/revogar-todas    encerra as outras, mantém a atual
POST   /auth/registrar                cria usuário (admin)
GET    /auth/me                       meu perfil
```

`/auth/refresh` e `/auth/logout` **não** exigem access token válido: precisam
funcionar justamente quando ele expirou.

`revogar-todas` mantém a sessão atual de propósito — quem acabou de trocar a
senha não deveria ser deslogado de onde está fazendo isso.

## Frontend

O `api.js` renova sozinho: o primeiro `401` dispara `/auth/refresh` e repete a
requisição. Chamadas concorrentes compartilham a **mesma** renovação — senão N
requisições simultâneas disparariam N refreshes, e o segundo derrubaria a
sessão, já que a rotação invalida o token anterior.

Tela **Minhas sessões** (`/sessoes`) mostra onde a conta está conectada e
permite encerrar.

## Configuração

| Variável | Padrão | Observação |
|---|---|---|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 15 | era 480 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 14 | |
| `COOKIE_SECURE` | `true` | **`false` em dev sobre http** |
| `COOKIE_SAMESITE` | `lax` | |
| `COOKIE_DOMAIN` | — | para subdomínios |
| `LOGIN_MAX_FALHAS` | 5 | |
| `LOGIN_BLOQUEIO_BASE_SEGUNDOS` | 60 | dobra a cada reincidência |
| `LOGIN_BLOQUEIO_MAX_SEGUNDOS` | 3600 | teto |
| `LOGIN_JANELA_FALHAS_MINUTOS` | 15 | |
| `TRUST_PROXY_HEADERS` | `false` | só ligue atrás de proxy real |
| `FIREBASE_ENABLED` | `false` | |
| `FIREBASE_PROJECT_ID` | — | |
| `FIREBASE_AUTO_PROVISIONAR` | `false` | |

`TRUST_PROXY_HEADERS` importa: com ele desligado, o IP vem da conexão. Ligado
sem proxy real na frente, qualquer cliente forja `X-Forwarded-For` e escapa do
bloqueio de força bruta.

## Compatibilidade

A migration `0004` não remove nada. Tokens JWT já emitidos continuam válidos
até expirarem — eles não têm `sid`, e `get_current_user` trata `sid` ausente
como sessão não rastreada em vez de recusar. Quem logar de novo passa a ter
sessão registrada.
