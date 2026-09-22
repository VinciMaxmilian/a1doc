"""FASE 3 — auditoria completa."""
import json

from conftest import auth, criar_usuario, enviar_documento, sem_sessao, token_de

import config
from indoc.audit.actions import Action
from indoc.audit.models import AuditLog
from indoc.audit.service import registrar, snapshot
from indoc.core.middleware import HEADER


def conteudo(bruto):
    """Decodifica uma coluna *_json do ORM.

    `before`/`after` só existem no schema de saída (AuditLogOut); no model são
    as colunas de texto.
    """
    return json.loads(bruto) if bruto else None


def logs(db, action=None, **filtros):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == str(action))
    for campo, valor in filtros.items():
        q = q.filter(getattr(AuditLog, campo) == valor)
    return q.order_by(AuditLog.id).all()


def login(client, username="comum1", senha="senha-forte-123"):
    client.cookies.clear()
    r = client.post("/auth/login", data={"username": username, "password": senha})
    assert r.status_code == 200, r.text
    return r


# ────────────────────────── autenticação ──────────────────────────

def test_login_e_registrado(client, comum, db):
    login(client)
    registros = logs(db, Action.LOGIN)
    assert len(registros) == 1
    assert registros[0].username == "comum1"
    assert registros[0].user_id == comum.id
    assert registros[0].session_id is not None


def test_login_invalido_e_registrado(client, comum, db):
    client.cookies.clear()
    client.post("/auth/login", data={"username": "comum1", "password": "errada"})
    registros = logs(db, Action.LOGIN_INVALIDO)
    assert len(registros) == 1
    assert registros[0].user_id is None  # falhou antes de identificar


def test_senha_nunca_aparece_na_auditoria(client, comum, db):
    client.cookies.clear()
    client.post("/auth/login", data={"username": "comum1", "password": "segredo-literal"})
    for registro in logs(db):
        bruto = " ".join(filter(None, [
            registro.before_json, registro.after_json, registro.metadata_json
        ]))
        assert "segredo-literal" not in bruto


def test_logout_e_registrado(client, comum, db):
    r = login(client)
    client.post("/auth/logout", headers={config.HEADER_CSRF: r.json()["csrf_token"]})
    assert len(logs(db, Action.LOGOUT)) == 1


def test_bloqueio_por_forca_bruta_e_registrado(client, comum, db, monkeypatch):
    monkeypatch.setattr(config, "LOGIN_MAX_FALHAS", 2)
    client.cookies.clear()
    for _ in range(3):
        client.post("/auth/login", data={"username": "comum1", "password": "errada"})
    assert len(logs(db, Action.LOGIN_BLOQUEADO)) >= 1


# ────────────────────────── documentos ──────────────────────────

def test_upload_e_registrado(client, h_comum, hierarquia, fluxo_inicial, db):
    enviar_documento(client, h_comum, hierarquia, nome="Auditado")
    registros = logs(db, Action.UPLOAD)
    assert len(registros) == 1
    assert registros[0].project_id == hierarquia["projeto_id"]


def test_visualizacao_e_registrada(client, h_comum, documento, db):
    client.get(f"/documentos/{documento['id']}", headers=h_comum)
    registros = logs(db, Action.VISUALIZACAO, document_id=documento["id"])
    assert len(registros) >= 1


def test_download_e_registrado(client, h_comum, documento, db):
    arq_id = documento["arquivos"][0]["id"]
    client.get(f"/documentos/arquivos/{arq_id}/download", headers=h_comum)
    registros = logs(db, Action.DOWNLOAD)
    assert len(registros) == 1
    assert registros[0].document_id == documento["id"]
    assert registros[0].entity_id == arq_id


def test_revisao_e_registrada(client, h_comum, documento, db):
    client.post(f"/documentos/{documento['id']}/upload-revisao", headers=h_comum,
                files={"arquivo": ("v2.pdf", b"v2", "application/pdf")})
    assert len(logs(db, Action.REVISAO, document_id=documento["id"])) == 1


def test_alteracao_de_metadata_guarda_antes_e_depois(client, h_admin, documento, hierarquia, db):
    campo = client.post(
        f"/hierarquia/tipos-documento/{hierarquia['tipo_documento_id']}/campos",
        json={"nome": "Autor", "tipo": "text"}, headers=h_admin,
    ).json()

    client.put(f"/documentos/{documento['id']}/campos", headers=h_admin,
               json={"valores": [{"campo_id": campo["id"], "valor": "Ana"}]})
    client.put(f"/documentos/{documento['id']}/campos", headers=h_admin,
               json={"valores": [{"campo_id": campo["id"], "valor": "Bia"}]})

    registros = logs(db, Action.ALTERACAO_METADATA)
    assert len(registros) == 2
    assert conteudo(registros[1].before_json) == {str(campo["id"]): "Ana"}
    assert conteudo(registros[1].after_json) == {str(campo["id"]): "Bia"}


def test_aprovacao_registra_a_transicao(client, h_comum, documento, fluxo_inicial, db):
    client.post(f"/documentos/{documento['id']}/transitar", headers=h_comum,
                json={"acao": "aprovado", "observacao": "ok"})
    registros = logs(db, Action.APROVACAO)
    assert len(registros) == 1
    assert conteudo(registros[0].before_json)["atividade_atual_id"] == fluxo_inicial["elaboracao_id"]
    assert conteudo(registros[0].after_json)["atividade_atual_id"] == fluxo_inicial["aprovacao_id"]


# ────────────────────────── permissões ──────────────────────────

def test_concessao_de_acl_e_registrada(client, h_admin, hierarquia, comum, db):
    client.post("/permissoes/acl", headers=h_admin, json={
        "subject_type": "usuario", "subject_id": comum.id,
        "resource_type": "projeto", "resource_id": hierarquia["projeto_id"],
        "permission": "read", "allow": True,
    })
    registros = logs(db, Action.ALTERACAO_PERMISSAO)
    assert len(registros) == 1
    assert conteudo(registros[0].after_json)["permission"] == "read"


def test_criacao_de_usuario_e_registrada(client, h_admin, db):
    client.post("/auth/registrar", headers=h_admin, json={
        "username": "auditado", "email": "auditado@indoc.local",
        "password": "senha-forte-123", "role": "user",
    })
    registros = logs(db, Action.CRIACAO, entity_type="usuario")
    assert len(registros) == 1
    depois = conteudo(registros[0].after_json)
    assert depois["username"] == "auditado"
    assert "hashed_password" not in depois


# ────────────────────────── contexto ──────────────────────────

def test_registro_captura_request_id_e_ip(client, h_comum, documento, db):
    client.get(f"/documentos/{documento['id']}", headers={**h_comum, HEADER: "trace-abc"})
    registro = logs(db, Action.VISUALIZACAO)[-1]
    assert registro.request_id == "trace-abc"
    assert registro.ip is not None


def test_snapshot_pega_so_os_campos_pedidos(comum):
    foto = snapshot(comum, ("id", "username", "role"))
    assert set(foto) == {"id", "username", "role"}
    assert "hashed_password" not in foto


def test_falha_de_auditoria_nao_derruba_a_operacao(db):
    """Um erro ao gravar o log não pode virar 500 na operação de negócio."""
    class SessaoQuebrada:
        def add(self, _):
            raise RuntimeError("banco fora do ar")

        def commit(self):
            raise RuntimeError("banco fora do ar")

        def rollback(self):
            pass

    assert registrar(SessaoQuebrada(), Action.LOGIN) is None


def test_objeto_exotico_e_serializado_como_texto(db, comum):
    """`default=str` evita que um tipo incomum impeça o registro."""
    registro = registrar(db, Action.CRIACAO, user=comum, metadata={"obj": object()})
    assert registro is not None
    assert "<object object at" in registro.metadata_json


def test_valor_irrecuperavel_vira_marcador_em_vez_de_perder_o_registro(db, comum):
    circular = {}
    circular["ele_mesmo"] = circular  # json recusa: referência circular

    registro = registrar(db, Action.CRIACAO, user=comum, metadata=circular)
    assert registro is not None, "o evento não pode ser perdido por causa do payload"
    assert "referência circular" in registro.metadata_json


# ────────────────────────── consulta ──────────────────────────

def test_consulta_e_restrita_a_admin(client, h_comum, h_admin):
    assert client.get("/auditoria", headers=h_comum).status_code == 403
    assert client.get("/auditoria", headers=h_admin).status_code == 200


def test_consulta_exige_autenticacao(client):
    assert sem_sessao(client).get("/auditoria").status_code == 401


def test_filtros_da_consulta(client, h_admin, h_comum, documento, db):
    client.get(f"/documentos/{documento['id']}", headers=h_comum)
    arq_id = documento["arquivos"][0]["id"]
    client.get(f"/documentos/arquivos/{arq_id}/download", headers=h_comum)

    por_acao = client.get("/auditoria", headers=h_admin,
                          params={"action": "download"}).json()
    assert por_acao["total"] == 1
    assert por_acao["itens"][0]["action"] == "download"

    por_documento = client.get("/auditoria", headers=h_admin,
                               params={"document_id": documento["id"]}).json()
    assert por_documento["total"] >= 2

    por_entidade = client.get("/auditoria", headers=h_admin,
                              params={"entity_type": "documento_arquivo"}).json()
    assert por_entidade["total"] == 1


def test_consulta_pagina_e_ordena_do_mais_recente(client, h_admin, h_comum, documento):
    for _ in range(3):
        client.get(f"/documentos/{documento['id']}", headers=h_comum)

    pagina = client.get("/auditoria", headers=h_admin, params={"limit": 2}).json()
    assert pagina["limit"] == 2
    assert len(pagina["itens"]) == 2
    ids = [i["id"] for i in pagina["itens"]]
    assert ids == sorted(ids, reverse=True), "mais recente primeiro"


def test_catalogo_de_acoes(client, h_admin):
    acoes = client.get("/auditoria/catalogo", headers=h_admin).json()["acoes"]
    assert "login" in acoes and "download" in acoes and "alteracao_permissao" in acoes


def test_detalhe_decodifica_o_json(client, h_admin, h_comum, documento):
    client.get(f"/documentos/{documento['id']}", headers=h_comum)
    listagem = client.get("/auditoria", headers=h_admin,
                          params={"action": "visualizacao"}).json()
    log_id = listagem["itens"][0]["id"]
    detalhe = client.get(f"/auditoria/{log_id}", headers=h_admin).json()
    assert detalhe["action"] == "visualizacao"
    assert detalhe["document_id"] == documento["id"]


def test_nao_existe_rota_de_alteracao_ou_exclusao(client, h_admin, h_comum, documento):
    """Append-only: a ausência dos verbos é a garantia."""
    client.get(f"/documentos/{documento['id']}", headers=h_comum)
    log_id = client.get("/auditoria", headers=h_admin).json()["itens"][0]["id"]

    for metodo in (client.put, client.patch, client.delete):
        r = metodo(f"/auditoria/{log_id}", headers=h_admin)
        assert r.status_code == 405, f"{metodo.__name__} não deveria existir"


def test_log_sobrevive_a_exclusao_do_usuario(client, db, h_admin):
    """Sem FK: o registro de quem fez o quê não some junto com a pessoa."""
    u = criar_usuario(db, "efemero")
    h = auth(token_de(client, "efemero"))
    client.get("/documentos", headers=h)
    registrar(db, Action.CRIACAO, user=u, entity_type="teste", entity_id=1)

    uid = u.id
    db.delete(u)
    db.commit()

    assert logs(db, user_id=uid), "auditoria precisa sobreviver ao usuário"
    assert client.get("/auditoria", headers=h_admin,
                      params={"user_id": uid}).status_code == 200
