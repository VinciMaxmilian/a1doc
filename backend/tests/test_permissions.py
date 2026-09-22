"""FASE 1 — RBAC + ACL granular.

Cobre a resolução (herança, deny, escopo de perfil, grupos), o fechamento da
listagem de documentos e a API de administração.
"""
import pytest
from conftest import auth, criar_usuario, enviar_documento, token_de

import models
from indoc.permissions.constants import Permission, ResourceType, SubjectType
from indoc.permissions.models import ACLEntry, Perfil, PerfilPermissao, UsuarioGrupo, UsuarioPerfil
from indoc.permissions.service import GLOBAL, PermissionService, Recurso
from indoc.permissions.service import ambiente as rec_ambiente
from indoc.permissions.service import documento as rec_documento
from indoc.permissions.service import projeto as rec_projeto

# ────────────────────────── helpers ──────────────────────────

def sem_perfis(db, user):
    """Tira o perfil padrão: o usuário fica sem permissão nenhuma."""
    db.query(UsuarioPerfil).filter(UsuarioPerfil.usuario_id == user.id).delete()
    db.commit()


def conceder(db, user, permission, recurso, allow=True, subject=None):
    stype, sid = subject or (SubjectType.USUARIO.value, user.id)
    db.add(ACLEntry(
        subject_type=stype, subject_id=sid,
        resource_type=recurso.tipo.value, resource_id=recurso.id,
        permission=str(permission), allow=allow,
    ))
    db.commit()


def servico(db, user):
    return PermissionService(db, user)


# ────────────────────────── resolução básica ──────────────────────────

def test_default_deny(db):
    """Sem perfil e sem ACL, não pode nada."""
    u = criar_usuario(db, "vazio")
    sem_perfis(db, u)
    assert servico(db, u).pode(Permission.READ) is False
    assert servico(db, u).pode(Permission.READ, rec_projeto(1)) is False


def test_admin_passa_por_tudo(db):
    a = criar_usuario(db, "adm", role="admin")
    sem_perfis(db, a)
    s = servico(db, a)
    assert s.is_admin
    for p in Permission:
        assert s.pode(p, rec_documento(999)) is True


def test_perfil_padrao_preserva_acesso_anterior(db):
    """O que o usuário comum já podia antes da ACL continua podendo."""
    u = criar_usuario(db, "comum")
    s = servico(db, u)
    for p in [Permission.READ, Permission.CREATE, Permission.UPLOAD,
              Permission.DOWNLOAD, Permission.REVISE,
              Permission.APPROVE, Permission.REJECT]:
        assert s.pode(p) is True, p
    # E o que era restrito a admin continua restrito.
    for p in [Permission.MANAGE_METADATA, Permission.MANAGE_WORKFLOW,
              Permission.MANAGE_PERMISSIONS]:
        assert s.pode(p) is False, p


# ────────────────────────── herança ──────────────────────────

def test_permissao_no_ambiente_desce_ate_o_documento(db, client, h_admin, hierarquia, fluxo_inicial, h_comum):
    doc = enviar_documento(client, h_comum, hierarquia)
    u = criar_usuario(db, "herdeiro")
    sem_perfis(db, u)

    assert servico(db, u).pode(Permission.READ, rec_documento(doc["id"])) is False
    conceder(db, u, Permission.READ, rec_ambiente(hierarquia["ambiente_id"]))
    assert servico(db, u).pode(Permission.READ, rec_documento(doc["id"])) is True


def test_deny_especifico_derruba_allow_herdado(db, client, h_comum, hierarquia, fluxo_inicial):
    doc = enviar_documento(client, h_comum, hierarquia)
    u = criar_usuario(db, "bloqueado")
    sem_perfis(db, u)

    conceder(db, u, Permission.READ, rec_ambiente(hierarquia["ambiente_id"]))
    assert servico(db, u).pode(Permission.READ, rec_documento(doc["id"])) is True

    conceder(db, u, Permission.READ, rec_documento(doc["id"]), allow=False)
    assert servico(db, u).pode(Permission.READ, rec_documento(doc["id"])) is False
    # O irmão continua visível: a negação foi só naquele documento.
    assert servico(db, u).pode(Permission.READ, rec_projeto(hierarquia["projeto_id"])) is True


def test_allow_especifico_vence_deny_herdado(db, client, h_comum, hierarquia, fluxo_inicial):
    doc = enviar_documento(client, h_comum, hierarquia)
    u = criar_usuario(db, "excecao")
    sem_perfis(db, u)

    conceder(db, u, Permission.READ, rec_projeto(hierarquia["projeto_id"]), allow=False)
    conceder(db, u, Permission.READ, rec_documento(doc["id"]), allow=True)
    assert servico(db, u).pode(Permission.READ, rec_documento(doc["id"])) is True


def test_deny_vence_allow_no_mesmo_nivel(db, hierarquia):
    """Usuário permitido diretamente, grupo negado no mesmo recurso."""
    u = criar_usuario(db, "conflito")
    sem_perfis(db, u)
    g = models.Grupo(nome="Bloqueados")
    db.add(g)
    db.commit()
    db.add(UsuarioGrupo(usuario_id=u.id, grupo_id=g.id))
    db.commit()

    alvo = rec_projeto(hierarquia["projeto_id"])
    conceder(db, u, Permission.READ, alvo, allow=True)
    conceder(db, u, Permission.READ, alvo, allow=False,
             subject=(SubjectType.GRUPO.value, g.id))
    assert servico(db, u).pode(Permission.READ, alvo) is False


def test_curinga_concede_todas(db, hierarquia):
    u = criar_usuario(db, "curinga")
    sem_perfis(db, u)
    conceder(db, u, "*", rec_projeto(hierarquia["projeto_id"]))
    s = servico(db, u)
    assert s.pode(Permission.APPROVE, rec_projeto(hierarquia["projeto_id"])) is True
    assert s.pode(Permission.DISTRIBUTE, rec_projeto(hierarquia["projeto_id"])) is True


# ────────────────────────── grupos e perfis ──────────────────────────

def test_permissao_vem_pelo_grupo(db, hierarquia):
    u = criar_usuario(db, "membro")
    sem_perfis(db, u)
    g = models.Grupo(nome="Engenharia Mecânica")
    db.add(g)
    db.commit()

    alvo = rec_projeto(hierarquia["projeto_id"])
    conceder(db, u, Permission.READ, alvo, subject=(SubjectType.GRUPO.value, g.id))
    assert servico(db, u).pode(Permission.READ, alvo) is False  # ainda não é membro

    db.add(UsuarioGrupo(usuario_id=u.id, grupo_id=g.id))
    db.commit()
    assert servico(db, u).pode(Permission.READ, alvo) is True


def test_perfil_com_escopo_nao_vaza_para_fora(db, client, h_admin, hierarquia):
    """Fornecedor do projeto X não enxerga o projeto Y."""
    u = criar_usuario(db, "fornecedor1")
    sem_perfis(db, u)

    outro_proj = client.post("/hierarquia/projetos", headers=h_admin,
                             json={"nome": "Outro", "area_id": hierarquia["area_id"]}).json()

    perfil = db.query(Perfil).filter(Perfil.nome == "fornecedor").first()
    db.add(UsuarioPerfil(usuario_id=u.id, perfil_id=perfil.id,
                         resource_type=ResourceType.PROJETO.value,
                         resource_id=hierarquia["projeto_id"]))
    db.commit()

    s = servico(db, u)
    assert s.pode(Permission.READ, rec_projeto(hierarquia["projeto_id"])) is True
    assert s.pode(Permission.READ, rec_projeto(outro_proj["id"])) is False
    assert s.pode(Permission.READ, GLOBAL) is False


def test_perfil_com_escopo_desce_para_o_documento(db, client, h_comum, hierarquia, fluxo_inicial):
    doc = enviar_documento(client, h_comum, hierarquia)
    u = criar_usuario(db, "fornecedor2")
    sem_perfis(db, u)

    perfil = db.query(Perfil).filter(Perfil.nome == "fornecedor").first()
    db.add(UsuarioPerfil(usuario_id=u.id, perfil_id=perfil.id,
                         resource_type=ResourceType.PROJETO.value,
                         resource_id=hierarquia["projeto_id"]))
    db.commit()

    s = servico(db, u)
    assert s.pode(Permission.READ, rec_documento(doc["id"])) is True
    assert s.pode(Permission.APPROVE, rec_documento(doc["id"])) is False  # fornecedor não aprova


def test_deny_explicito_vence_perfil_no_mesmo_nivel(db, hierarquia):
    u = criar_usuario(db, "perfilado")
    sem_perfis(db, u)
    perfil = db.query(Perfil).filter(Perfil.nome == "consulta").first()
    alvo = rec_projeto(hierarquia["projeto_id"])
    db.add(UsuarioPerfil(usuario_id=u.id, perfil_id=perfil.id,
                         resource_type=ResourceType.PROJETO.value,
                         resource_id=hierarquia["projeto_id"]))
    db.commit()
    assert servico(db, u).pode(Permission.READ, alvo) is True

    conceder(db, u, Permission.READ, alvo, allow=False)
    assert servico(db, u).pode(Permission.READ, alvo) is False


def test_recurso_global_nao_aceita_id():
    with pytest.raises(ValueError):
        Recurso(ResourceType.GLOBAL, 1)
    with pytest.raises(ValueError):
        Recurso(ResourceType.PROJETO, None)


# ────────────────────────── D1: listagem com escopo ──────────────────────────

def test_listagem_so_mostra_o_que_pode_ler(client, db, h_admin, h_comum, hierarquia, fluxo_inicial):
    enviar_documento(client, h_comum, hierarquia, nome="Visível")

    u = criar_usuario(db, "restrito")
    sem_perfis(db, u)
    h = auth(token_de(client, "restrito"))

    r = client.get("/documentos", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] == 0, "usuário sem permissão não pode ver documento algum"

    conceder(db, u, Permission.READ, rec_projeto(hierarquia["projeto_id"]))
    assert client.get("/documentos", headers=h).json()["total"] == 1


def test_listagem_respeita_deny_no_documento(client, db, h_comum, hierarquia, fluxo_inicial):
    a = enviar_documento(client, h_comum, hierarquia, nome="Doc A")
    enviar_documento(client, h_comum, hierarquia, nome="Doc B")

    u = criar_usuario(db, "quase")
    sem_perfis(db, u)
    h = auth(token_de(client, "quase"))
    conceder(db, u, Permission.READ, rec_projeto(hierarquia["projeto_id"]))
    conceder(db, u, Permission.READ, rec_documento(a["id"]), allow=False)

    itens = client.get("/documentos", headers=h).json()["itens"]
    assert [i["nome"] for i in itens] == ["Doc B"]


def test_listagem_inclui_documento_liberado_individualmente(
    client, db, h_comum, hierarquia, fluxo_inicial
):
    a = enviar_documento(client, h_comum, hierarquia, nome="Só esse")
    enviar_documento(client, h_comum, hierarquia, nome="Esse não")

    u = criar_usuario(db, "pontual")
    sem_perfis(db, u)
    h = auth(token_de(client, "pontual"))
    conceder(db, u, Permission.READ, rec_documento(a["id"]))

    itens = client.get("/documentos", headers=h).json()["itens"]
    assert [i["nome"] for i in itens] == ["Só esse"]


def test_detalhe_e_download_negados_sem_permissao(client, db, h_comum, hierarquia, fluxo_inicial):
    doc = enviar_documento(client, h_comum, hierarquia)
    arq_id = doc["arquivos"][0]["id"]

    criar_usuario(db, "curioso")
    u = db.query(models.User).filter(models.User.username == "curioso").first()
    sem_perfis(db, u)
    h = auth(token_de(client, "curioso"))

    assert client.get(f"/documentos/{doc['id']}", headers=h).status_code == 403
    assert client.get(f"/documentos/arquivos/{arq_id}/download", headers=h).status_code == 403


def test_download_exige_permissao_no_documento(client, db, h_comum, hierarquia, fluxo_inicial):
    """Ler não implica baixar: são permissões distintas."""
    doc = enviar_documento(client, h_comum, hierarquia)
    arq_id = doc["arquivos"][0]["id"]

    u = criar_usuario(db, "leitor")
    sem_perfis(db, u)
    h = auth(token_de(client, "leitor"))
    conceder(db, u, Permission.READ, rec_projeto(hierarquia["projeto_id"]))

    assert client.get(f"/documentos/{doc['id']}", headers=h).status_code == 200
    assert client.get(f"/documentos/arquivos/{arq_id}/download", headers=h).status_code == 403

    conceder(db, u, Permission.DOWNLOAD, rec_projeto(hierarquia["projeto_id"]))
    assert client.get(f"/documentos/arquivos/{arq_id}/download", headers=h).status_code == 200


def test_upload_exige_create_no_projeto_de_destino(client, db, h_admin, hierarquia, fluxo_inicial):
    u = criar_usuario(db, "semcreate")
    sem_perfis(db, u)
    h = auth(token_de(client, "semcreate"))

    r = client.post("/documentos/upload", headers=h,
                    data={**hierarquia, "nome": "Tentativa"},
                    files=[("arquivos", ("a.pdf", b"x", "application/pdf"))])
    assert r.status_code == 403


def test_aprovar_e_reprovar_sao_permissoes_distintas(
    client, db, h_comum, hierarquia, fluxo_inicial
):
    doc = enviar_documento(client, h_comum, hierarquia)
    u = criar_usuario(db, "sorejeita")
    sem_perfis(db, u)
    h = auth(token_de(client, "sorejeita"))
    alvo = rec_projeto(hierarquia["projeto_id"])
    conceder(db, u, Permission.READ, alvo)
    conceder(db, u, Permission.REJECT, alvo)

    assert client.post(f"/documentos/{doc['id']}/transitar", headers=h,
                       json={"acao": "aprovado"}).status_code == 403
    # Sem transição 'reprovado' configurada a partir da Elaboração dá 400 —
    # o que importa é que não deu 403: a permissão passou.
    r = client.post(f"/documentos/{doc['id']}/transitar", headers=h,
                    json={"acao": "reprovado"})
    assert r.status_code != 403


# ────────────────────────── API de administração ──────────────────────────

def test_catalogo_lista_o_vocabulario(client, h_comum):
    r = client.get("/permissoes/catalogo", headers=h_comum)
    assert r.status_code == 200
    assert "manage_permissions" in r.json()["permissoes"]
    assert set(r.json()["resource_types"]) == {"global", "ambiente", "area", "projeto", "documento"}


def test_permissoes_efetivas_do_proprio_usuario(client, h_comum):
    r = client.get("/permissoes/efetivas", headers=h_comum)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["is_admin"] is False
    assert "read" in corpo["permissoes"]
    assert "manage_workflow" not in corpo["permissoes"]


def test_permissoes_de_outro_usuario_e_restrito_a_admin(client, h_comum, h_admin, comum):
    assert client.get(f"/permissoes/efetivas/{comum.id}", headers=h_comum).status_code == 403
    assert client.get(f"/permissoes/efetivas/{comum.id}", headers=h_admin).status_code == 200


def test_crud_de_grupo_e_membros(client, h_admin, h_comum, comum):
    r = client.post("/permissoes/grupos", headers=h_admin,
                    json={"nome": "Elétrica", "descricao": "Disciplina elétrica"})
    assert r.status_code == 201
    gid = r.json()["id"]

    assert client.post("/permissoes/grupos", headers=h_admin,
                       json={"nome": "Elétrica"}).status_code == 400
    assert client.post("/permissoes/grupos", headers=h_comum,
                       json={"nome": "X"}).status_code == 403

    assert client.post(f"/permissoes/grupos/{gid}/membros/{comum.id}",
                       headers=h_admin).status_code == 200
    membros = client.get(f"/permissoes/grupos/{gid}/membros", headers=h_admin).json()
    assert [m["username"] for m in membros] == ["comum1"]

    grupos = client.get("/permissoes/grupos", headers=h_admin).json()
    assert [g["total_membros"] for g in grupos if g["id"] == gid] == [1]

    assert client.delete(f"/permissoes/grupos/{gid}/membros/{comum.id}",
                         headers=h_admin).status_code == 200
    assert client.get(f"/permissoes/grupos/{gid}/membros", headers=h_admin).json() == []


def test_perfil_de_sistema_nao_pode_ser_excluido(client, h_admin, db):
    perfil = db.query(Perfil).filter(Perfil.nome == "consulta").first()
    r = client.delete(f"/permissoes/perfis/{perfil.id}", headers=h_admin)
    assert r.status_code == 400


def test_criar_editar_e_excluir_perfil(client, h_admin):
    r = client.post("/permissoes/perfis", headers=h_admin,
                    json={"nome": "auditor", "descricao": "Só olha",
                          "permissoes": ["read", "download"]})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert sorted(r.json()["permissoes"]) == ["download", "read"]
    assert r.json()["sistema"] is False

    r = client.put(f"/permissoes/perfis/{pid}", headers=h_admin,
                   json={"permissoes": ["read"]})
    assert r.json()["permissoes"] == ["read"]

    assert client.delete(f"/permissoes/perfis/{pid}", headers=h_admin).status_code == 200


def test_perfil_rejeita_permissao_inexistente(client, h_admin):
    r = client.post("/permissoes/perfis", headers=h_admin,
                    json={"nome": "torto", "permissoes": ["apagar_tudo"]})
    assert r.status_code == 422


def test_atribuir_perfil_com_escopo_muda_o_acesso(client, db, h_admin, hierarquia, fluxo_inicial, h_comum):
    doc = enviar_documento(client, h_comum, hierarquia)
    u = criar_usuario(db, "novato")
    sem_perfis(db, u)
    h = auth(token_de(client, "novato"))
    assert client.get(f"/documentos/{doc['id']}", headers=h).status_code == 403

    perfil = db.query(Perfil).filter(Perfil.nome == "consulta").first()
    r = client.post(f"/permissoes/usuarios/{u.id}/perfis", headers=h_admin,
                    json={"perfil_id": perfil.id, "resource_type": "projeto",
                          "resource_id": hierarquia["projeto_id"]})
    assert r.status_code == 201
    assert client.get(f"/documentos/{doc['id']}", headers=h).status_code == 200

    atribuicoes = client.get(f"/permissoes/usuarios/{u.id}/perfis", headers=h_admin).json()
    assert client.delete(f"/permissoes/usuarios/{u.id}/perfis/{atribuicoes[0]['id']}",
                         headers=h_admin).status_code == 200
    assert client.get(f"/documentos/{doc['id']}", headers=h).status_code == 403


def test_atribuicao_com_escopo_sem_id_e_rejeitada(client, h_admin, db, comum):
    perfil = db.query(Perfil).filter(Perfil.nome == "consulta").first()
    r = client.post(f"/permissoes/usuarios/{comum.id}/perfis", headers=h_admin,
                    json={"perfil_id": perfil.id, "resource_type": "projeto"})
    assert r.status_code == 422


def test_conceder_acl_exige_manage_permissions_no_recurso(
    client, db, h_admin, h_comum, hierarquia, comum
):
    corpo = {
        "subject_type": "usuario", "subject_id": comum.id,
        "resource_type": "projeto", "resource_id": hierarquia["projeto_id"],
        "permission": "read", "allow": True,
    }
    # usuário comum não administra permissões
    assert client.post("/permissoes/acl", headers=h_comum, json=corpo).status_code == 403
    assert client.post("/permissoes/acl", headers=h_admin, json=corpo).status_code == 201

    # ...até receber manage_permissions naquele projeto
    conceder(db, comum, Permission.MANAGE_PERMISSIONS, rec_projeto(hierarquia["projeto_id"]))
    r = client.get("/permissoes/acl", headers=h_comum,
                   params={"resource_type": "projeto", "resource_id": hierarquia["projeto_id"]})
    assert r.status_code == 200


def test_conceder_acl_rejeita_sujeito_inexistente(client, h_admin, hierarquia):
    r = client.post("/permissoes/acl", headers=h_admin, json={
        "subject_type": "usuario", "subject_id": 99999,
        "resource_type": "projeto", "resource_id": hierarquia["projeto_id"],
        "permission": "read",
    })
    assert r.status_code == 400


def test_conceder_acl_e_idempotente_e_alterna_allow(client, h_admin, hierarquia, comum):
    corpo = {
        "subject_type": "usuario", "subject_id": comum.id,
        "resource_type": "projeto", "resource_id": hierarquia["projeto_id"],
        "permission": "read", "allow": True,
    }
    primeiro = client.post("/permissoes/acl", headers=h_admin, json=corpo).json()
    segundo = client.post("/permissoes/acl", headers=h_admin,
                          json={**corpo, "allow": False}).json()
    assert primeiro["id"] == segundo["id"], "não deve duplicar a mesma regra"
    assert segundo["allow"] is False

    assert client.delete(f"/permissoes/acl/{segundo['id']}", headers=h_admin).status_code == 200


def test_acl_global_nao_aceita_resource_id(client, h_admin, comum):
    r = client.post("/permissoes/acl", headers=h_admin, json={
        "subject_type": "usuario", "subject_id": comum.id,
        "resource_type": "global", "resource_id": 1, "permission": "read",
    })
    assert r.status_code == 422


def test_excluir_grupo_remove_suas_acls(client, db, h_admin, hierarquia):
    gid = client.post("/permissoes/grupos", headers=h_admin, json={"nome": "Temp"}).json()["id"]
    client.post("/permissoes/acl", headers=h_admin, json={
        "subject_type": "grupo", "subject_id": gid,
        "resource_type": "projeto", "resource_id": hierarquia["projeto_id"],
        "permission": "read",
    })
    client.delete(f"/permissoes/grupos/{gid}", headers=h_admin)
    restantes = db.query(ACLEntry).filter(
        ACLEntry.subject_type == "grupo", ACLEntry.subject_id == gid
    ).count()
    assert restantes == 0, "ACL órfã reviveria se um grupo novo reaproveitasse o id"


# ────────────────────────── semente ──────────────────────────

def test_usuario_criado_pela_api_nasce_com_perfil(client, h_admin, db):
    r = client.post("/auth/registrar", headers=h_admin, json={
        "username": "novo", "email": "novo@indoc.local",
        "password": "senha-forte-123", "role": "user",
    })
    assert r.status_code == 201
    u = db.query(models.User).filter(models.User.username == "novo").first()
    atribuicoes = db.query(UsuarioPerfil).filter(UsuarioPerfil.usuario_id == u.id).all()
    assert len(atribuicoes) == 1
    assert servico(db, u).pode(Permission.READ) is True


def test_perfis_semente_sao_idempotentes(db):
    from indoc.permissions.seed import garantir_perfis

    antes = db.query(Perfil).count()
    garantir_perfis(db)
    garantir_perfis(db)
    assert db.query(Perfil).count() == antes
    assert db.query(PerfilPermissao).filter(
        PerfilPermissao.perfil_id == db.query(Perfil).filter(
            Perfil.nome == "consulta").first().id
    ).count() == 1
