import pytest
from conftest import auth, criar_usuario, enviar_documento, sem_sessao, token_de

# ────────────────────────── upload ──────────────────────────

def test_upload_cria_documento_na_atividade_inicial(documento, fluxo_inicial):
    assert documento["codigo"].startswith("DOC-")
    assert documento["atividade_atual"]["id"] == fluxo_inicial["elaboracao_id"]
    assert documento["revisao_label"] == "1"
    assert len(documento["arquivos"]) == 1
    assert documento["historico"][0]["acao"] == "upload_inicial"


def test_upload_exige_autenticacao(client, hierarquia):
    r = sem_sessao(client).post("/documentos/upload", data={**hierarquia, "nome": "X"},
                                files=[("arquivos", ("a.pdf", b"x", "application/pdf"))])
    assert r.status_code == 401


def test_upload_rejeita_extensao_perigosa(client, h_comum, hierarquia, fluxo_inicial):
    r = client.post("/documentos/upload", headers=h_comum,
                    data={**hierarquia, "nome": "Malicioso"},
                    files=[("arquivos", ("payload.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 400
    assert "Extensão não permitida" in r.json()["detail"]


def test_upload_rejeita_arquivo_acima_do_limite(client, h_comum, hierarquia, fluxo_inicial):
    """MAX_UPLOAD_MB=1 na suíte."""
    r = client.post("/documentos/upload", headers=h_comum,
                    data={**hierarquia, "nome": "Grande"},
                    files=[("arquivos", ("grande.pdf", b"x" * (2 * 1024 * 1024),
                                         "application/pdf"))])
    assert r.status_code == 413


def test_upload_rejeita_hierarquia_inconsistente(client, h_admin, h_comum,
                                                 hierarquia, fluxo_inicial):
    """Projeto que não pertence à área informada."""
    outra_area = client.post("/hierarquia/areas", headers=h_admin,
                             json={"nome": "Outra", "ambiente_id": hierarquia["ambiente_id"]}
                             ).json()
    r = client.post("/documentos/upload", headers=h_comum,
                    data={**hierarquia, "area_id": outra_area["id"], "nome": "X"},
                    files=[("arquivos", ("a.pdf", b"x", "application/pdf"))])
    assert r.status_code == 400


def test_arquivos_de_mesmo_nome_no_mesmo_envio_nao_se_sobrescrevem(
    client, h_comum, hierarquia, fluxo_inicial
):
    """Antes o segundo arquivo sobrescrevia o primeiro no tmp e o job falhava."""
    doc = enviar_documento(client, h_comum, hierarquia, arquivos=[
        ("arquivos", ("relatorio.pdf", b"primeiro", "application/pdf")),
        ("arquivos", ("relatorio.pdf", b"segundo", "application/pdf")),
    ])
    assert len(doc["arquivos"]) == 2
    nomes = {a["arquivo_nome"] for a in doc["arquivos"]}
    assert nomes == {"relatorio.pdf", "relatorio (1).pdf"}


@pytest.mark.parametrize("nome_perigoso", ["..", ".", "../etc"])
def test_nome_de_documento_nao_escapa_do_diretorio_de_uploads(
    client, db, h_comum, hierarquia, fluxo_inicial, nome_perigoso
):
    """slugify('..') devolvia '..' e o arquivo era gravado acima de UPLOAD_DIR."""
    import config
    import models

    doc = enviar_documento(client, h_comum, hierarquia, nome=nome_perigoso)
    arquivos = db.query(models.DocumentoArquivo).filter(
        models.DocumentoArquivo.documento_id == doc["id"]
    ).all()
    assert arquivos, "upload deveria ter concluído"
    for arq in arquivos:
        destino = (config.UPLOAD_DIR / arq.arquivo_path).resolve()
        assert config.UPLOAD_DIR.resolve() in destino.parents
        assert destino.is_file()


def test_upload_sem_fluxo_zero_marca_job_com_erro(client, h_comum, hierarquia):
    """Sem Fluxo 0 o documento ficaria sem atividade e sem histórico, em silêncio."""
    files = [("arquivos", ("a.pdf", b"x", "application/pdf"))]
    r = client.post("/documentos/upload", headers=h_comum,
                    data={**hierarquia, "nome": "Sem fluxo"}, files=files)
    assert r.status_code == 202
    job = client.get(f"/documentos/jobs/{r.json()['job_id']}", headers=h_comum).json()
    assert job["status"] == "erro"
    assert "Fluxo inicial ausente" in job["erro_msg"]


# ────────────────────────── reenvio ──────────────────────────

def test_reenvio_segue_a_transicao_configurada(client, h_comum, hierarquia,
                                               fluxo_inicial, documento):
    """Antes caía num fallback por ordem de ID; agora usa a transição 'aprovado'."""
    doc = enviar_documento(client, h_comum, hierarquia, nome=documento["nome"])
    assert doc["id"] == documento["id"], "mesmo nome + projeto = mesmo documento"
    assert doc["atividade_atual"]["id"] == fluxo_inicial["aprovacao_id"]
    assert doc["historico"][-1]["acao"] == "reenvio"


def test_reenvio_sem_transicao_mantem_atividade(client, h_admin, h_comum,
                                                hierarquia, fluxo_inicial, documento):
    transicoes = client.get("/workflow/transicoes", headers=h_admin).json()
    for t in transicoes:
        client.delete(f"/workflow/transicoes/{t['id']}", headers=h_admin)
    doc = enviar_documento(client, h_comum, hierarquia, nome=documento["nome"])
    assert doc["atividade_atual"]["id"] == fluxo_inicial["elaboracao_id"]


# ────────────────────────── download ──────────────────────────

def test_download_exige_autenticacao(client, documento):
    arq_id = documento["arquivos"][0]["id"]
    assert sem_sessao(client).get(
        f"/documentos/arquivos/{arq_id}/download"
    ).status_code == 401


def test_download_autenticado_devolve_o_conteudo(client, h_comum, documento):
    arq_id = documento["arquivos"][0]["id"]
    r = client.get(f"/documentos/arquivos/{arq_id}/download", headers=h_comum)
    assert r.status_code == 200
    assert r.content == b"conteudo-pdf"


def test_download_de_arquivo_inexistente(client, h_comum):
    assert client.get("/documentos/arquivos/9999/download",
                      headers=h_comum).status_code == 404


def test_uploads_nao_e_servido_como_estatico(client, documento):
    """A montagem pública de /uploads expunha todos os documentos sem token."""
    r = client.get("/uploads/Eng/Civil/Ponte/Memorial Descritivo/Rev 1/plano.pdf")
    assert r.status_code == 404


def test_caminho_fisico_nao_e_exposto_na_api(documento):
    assert "arquivo_path" not in documento["arquivos"][0]


# ────────────────────────── listagem ──────────────────────────

def test_listagem_filtra_por_nome(client, h_comum, documento):
    r = client.get("/documentos", params={"nome": "Memorial"}, headers=h_comum).json()
    assert r["total"] == 1
    assert r["itens"][0]["id"] == documento["id"]


def test_limit_tem_teto(client, h_comum):
    assert client.get("/documentos", params={"limit": 1_000_000},
                      headers=h_comum).status_code == 422
    assert client.get("/documentos", params={"limit": 100},
                      headers=h_comum).status_code == 200


def test_skip_negativo_e_rejeitado(client, h_comum):
    assert client.get("/documentos", params={"skip": -1},
                      headers=h_comum).status_code == 422


def test_data_sai_com_fuso_explicito(documento):
    """Sem fuso o cliente interpretaria UTC como hora local."""
    assert documento["created_at"].endswith("+00:00")


# ────────────────────────── campos do formulário ──────────────────────────

def test_campos_de_outro_tipo_sao_rejeitados(client, h_admin, documento, hierarquia):
    outro_tipo = client.post("/hierarquia/tipos-documento",
                             json={"nome": "Planta"}, headers=h_admin).json()
    campo_alheio = client.post(
        f"/hierarquia/tipos-documento/{outro_tipo['id']}/campos",
        json={"nome": "Escala", "tipo": "text"}, headers=h_admin,
    ).json()

    r = client.put(f"/documentos/{documento['id']}/campos", headers=h_admin,
                   json={"valores": [{"campo_id": campo_alheio["id"], "valor": "1:100"}]})
    assert r.status_code == 400


def test_atualiza_e_reatualiza_campo(client, h_admin, documento, hierarquia):
    campo = client.post(
        f"/hierarquia/tipos-documento/{hierarquia['tipo_documento_id']}/campos",
        json={"nome": "Autor", "tipo": "text"}, headers=h_admin,
    ).json()

    for valor in ("Ana", "Bruno"):
        r = client.put(f"/documentos/{documento['id']}/campos", headers=h_admin,
                       json={"valores": [{"campo_id": campo["id"], "valor": valor}]})
        assert r.status_code == 200

    detalhe = client.get(f"/documentos/{documento['id']}", headers=h_admin).json()
    campos = {c["campo_nome"]: c["valor"] for c in detalhe["valores_campos"]}
    assert campos["Autor"] == "Bruno"


def test_atualizar_campos_exige_admin(client, h_comum, documento):
    r = client.put(f"/documentos/{documento['id']}/campos", headers=h_comum,
                   json={"valores": []})
    assert r.status_code == 403


# ────────────────────────── revisão ──────────────────────────

def test_responsavel_envia_revisao(client, h_comum, documento):
    r = client.post(f"/documentos/{documento['id']}/upload-revisao", headers=h_comum,
                    files={"arquivo": ("v2.pdf", b"versao 2", "application/pdf")},
                    data={"observacao": "ajustes"})
    assert r.status_code == 200
    assert len(r.json()["arquivos"]) == 2


def test_revisao_rejeita_extensao_perigosa(client, h_comum, documento):
    r = client.post(f"/documentos/{documento['id']}/upload-revisao", headers=h_comum,
                    files={"arquivo": ("x.sh", b"#!/bin/sh", "text/plain")})
    assert r.status_code == 400


def test_estranho_nao_envia_revisao_em_atividade_restrita(
    client, db, h_admin, documento, fluxo_inicial
):
    import models

    ativ = db.query(models.Atividade).filter(
        models.Atividade.id == fluxo_inicial["elaboracao_id"]
    ).first()
    ativ.role_requerido = "admin"
    db.commit()

    criar_usuario(db, "estranho", role="user")
    h_estranho = auth(token_de(client, "estranho"))
    r = client.post(f"/documentos/{documento['id']}/upload-revisao", headers=h_estranho,
                    files={"arquivo": ("v2.pdf", b"x", "application/pdf")})
    assert r.status_code == 403
