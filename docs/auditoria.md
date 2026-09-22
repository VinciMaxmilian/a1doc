# Auditoria (FASE 3)

Registro **append-only** de quem fez o quê, quando e de onde.

## Garantia de imutabilidade

Não existe endpoint de `PUT`, `PATCH` ou `DELETE` em `/auditoria` — a ausência
é a garantia. Vale inclusive para administradores: a API não oferece caminho
para alterar o log. Um teste verifica que esses verbos respondem `405`.

`AuditLog` **não tem FK** em `user_id`, `project_id` e `document_id`. É
deliberado: o registro precisa sobreviver à exclusão da entidade que descreve.
Um "documento X excluído" que some junto com o documento não serve para nada.
Pelo mesmo motivo o `username` é congelado na linha, não resolvido por join.

## O que é registrado

| Grupo | Ações |
|---|---|
| Autenticação | `login`, `logout`, `login_invalido`, `login_bloqueado`, `sessao_revogada`, `sessao_reuso_detectado` |
| Entidades | `criacao`, `edicao`, `exclusao` |
| Documentos | `visualizacao`, `download`, `upload`, `revisao`, `alteracao_metadata`, `aprovacao`, `reprovacao`, `transicao` |
| Governança | `alteracao_permissao`, `alteracao_workflow` |
| Reservadas | `comentario` (F16), `grd` (F23), `assinatura` (F36), `exportacao` (F58) |

As reservadas já existem no enum para que a tela de filtros e os relatórios não
precisem mudar quando as fases correspondentes chegarem.

## Campos

Além de ação e entidade, cada registro guarda `user_id`, `username`,
`session_id`, `ip`, `user_agent`, `request_id`, e os JSON `before`, `after` e
`metadata`.

`project_id` e `document_id` são **desnormalizados** de propósito: a consulta
quase sempre pergunta "o que aconteceu neste projeto / neste documento", e
reconstruir isso por `entity_type`/`entity_id` exigiria um join diferente por
tipo de entidade.

`request_id` vem do `RequestIdMiddleware` e amarra o evento à requisição — e
aos logs da aplicação, que carregam o mesmo id.

## Registro explícito, não middleware

Um middleware sabe o método e a rota, mas não sabe **o que mudou**. Os campos
`before`/`after` exigem conhecimento do domínio, e "houve um PUT em
/documentos/7" não responde à pergunta que a auditoria existe para responder.

O que é automático é o **contexto** (IP, user-agent, request_id), via
`ContextVar` — assim o registro não precisa receber o `Request` em cada camada.

```python
registrar(
    db, Action.ALTERACAO_METADATA, user=perms.user,
    entity_type="documento", entity_id=doc.id,
    project_id=doc.projeto_id, document_id=doc.id,
    before=antes, after=depois,
)
```

## Robustez

**Falha de auditoria não derruba a operação.** Se gravar o log falhar, a
operação de negócio já feita não é desfeita — o erro vai para o log da
aplicação. Falhar a requisição tornaria a auditoria um ponto único de
indisponibilidade do sistema inteiro. A FASE 62 deve alarmar sobre esses erros.

O `rollback` no caminho de erro só acontece quando `registrar` é dono da
transação (`commit=True`). Com `commit=False` quem manda é o chamador —
desfazer a transação dele ali apagaria silenciosamente a operação de negócio.

**Segredos nunca entram.** `password`, `token`, `hashed_password`,
`id_token` e afins são substituídos por `***`, recursivamente, antes de
serializar.

**Nenhum payload custa um registro.** O sanitizador detecta ciclos e limita a
profundidade; valores exóticos caem em `default=str`; o que o JSON recusa de
vez vira um marcador. O evento é gravado de qualquer jeito.

## Consulta

Restrita a admin/dev. A auditoria mostra acessos de toda a instalação,
inclusive de projetos que o consultante não pode ver — filtrar por ACL daria
uma visão inconsistente e vazaria a existência de documentos pelo próprio
registro. Uma visão por projeto deve vir com os portais (FASES 26/27).

```
GET /auditoria/catalogo    ações registráveis
GET /auditoria             lista paginada, mais recente primeiro
GET /auditoria/{id}        detalhe, com os JSON já decodificados
```

Filtros: `user_id`, `action`, `entity_type`, `entity_id`, `project_id`,
`document_id`, `ip`, `request_id`, `de`, `ate`.

Tela em **Administração → Auditoria** (`/admin/auditoria`).

## Retenção

Não há expurgo automático. A FASE 39 (retenção documental) deve definir a
política; até lá o log cresce indefinidamente, o que é o comportamento seguro.
`limpar_sessoes_expiradas` remove **sessões** vencidas há mais de 30 dias, não
registros de auditoria.
