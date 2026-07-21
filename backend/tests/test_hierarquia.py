def test_arvore_exige_autenticacao(client):
    assert client.get("/hierarquia").status_code == 401


def test_criacao_exige_admin(client, h_comum):
    r = client.post("/hierarquia/ambientes", json={"nome": "X"}, headers=h_comum)
    assert r.status_code == 403


def test_arvore_completa(client, h_admin, hierarquia):
    arvore = client.get("/hierarquia", headers=h_admin).json()
    assert len(arvore) == 1
    assert arvore[0]["areas"][0]["projetos"][0]["nome"] == "Ponte"


def test_area_com_ambiente_inexistente(client, h_admin):
    r = client.post("/hierarquia/areas",
                    json={"nome": "X", "ambiente_id": 9999}, headers=h_admin)
    assert r.status_code == 400


def test_projeto_com_area_inexistente(client, h_admin):
    r = client.post("/hierarquia/projetos",
                    json={"nome": "X", "area_id": 9999}, headers=h_admin)
    assert r.status_code == 400


def test_nome_vazio_e_rejeitado(client, h_admin):
    assert client.post("/hierarquia/ambientes",
                       json={"nome": ""}, headers=h_admin).status_code == 422


def test_campo_select_exige_opcoes(client, h_admin, hierarquia):
    tipo_id = hierarquia["tipo_documento_id"]
    r = client.post(f"/hierarquia/tipos-documento/{tipo_id}/campos", headers=h_admin,
                    json={"nome": "Disciplina", "tipo": "select"})
    assert r.status_code == 400

    r = client.post(f"/hierarquia/tipos-documento/{tipo_id}/campos", headers=h_admin,
                    json={"nome": "Disciplina", "tipo": "select",
                          "opcoes": ["Elétrica", "Civil"], "ordem": 1})
    assert r.status_code == 201
    assert r.json()["opcoes"] == ["Elétrica", "Civil"]


def test_campos_saem_ordenados(client, h_admin, hierarquia):
    tipo_id = hierarquia["tipo_documento_id"]
    for nome, ordem in [("C", 3), ("A", 1), ("B", 2)]:
        client.post(f"/hierarquia/tipos-documento/{tipo_id}/campos", headers=h_admin,
                    json={"nome": nome, "tipo": "text", "ordem": ordem})
    campos = client.get(f"/hierarquia/tipos-documento/{tipo_id}/campos",
                        headers=h_admin).json()
    assert [c["nome"] for c in campos] == ["A", "B", "C"]


def test_nao_deleta_no_com_documentos(client, h_admin, documento):
    """Excluir ambiente/área/projeto com documentos violaria a FK NOT NULL."""
    doc = documento
    for rota, chave in [
        ("ambientes", "ambiente_id"),
        ("areas", "area_id"),
        ("projetos", "projeto_id"),
        ("tipos-documento", "tipo_documento_id"),
    ]:
        r = client.delete(f"/hierarquia/{rota}/{doc[chave]}", headers=h_admin)
        assert r.status_code == 400, f"{rota} deveria bloquear a exclusão"


def test_deleta_no_vazio(client, h_admin):
    amb = client.post("/hierarquia/ambientes", json={"nome": "Vazio"},
                      headers=h_admin).json()
    assert client.delete(f"/hierarquia/ambientes/{amb['id']}",
                         headers=h_admin).status_code == 200
