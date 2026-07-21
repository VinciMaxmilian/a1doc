from conftest import auth, criar_usuario, token_de

import models


def test_fluxos_sao_numerados_a_partir_de_zero(client, h_admin):
    a = client.post("/workflow/fluxos", json={"nome": "A"}, headers=h_admin).json()
    b = client.post("/workflow/fluxos", json={"nome": "B"}, headers=h_admin).json()
    assert (a["numero"], b["numero"]) == (0, 1)


def test_configuracao_exige_admin(client, h_comum):
    assert client.post("/workflow/fluxos", json={"nome": "X"},
                       headers=h_comum).status_code == 403


def test_leitura_liberada_para_usuario_comum(client, h_comum, fluxo_inicial):
    assert client.get("/workflow/fluxos", headers=h_comum).status_code == 200


def test_atividade_em_fluxo_inexistente(client, h_admin):
    r = client.post("/workflow/atividades",
                    json={"nome": "X", "fluxo_id": 9999}, headers=h_admin)
    assert r.status_code == 400


def test_atividades_saem_por_ordem_e_nao_por_id(client, h_admin):
    fluxo = client.post("/workflow/fluxos", json={"nome": "F"}, headers=h_admin).json()
    for nome, ordem in [("Terceira", 3), ("Primeira", 1), ("Segunda", 2)]:
        client.post("/workflow/atividades", headers=h_admin,
                    json={"nome": nome, "fluxo_id": fluxo["id"], "ordem": ordem})
    ativs = client.get("/workflow/atividades", params={"fluxo_id": fluxo["id"]},
                       headers=h_admin).json()
    assert [a["nome"] for a in ativs] == ["Primeira", "Segunda", "Terceira"]


def test_acao_invalida_e_rejeitada(client, h_admin, fluxo_inicial):
    r = client.post("/workflow/transicoes", headers=h_admin, json={
        "atividade_origem_id": fluxo_inicial["elaboracao_id"],
        "acao": "talvez",
        "atividade_destino_id": fluxo_inicial["aprovacao_id"],
    })
    assert r.status_code == 422


def test_transicao_com_atividade_inexistente(client, h_admin, fluxo_inicial):
    r = client.post("/workflow/transicoes", headers=h_admin, json={
        "atividade_origem_id": fluxo_inicial["elaboracao_id"],
        "acao": "aprovado", "atividade_destino_id": 9999,
    })
    assert r.status_code == 400


def test_transicao_e_upsert_por_origem_e_acao(client, h_admin, fluxo_inicial):
    antes = client.get("/workflow/transicoes", headers=h_admin).json()
    r = client.post("/workflow/transicoes", headers=h_admin, json={
        "atividade_origem_id": fluxo_inicial["elaboracao_id"],
        "acao": "aprovado",
        "atividade_destino_id": fluxo_inicial["elaboracao_id"],
        "gera_nova_revisao": True,
    })
    assert r.status_code == 200
    assert r.json()["gera_nova_revisao"] is True
    depois = client.get("/workflow/transicoes", headers=h_admin).json()
    assert len(depois) == len(antes)


def test_criar_transicao_devolve_nomes(client, h_admin, fluxo_inicial):
    r = client.post("/workflow/transicoes", headers=h_admin, json={
        "atividade_origem_id": fluxo_inicial["aprovacao_id"],
        "acao": "aprovado",
        "atividade_destino_id": fluxo_inicial["elaboracao_id"],
    }).json()
    assert r["atividade_origem_nome"] == "Aprovação"
    assert r["atividade_destino_nome"] == "Elaboração"


def test_nao_deleta_atividade_com_documentos(client, h_admin, documento, fluxo_inicial):
    r = client.delete(f"/workflow/atividades/{fluxo_inicial['elaboracao_id']}",
                      headers=h_admin)
    assert r.status_code == 400


def test_nao_deleta_fluxo_com_documentos(client, h_admin, documento, fluxo_inicial):
    r = client.delete(f"/workflow/fluxos/{fluxo_inicial['fluxo_id']}", headers=h_admin)
    assert r.status_code == 400


# ────────────────────────── transição de documento ──────────────────────────

def test_transitar_move_o_documento(client, h_comum, documento, fluxo_inicial):
    r = client.post(f"/documentos/{documento['id']}/transitar", headers=h_comum,
                    json={"acao": "aprovado", "observacao": "ok"})
    assert r.status_code == 200
    body = r.json()
    assert body["atividade_atual"]["id"] == fluxo_inicial["aprovacao_id"]
    assert body["historico"][-1]["acao"] == "aprovado"


def test_transitar_gera_nova_revisao_quando_configurado(client, h_comum, documento):
    client.post(f"/documentos/{documento['id']}/transitar", headers=h_comum,
                json={"acao": "aprovado"})
    r = client.post(f"/documentos/{documento['id']}/transitar", headers=h_comum,
                    json={"acao": "reprovado"}).json()
    assert r["revisao_label"] == "2"


def test_transicao_nao_configurada(client, h_comum, documento):
    r = client.post(f"/documentos/{documento['id']}/transitar", headers=h_comum,
                    json={"acao": "reprovado"})
    assert r.status_code == 400
    assert "Sem transição configurada" in r.json()["detail"]


def test_acao_livre_e_rejeitada(client, h_comum, documento):
    r = client.post(f"/documentos/{documento['id']}/transitar", headers=h_comum,
                    json={"acao": "qualquer-coisa"})
    assert r.status_code == 422


def test_atividade_restrita_bloqueia_papel_errado(client, db, h_comum, documento,
                                                  fluxo_inicial):
    ativ = db.query(models.Atividade).filter(
        models.Atividade.id == fluxo_inicial["elaboracao_id"]
    ).first()
    ativ.role_requerido = "admin"
    db.commit()

    r = client.post(f"/documentos/{documento['id']}/transitar", headers=h_comum,
                    json={"acao": "aprovado"})
    assert r.status_code == 403


def test_admin_transita_mesmo_em_atividade_restrita(client, db, h_admin, documento,
                                                    fluxo_inicial):
    ativ = db.query(models.Atividade).filter(
        models.Atividade.id == fluxo_inicial["elaboracao_id"]
    ).first()
    ativ.role_requerido = "user"
    db.commit()

    r = client.post(f"/documentos/{documento['id']}/transitar", headers=h_admin,
                    json={"acao": "aprovado"})
    assert r.status_code == 200


def test_papel_correto_transita(client, db, documento, fluxo_inicial):
    ativ = db.query(models.Atividade).filter(
        models.Atividade.id == fluxo_inicial["elaboracao_id"]
    ).first()
    ativ.role_requerido = "user"
    db.commit()

    criar_usuario(db, "revisor", role="user")
    headers = auth(token_de(client, "revisor"))
    r = client.post(f"/documentos/{documento['id']}/transitar", headers=headers,
                    json={"acao": "aprovado"})
    assert r.status_code == 200


def test_transitar_exige_autenticacao(client, documento):
    r = client.post(f"/documentos/{documento['id']}/transitar", json={"acao": "aprovado"})
    assert r.status_code == 401
