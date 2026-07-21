from conftest import auth, criar_usuario, token_de


def test_login_com_credenciais_validas(client, comum):
    r = client.post("/auth/login",
                    data={"username": "comum1", "password": "senha-forte-123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "comum1"
    assert "hashed_password" not in body["user"]


def test_login_com_senha_errada(client, comum):
    r = client.post("/auth/login", data={"username": "comum1", "password": "errada"})
    assert r.status_code == 401


def test_usuario_inativo_nao_loga(client, db, comum):
    comum.is_active = False
    db.commit()
    r = client.post("/auth/login",
                    data={"username": "comum1", "password": "senha-forte-123"})
    assert r.status_code == 403


def test_me_exige_token(client):
    assert client.get("/auth/me").status_code == 401


def test_token_invalido_e_rejeitado(client):
    assert client.get("/auth/me", headers=auth("lixo.nao.jwt")).status_code == 401


def test_token_de_usuario_desativado_para_de_funcionar(client, db, comum):
    headers = auth(token_de(client, "comum1"))
    assert client.get("/auth/me", headers=headers).status_code == 200
    comum.is_active = False
    db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_registrar_exige_admin(client, h_comum):
    """Escalação de privilégio: usuário comum não cria contas."""
    r = client.post("/auth/registrar", headers=h_comum, json={
        "username": "invasor", "email": "x@y.com",
        "password": "senha-forte-123", "role": "dev",
    })
    assert r.status_code == 403


def test_registrar_sem_token_e_bloqueado(client):
    r = client.post("/auth/registrar", json={
        "username": "invasor", "email": "x@y.com",
        "password": "senha-forte-123", "role": "dev",
    })
    assert r.status_code == 401


def test_admin_registra_usuario(client, h_admin):
    r = client.post("/auth/registrar", headers=h_admin, json={
        "username": "novo", "email": "novo@indoc.local",
        "password": "senha-forte-123", "role": "user",
    })
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "user"


def test_role_invalido_e_rejeitado(client, h_admin):
    r = client.post("/auth/registrar", headers=h_admin, json={
        "username": "novo", "email": "novo@indoc.local",
        "password": "senha-forte-123", "role": "superuser",
    })
    assert r.status_code == 422


def test_email_invalido_e_rejeitado(client, h_admin):
    r = client.post("/auth/registrar", headers=h_admin, json={
        "username": "novo", "email": "nao-eh-email",
        "password": "senha-forte-123", "role": "user",
    })
    assert r.status_code == 422


def test_senha_curta_e_rejeitada(client, h_admin):
    r = client.post("/auth/registrar", headers=h_admin, json={
        "username": "novo", "email": "novo@indoc.local",
        "password": "123", "role": "user",
    })
    assert r.status_code == 422


def test_admin_nao_deleta_a_propria_conta(client, h_admin, db):
    admin_id = client.get("/auth/me", headers=h_admin).json()["id"]
    assert client.delete(f"/usuarios/{admin_id}", headers=h_admin).status_code == 400


def test_listar_usuarios_exige_admin(client, h_comum, h_admin):
    assert client.get("/usuarios", headers=h_comum).status_code == 403
    assert client.get("/usuarios", headers=h_admin).status_code == 200


def test_role_dev_tem_acesso_administrativo(client, db):
    criar_usuario(db, "devuser", role="dev")
    headers = auth(token_de(client, "devuser"))
    assert client.get("/usuarios", headers=headers).status_code == 200
