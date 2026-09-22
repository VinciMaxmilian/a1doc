"""FASE 2 — autenticação corporativa: cookies, refresh, CSRF, sessões e throttle."""
import pytest
from conftest import auth, criar_usuario, sem_sessao, token_de

import config
import models
from indoc.auth import tokens
from indoc.auth.models import LoginThrottle, UserSession
from indoc.auth.providers import CredencialInvalida, FirebaseProvider, LocalPasswordProvider
from indoc.core.time import utcnow


def login(client, username="comum1", senha="senha-forte-123"):
    client.cookies.clear()
    r = client.post("/auth/login", data={"username": username, "password": senha})
    assert r.status_code == 200, r.text
    return r


def cabecalho_csrf(resposta):
    return {config.HEADER_CSRF: resposta.json()["csrf_token"]}


# ────────────────────────── cookies ──────────────────────────

def test_login_define_os_tres_cookies(client, comum):
    r = login(client)
    assert config.COOKIE_ACCESS in r.cookies
    assert config.COOKIE_REFRESH in r.cookies
    assert config.COOKIE_CSRF in r.cookies


def test_cookies_de_sessao_sao_httponly_e_o_csrf_nao(client, comum):
    r = login(client)
    # Um Set-Cookie por entrada: o valor de Expires contém vírgula, então
    # separar a string concatenada por vírgula quebraria o parsing.
    definidos = {
        linha.split("=", 1)[0]: linha for linha in r.headers.get_list("set-cookie")
    }
    for cookie in (config.COOKIE_ACCESS, config.COOKIE_REFRESH):
        assert "HttpOnly" in definidos[cookie], f"{cookie} precisa ser HttpOnly"
    # O front precisa LER este para reenviar no header — não pode ser HttpOnly.
    assert "HttpOnly" not in definidos[config.COOKIE_CSRF]


def test_cookie_autentica_sem_header(client, comum):
    login(client)
    r = client.get("/auth/me")  # sem Authorization
    assert r.status_code == 200
    assert r.json()["username"] == "comum1"


def test_header_bearer_continua_funcionando(client, comum):
    """Cliente de API não usa cookie; o header não é o problema que a FASE 2 corrige."""
    token = token_de(client, "comum1")
    sem_sessao(client)
    r = client.get("/auth/me", headers=auth(token))
    assert r.status_code == 200


def test_sem_credencial_alguma_e_401(client):
    assert sem_sessao(client).get("/auth/me").status_code == 401


# ────────────────────────── CSRF ──────────────────────────

def test_metodo_inseguro_por_cookie_exige_csrf(client, admin):
    login(client, "admin1")
    # Sem o header: o navegador mandaria o cookie sozinho num ataque cross-site.
    r = client.post("/permissoes/grupos", json={"nome": "Sem CSRF"})
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]


def test_metodo_inseguro_por_cookie_passa_com_csrf(client, admin):
    r_login = login(client, "admin1")
    r = client.post("/permissoes/grupos", json={"nome": "Com CSRF"},
                    headers=cabecalho_csrf(r_login))
    assert r.status_code == 201


def test_csrf_errado_e_recusado(client, admin):
    login(client, "admin1")
    r = client.post("/permissoes/grupos", json={"nome": "X"},
                    headers={config.HEADER_CSRF: "valor-que-nao-bate"})
    assert r.status_code == 403


def test_leitura_por_cookie_nao_exige_csrf(client, comum):
    login(client)
    assert client.get("/documentos").status_code == 200


def test_bearer_nao_exige_csrf(client, admin):
    """Navegador não injeta Authorization sozinho — não há CSRF a proteger ali."""
    token = token_de(client, "admin1")
    sem_sessao(client)
    r = client.post("/permissoes/grupos", json={"nome": "Via Bearer"}, headers=auth(token))
    assert r.status_code == 201


# ────────────────────────── refresh e rotação ──────────────────────────

def test_refresh_renova_e_rotaciona_o_token(client, comum, db):
    r = login(client)
    primeiro = r.cookies[config.COOKIE_REFRESH]

    r2 = client.post("/auth/refresh")
    assert r2.status_code == 200
    segundo = r2.cookies[config.COOKIE_REFRESH]
    assert segundo != primeiro, "o refresh precisa rotacionar"

    # Continua sendo UMA sessão, não duas.
    assert db.query(UserSession).filter(UserSession.usuario_id == comum.id).count() == 1


def test_reuso_de_refresh_antigo_revoga_tudo(client, comum, db):
    r = login(client)
    antigo = r.cookies[config.COOKIE_REFRESH]
    client.post("/auth/refresh")  # rotaciona

    # Um atacante que copiou o token antigo tenta usá-lo.
    client.cookies.clear()
    client.cookies.set(config.COOKIE_REFRESH, antigo)
    assert client.post("/auth/refresh").status_code == 401

    vivas = db.query(UserSession).filter(
        UserSession.usuario_id == comum.id, UserSession.revoked_at.is_(None)
    ).count()
    assert vivas == 0, "reuso de token deve derrubar todas as sessões do usuário"


def test_refresh_sem_cookie_e_401(client):
    assert sem_sessao(client).post("/auth/refresh").status_code == 401


def test_access_token_expirado_mas_refresh_valido(client, comum, monkeypatch):
    login(client)
    # Simula o access vencido descartando só esse cookie.
    client.cookies.delete(config.COOKIE_ACCESS)
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/refresh").status_code == 200
    assert client.get("/auth/me").status_code == 200


# ────────────────────────── logout e revogação ──────────────────────────

def test_logout_revoga_a_sessao(client, comum, db):
    r = login(client)
    client.post("/auth/logout", headers=cabecalho_csrf(r))
    sessao = db.query(UserSession).filter(UserSession.usuario_id == comum.id).first()
    assert sessao.revoked_at is not None


def test_sessao_revogada_invalida_o_access_token_na_hora(client, comum, db):
    """Revogar não pode esperar o access token expirar sozinho."""
    r = login(client)
    token = r.json()["access_token"]
    sessao = db.query(UserSession).filter(UserSession.usuario_id == comum.id).first()

    sessao.revoked_at = utcnow()
    db.commit()

    sem_sessao(client)
    assert client.get("/auth/me", headers=auth(token)).status_code == 401


def test_listar_e_revogar_sessoes(client, comum, db):
    r1 = login(client)
    login(client)  # segunda sessão, outro "dispositivo"
    r3 = login(client)

    sessoes = client.get("/auth/sessoes").json()
    assert len(sessoes) == 3
    assert sum(1 for s in sessoes if s["atual"]) == 1

    alvo = next(s for s in sessoes if not s["atual"] and s["ativa"])
    assert client.delete(f"/auth/sessoes/{alvo['id']}",
                         headers=cabecalho_csrf(r3)).status_code == 200

    depois = {s["id"]: s for s in client.get("/auth/sessoes").json()}
    assert depois[alvo["id"]]["ativa"] is False
    assert r1 is not None


def test_revogar_todas_mantem_a_sessao_atual(client, comum):
    login(client)
    login(client)
    r = login(client)

    resultado = client.post("/auth/sessoes/revogar-todas", headers=cabecalho_csrf(r))
    assert resultado.json()["revogadas"] == 2
    # A atual continua funcionando — quem trocou a senha não deve se deslogar.
    assert client.get("/auth/me").status_code == 200


def test_nao_revoga_sessao_de_outro_usuario(client, db, comum, admin):
    r_admin = login(client, "admin1")
    sessao_admin = client.get("/auth/sessoes").json()[0]["id"]

    r_comum = login(client, "comum1")
    assert client.delete(f"/auth/sessoes/{sessao_admin}",
                         headers=cabecalho_csrf(r_comum)).status_code == 404
    assert r_admin is not None


# ────────────────────────── contas bloqueadas ──────────────────────────

def test_conta_inativa_nao_loga(client, db):
    u = criar_usuario(db, "inativo")
    u.is_active = False
    db.commit()
    client.cookies.clear()
    r = client.post("/auth/login", data={"username": "inativo", "password": "senha-forte-123"})
    assert r.status_code == 403


def test_conta_bloqueada_nao_loga(client, db):
    u = criar_usuario(db, "suspenso")
    u.bloqueado_em = utcnow()
    u.motivo_bloqueio = "Em apuração"
    db.commit()
    client.cookies.clear()
    r = client.post("/auth/login", data={"username": "suspenso", "password": "senha-forte-123"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Em apuração"


def test_bloqueio_derruba_sessao_existente(client, db, comum):
    login(client)
    comum.bloqueado_em = utcnow()
    db.commit()
    assert client.get("/auth/me").status_code == 403


# ────────────────────────── força bruta ──────────────────────────

def test_bloqueio_progressivo_apos_falhas(client, comum, db, monkeypatch):
    monkeypatch.setattr(config, "LOGIN_MAX_FALHAS", 3)
    client.cookies.clear()

    for _ in range(3):
        r = client.post("/auth/login", data={"username": "comum1", "password": "errada"})
        assert r.status_code == 401

    # Bloqueado — e nem a senha certa passa mais.
    r = client.post("/auth/login", data={"username": "comum1", "password": "senha-forte-123"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_login_correto_zera_o_contador(client, comum, db, monkeypatch):
    monkeypatch.setattr(config, "LOGIN_MAX_FALHAS", 5)
    client.cookies.clear()
    for _ in range(2):
        client.post("/auth/login", data={"username": "comum1", "password": "errada"})

    assert client.post("/auth/login",
                       data={"username": "comum1", "password": "senha-forte-123"}
                       ).status_code == 200

    linha = db.query(LoginThrottle).filter(
        LoginThrottle.tipo == "username", LoginThrottle.chave == "comum1"
    ).first()
    assert linha.falhas == 0
    assert linha.bloqueado_ate is None


def test_usuario_inexistente_nao_vaza_que_nao_existe(client):
    client.cookies.clear()
    r = client.post("/auth/login", data={"username": "ninguem", "password": "x"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Credenciais inválidas"


# ────────────────────────── providers ──────────────────────────

def test_providers_lista_o_local_por_padrao(client, comum):
    login(client)
    r = client.get("/auth/providers")
    assert r.json()["providers"] == ["local"]
    assert r.json()["firebase_project_id"] is None


def test_firebase_aparece_quando_configurado(client, comum, monkeypatch):
    monkeypatch.setattr(config, "FIREBASE_ENABLED", True)
    monkeypatch.setattr(config, "FIREBASE_PROJECT_ID", "indoc-71c52")
    login(client)
    corpo = client.get("/auth/providers").json()
    assert corpo["providers"] == ["local", "firebase"]
    assert corpo["firebase_project_id"] == "indoc-71c52"


def test_firebase_desligado_recusa_login(client, db):
    with pytest.raises(CredencialInvalida):
        FirebaseProvider().autenticar(db, {"id_token": "qualquer-coisa"})


def test_firebase_vincula_por_email_verificado(db, monkeypatch):
    """E-mail/senha e Google emitem o mesmo ID token — o vínculo é o mesmo."""
    monkeypatch.setattr(config, "FIREBASE_ENABLED", True)
    monkeypatch.setattr(config, "FIREBASE_PROJECT_ID", "indoc-71c52")
    u = criar_usuario(db, "ana")

    provider = FirebaseProvider()
    monkeypatch.setattr(provider, "verificar_token", lambda _t: {
        "sub": "uid-firebase-123", "email": "ana@indoc.local", "email_verified": True,
    })

    identidade = provider.autenticar(db, {"id_token": "fake"})
    assert identidade.user.id == u.id
    assert identidade.provider == "firebase"

    # Segunda vez entra pelo vínculo já gravado.
    assert provider.autenticar(db, {"id_token": "fake"}).user.id == u.id


def test_firebase_recusa_email_nao_verificado(db, monkeypatch):
    """Senão bastaria criar uma conta com o e-mail alheio para assumir a conta."""
    monkeypatch.setattr(config, "FIREBASE_ENABLED", True)
    monkeypatch.setattr(config, "FIREBASE_PROJECT_ID", "indoc-71c52")
    criar_usuario(db, "bia")

    provider = FirebaseProvider()
    monkeypatch.setattr(provider, "verificar_token", lambda _t: {
        "sub": "uid-falso", "email": "bia@indoc.local", "email_verified": False,
    })
    with pytest.raises(CredencialInvalida):
        provider.autenticar(db, {"id_token": "fake"})


def test_firebase_recusa_quem_nao_esta_cadastrado(db, monkeypatch):
    monkeypatch.setattr(config, "FIREBASE_ENABLED", True)
    monkeypatch.setattr(config, "FIREBASE_PROJECT_ID", "indoc-71c52")
    monkeypatch.setattr(config, "FIREBASE_AUTO_PROVISIONAR", False)

    provider = FirebaseProvider()
    monkeypatch.setattr(provider, "verificar_token", lambda _t: {
        "sub": "uid-desconhecido", "email": "estranho@gmail.com", "email_verified": True,
    })
    with pytest.raises(CredencialInvalida):
        provider.autenticar(db, {"id_token": "fake"})


def test_provider_local_nao_vaza_tempo_com_usuario_inexistente(db):
    """Verifica a senha mesmo sem usuário, para não virar oráculo de contas."""
    with pytest.raises(CredencialInvalida):
        LocalPasswordProvider().autenticar(db, {"username": "fantasma", "password": "x"})


# ────────────────────────── tokens ──────────────────────────

def test_refresh_token_e_guardado_como_hash(client, comum, db):
    r = login(client)
    bruto = r.cookies[config.COOKIE_REFRESH]
    sessao = db.query(UserSession).filter(UserSession.usuario_id == comum.id).first()
    assert sessao.refresh_token_hash != bruto
    assert sessao.refresh_token_hash == tokens.hash_refresh(bruto)


def test_access_token_carrega_a_sessao(client, comum):
    r = login(client)
    payload = tokens.ler_access_token(r.json()["access_token"])
    assert payload["typ"] == "access"
    assert payload["sid"] is not None


def test_token_de_outro_tipo_e_recusado(client, comum):
    import jwt

    forjado = jwt.encode(
        {"sub": str(comum.id), "typ": "refresh",
         "exp": utcnow().timestamp() + 3600},
        config.SECRET_KEY, algorithm=config.ALGORITHM,
    )
    sem_sessao(client)
    assert client.get("/auth/me", headers=auth(forjado)).status_code == 401


def test_usuarios_criados_pela_api_continuam_funcionando(client, admin, db):
    r_login = login(client, "admin1")
    r = client.post("/auth/registrar", headers=cabecalho_csrf(r_login), json={
        "username": "recem", "email": "recem@indoc.local",
        "password": "senha-forte-123", "role": "user",
    })
    assert r.status_code == 201
    assert login(client, "recem").status_code == 200
    assert db.query(models.User).filter(models.User.username == "recem").first() is not None
