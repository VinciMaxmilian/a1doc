"""API de administração do controle de acesso (FASE 1).

Quem pode o quê aqui:

- criar/editar grupos e perfis, e atribuir perfis: `exige_admin`. Mexer no
  catálogo de perfis é mudar a política da instalação inteira.
- conceder/negar ACL sobre um recurso: `manage_permissions` NAQUELE recurso.
  Assim o coordenador de um projeto distribui acesso dentro dele sem virar
  administrador do sistema.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

import schemas as schemas_legado
from database import get_db
from indoc.permissions import schemas as sch
from indoc.permissions.constants import Permission, ResourceType
from indoc.permissions.deps import exige_admin, get_permissions
from indoc.permissions.models import (
    ACLEntry,
    Grupo,
    Perfil,
    PerfilPermissao,
    UsuarioGrupo,
    UsuarioPerfil,
)
from indoc.permissions.service import PermissionService, Recurso
from indoc.users.models import User

router = APIRouter(prefix="/permissoes", tags=["permissoes"])


def _recurso(resource_type: str, resource_id: int | None) -> Recurso:
    tipo = ResourceType(resource_type)
    return Recurso(tipo, None if tipo == ResourceType.GLOBAL else resource_id)


def _perfil_out(p: Perfil) -> dict:
    return {
        "id": p.id, "nome": p.nome, "descricao": p.descricao,
        "sistema": p.sistema, "ativo": p.ativo,
        "permissoes": sorted(pp.permission for pp in p.permissoes),
    }


# ── catálogo ────────────────────────────────────────────────────────────

@router.get("/catalogo", response_model=sch.CatalogoOut)
def catalogo(_: PermissionService = Depends(get_permissions)):
    """Vocabulário aceito. A UI monta os selects a partir daqui."""
    return sch.CatalogoOut()


# ── permissões efetivas ─────────────────────────────────────────────────

@router.get("/efetivas", response_model=sch.PermissoesEfetivasOut)
def minhas_permissoes(
    resource_type: ResourceType = ResourceType.GLOBAL,
    resource_id: int | None = None,
    perms: PermissionService = Depends(get_permissions),
):
    """O que EU posso neste recurso. A UI usa para esconder o que não cabe."""
    try:
        alvo = _recurso(resource_type, resource_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {
        "usuario_id": perms.user.id,
        "resource_type": alvo.tipo.value,
        "resource_id": alvo.id,
        "is_admin": perms.is_admin,
        "permissoes": sorted(perms.permissoes_em(alvo)),
    }


@router.get("/efetivas/{usuario_id}", response_model=sch.PermissoesEfetivasOut)
def permissoes_de(
    usuario_id: int,
    resource_type: ResourceType = ResourceType.GLOBAL,
    resource_id: int | None = None,
    db: Session = Depends(get_db),
    _: PermissionService = Depends(exige_admin),
):
    """O que OUTRO usuário pode. Ferramenta de suporte: responde
    "por que fulano não consegue abrir isso?" sem entrar no banco."""
    alvo_user = db.query(User).filter(User.id == usuario_id).first()
    if not alvo_user:
        raise HTTPException(404, "Usuário não encontrado")
    try:
        alvo = _recurso(resource_type, resource_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    servico = PermissionService(db, alvo_user)
    return {
        "usuario_id": usuario_id,
        "resource_type": alvo.tipo.value,
        "resource_id": alvo.id,
        "is_admin": servico.is_admin,
        "permissoes": sorted(servico.permissoes_em(alvo)),
    }


# ── grupos ──────────────────────────────────────────────────────────────

@router.get("/grupos", response_model=list[sch.GrupoOut])
def listar_grupos(db: Session = Depends(get_db), _: PermissionService = Depends(exige_admin)):
    contagem = dict(
        db.query(UsuarioGrupo.grupo_id, func.count(UsuarioGrupo.id))
        .group_by(UsuarioGrupo.grupo_id).all()
    )
    return [
        {"id": g.id, "nome": g.nome, "descricao": g.descricao, "ativo": g.ativo,
         "total_membros": contagem.get(g.id, 0)}
        for g in db.query(Grupo).order_by(Grupo.nome).all()
    ]


@router.post("/grupos", response_model=sch.GrupoOut, status_code=201)
def criar_grupo(data: sch.GrupoCreate, db: Session = Depends(get_db),
                _: PermissionService = Depends(exige_admin)):
    if db.query(Grupo).filter(Grupo.nome == data.nome).first():
        raise HTTPException(400, "Já existe um grupo com esse nome")
    g = Grupo(nome=data.nome, descricao=data.descricao)
    db.add(g)
    db.commit()
    db.refresh(g)
    return {"id": g.id, "nome": g.nome, "descricao": g.descricao,
            "ativo": g.ativo, "total_membros": 0}


@router.put("/grupos/{grupo_id}", response_model=sch.GrupoOut)
def atualizar_grupo(grupo_id: int, data: sch.GrupoUpdate, db: Session = Depends(get_db),
                    _: PermissionService = Depends(exige_admin)):
    g = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not g:
        raise HTTPException(404, "Grupo não encontrado")
    if data.nome and data.nome != g.nome:
        if db.query(Grupo).filter(Grupo.nome == data.nome).first():
            raise HTTPException(400, "Já existe um grupo com esse nome")
        g.nome = data.nome
    if data.descricao is not None:
        g.descricao = data.descricao
    if data.ativo is not None:
        g.ativo = data.ativo
    db.commit()
    db.refresh(g)
    total = db.query(func.count(UsuarioGrupo.id)).filter(
        UsuarioGrupo.grupo_id == grupo_id
    ).scalar()
    return {"id": g.id, "nome": g.nome, "descricao": g.descricao,
            "ativo": g.ativo, "total_membros": total}


@router.delete("/grupos/{grupo_id}", response_model=schemas_legado.OkOut)
def deletar_grupo(grupo_id: int, db: Session = Depends(get_db),
                  _: PermissionService = Depends(exige_admin)):
    g = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not g:
        raise HTTPException(404, "Grupo não encontrado")
    # As ACLs que citam o grupo ficariam órfãs e voltariam a valer se um grupo
    # novo reaproveitasse o id. Removidas junto.
    db.query(ACLEntry).filter(
        ACLEntry.subject_type == "grupo", ACLEntry.subject_id == grupo_id
    ).delete(synchronize_session=False)
    db.delete(g)
    db.commit()
    return {"ok": True}


@router.get("/grupos/{grupo_id}/membros", response_model=list[sch.MembroOut])
def listar_membros(grupo_id: int, db: Session = Depends(get_db),
                   _: PermissionService = Depends(exige_admin)):
    if not db.query(Grupo).filter(Grupo.id == grupo_id).first():
        raise HTTPException(404, "Grupo não encontrado")
    return (
        db.query(User).join(UsuarioGrupo, UsuarioGrupo.usuario_id == User.id)
        .filter(UsuarioGrupo.grupo_id == grupo_id).order_by(User.username).all()
    )


@router.post("/grupos/{grupo_id}/membros/{usuario_id}", response_model=schemas_legado.OkOut)
def adicionar_membro(grupo_id: int, usuario_id: int, db: Session = Depends(get_db),
                     _: PermissionService = Depends(exige_admin)):
    if not db.query(Grupo).filter(Grupo.id == grupo_id).first():
        raise HTTPException(404, "Grupo não encontrado")
    if not db.query(User).filter(User.id == usuario_id).first():
        raise HTTPException(404, "Usuário não encontrado")
    ja = db.query(UsuarioGrupo).filter(
        UsuarioGrupo.grupo_id == grupo_id, UsuarioGrupo.usuario_id == usuario_id
    ).first()
    if not ja:
        db.add(UsuarioGrupo(grupo_id=grupo_id, usuario_id=usuario_id))
        db.commit()
    return {"ok": True}


@router.delete("/grupos/{grupo_id}/membros/{usuario_id}", response_model=schemas_legado.OkOut)
def remover_membro(grupo_id: int, usuario_id: int, db: Session = Depends(get_db),
                   _: PermissionService = Depends(exige_admin)):
    db.query(UsuarioGrupo).filter(
        UsuarioGrupo.grupo_id == grupo_id, UsuarioGrupo.usuario_id == usuario_id
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}


# ── perfis ──────────────────────────────────────────────────────────────

@router.get("/perfis", response_model=list[sch.PerfilOut])
def listar_perfis(db: Session = Depends(get_db), _: PermissionService = Depends(exige_admin)):
    return [_perfil_out(p) for p in db.query(Perfil).order_by(Perfil.nome).all()]


@router.post("/perfis", response_model=sch.PerfilOut, status_code=201)
def criar_perfil(data: sch.PerfilCreate, db: Session = Depends(get_db),
                 _: PermissionService = Depends(exige_admin)):
    if db.query(Perfil).filter(Perfil.nome == data.nome).first():
        raise HTTPException(400, "Já existe um perfil com esse nome")
    p = Perfil(nome=data.nome, descricao=data.descricao, sistema=False)
    p.permissoes = [PerfilPermissao(permission=perm) for perm in set(data.permissoes)]
    db.add(p)
    db.commit()
    db.refresh(p)
    return _perfil_out(p)


@router.put("/perfis/{perfil_id}", response_model=sch.PerfilOut)
def atualizar_perfil(perfil_id: int, data: sch.PerfilUpdate, db: Session = Depends(get_db),
                     _: PermissionService = Depends(exige_admin)):
    p = db.query(Perfil).filter(Perfil.id == perfil_id).first()
    if not p:
        raise HTTPException(404, "Perfil não encontrado")
    if data.descricao is not None:
        p.descricao = data.descricao
    if data.ativo is not None:
        p.ativo = data.ativo
    if data.permissoes is not None:
        # Perfis de sistema podem ter as permissões ajustadas (a instalação é
        # de quem a opera), mas não podem ser excluídos.
        db.query(PerfilPermissao).filter(
            PerfilPermissao.perfil_id == perfil_id
        ).delete(synchronize_session=False)
        db.flush()
        for perm in set(data.permissoes):
            db.add(PerfilPermissao(perfil_id=perfil_id, permission=perm))
    db.commit()
    db.refresh(p)
    return _perfil_out(p)


@router.delete("/perfis/{perfil_id}", response_model=schemas_legado.OkOut)
def deletar_perfil(perfil_id: int, db: Session = Depends(get_db),
                   _: PermissionService = Depends(exige_admin)):
    p = db.query(Perfil).filter(Perfil.id == perfil_id).first()
    if not p:
        raise HTTPException(404, "Perfil não encontrado")
    if p.sistema:
        raise HTTPException(400, "Perfil de sistema não pode ser excluído")
    if db.query(UsuarioPerfil).filter(UsuarioPerfil.perfil_id == perfil_id).first():
        raise HTTPException(400, "Há usuários com este perfil atribuído")
    db.query(ACLEntry).filter(
        ACLEntry.subject_type == "perfil", ACLEntry.subject_id == perfil_id
    ).delete(synchronize_session=False)
    db.delete(p)
    db.commit()
    return {"ok": True}


# ── atribuição de perfil a usuário ──────────────────────────────────────

@router.get("/usuarios/{usuario_id}/perfis", response_model=list[sch.UsuarioPerfilOut])
def listar_perfis_do_usuario(usuario_id: int, db: Session = Depends(get_db),
                             _: PermissionService = Depends(exige_admin)):
    linhas = (
        db.query(UsuarioPerfil, Perfil.nome)
        .join(Perfil, Perfil.id == UsuarioPerfil.perfil_id)
        .filter(UsuarioPerfil.usuario_id == usuario_id).all()
    )
    return [
        {"id": up.id, "perfil_id": up.perfil_id, "perfil_nome": nome,
         "resource_type": up.resource_type, "resource_id": up.resource_id}
        for up, nome in linhas
    ]


@router.post("/usuarios/{usuario_id}/perfis", response_model=sch.UsuarioPerfilOut, status_code=201)
def atribuir_perfil(usuario_id: int, data: sch.AtribuirPerfil, db: Session = Depends(get_db),
                    _: PermissionService = Depends(exige_admin)):
    if not db.query(User).filter(User.id == usuario_id).first():
        raise HTTPException(404, "Usuário não encontrado")
    perfil = db.query(Perfil).filter(Perfil.id == data.perfil_id).first()
    if not perfil:
        raise HTTPException(404, "Perfil não encontrado")

    tipo = None if data.resource_type in (None, ResourceType.GLOBAL) else data.resource_type.value
    rid = None if tipo is None else data.resource_id

    ja = db.query(UsuarioPerfil).filter(
        UsuarioPerfil.usuario_id == usuario_id,
        UsuarioPerfil.perfil_id == data.perfil_id,
        UsuarioPerfil.resource_type.is_(None) if tipo is None
        else UsuarioPerfil.resource_type == tipo,
        UsuarioPerfil.resource_id.is_(None) if rid is None
        else UsuarioPerfil.resource_id == rid,
    ).first()
    if ja:
        up = ja
    else:
        up = UsuarioPerfil(usuario_id=usuario_id, perfil_id=data.perfil_id,
                           resource_type=tipo, resource_id=rid)
        db.add(up)
        db.commit()
        db.refresh(up)
    return {"id": up.id, "perfil_id": up.perfil_id, "perfil_nome": perfil.nome,
            "resource_type": up.resource_type, "resource_id": up.resource_id}


@router.delete("/usuarios/{usuario_id}/perfis/{atribuicao_id}", response_model=schemas_legado.OkOut)
def remover_perfil(usuario_id: int, atribuicao_id: int, db: Session = Depends(get_db),
                   _: PermissionService = Depends(exige_admin)):
    db.query(UsuarioPerfil).filter(
        UsuarioPerfil.id == atribuicao_id, UsuarioPerfil.usuario_id == usuario_id
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}


# ── ACL ─────────────────────────────────────────────────────────────────

@router.get("/acl", response_model=list[sch.ACLOut])
def listar_acl(
    resource_type: ResourceType,
    resource_id: int | None = None,
    db: Session = Depends(get_db),
    perms: PermissionService = Depends(get_permissions),
):
    """Concessões sobre um recurso. Exige `manage_permissions` NELE."""
    try:
        alvo = _recurso(resource_type, resource_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    perms.exigir(Permission.MANAGE_PERMISSIONS, alvo)
    return (
        db.query(ACLEntry)
        .filter(ACLEntry.resource_type == alvo.tipo.value)
        .filter(ACLEntry.resource_id.is_(None) if alvo.id is None
                else ACLEntry.resource_id == alvo.id)
        .order_by(ACLEntry.subject_type, ACLEntry.subject_id, ACLEntry.permission)
        .all()
    )


@router.post("/acl", response_model=sch.ACLOut, status_code=201)
def conceder(data: sch.ACLCreate, db: Session = Depends(get_db),
             perms: PermissionService = Depends(get_permissions)):
    try:
        alvo = _recurso(data.resource_type, data.resource_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    perms.exigir(Permission.MANAGE_PERMISSIONS, alvo)
    _validar_sujeito(db, data.subject_type, data.subject_id)

    existente = db.query(ACLEntry).filter(
        ACLEntry.subject_type == data.subject_type.value,
        ACLEntry.subject_id == data.subject_id,
        ACLEntry.resource_type == alvo.tipo.value,
        ACLEntry.resource_id.is_(None) if alvo.id is None else ACLEntry.resource_id == alvo.id,
        ACLEntry.permission == data.permission,
    ).first()

    if existente:
        existente.allow = data.allow
        entrada = existente
    else:
        entrada = ACLEntry(
            subject_type=data.subject_type.value, subject_id=data.subject_id,
            resource_type=alvo.tipo.value, resource_id=alvo.id,
            permission=data.permission, allow=data.allow,
            created_by_id=perms.user.id,
        )
        db.add(entrada)
    db.commit()
    db.refresh(entrada)
    return entrada


@router.delete("/acl/{entry_id}", response_model=schemas_legado.OkOut)
def revogar(entry_id: int, db: Session = Depends(get_db),
            perms: PermissionService = Depends(get_permissions)):
    entrada = db.query(ACLEntry).filter(ACLEntry.id == entry_id).first()
    if not entrada:
        raise HTTPException(404, "Entrada não encontrada")
    alvo = _recurso(entrada.resource_type, entrada.resource_id)
    perms.exigir(Permission.MANAGE_PERMISSIONS, alvo)
    db.delete(entrada)
    db.commit()
    return {"ok": True}


def _validar_sujeito(db: Session, subject_type, subject_id: int) -> None:
    """Uma ACL apontando para sujeito inexistente é lixo silencioso."""
    modelo = {"usuario": User, "grupo": Grupo, "perfil": Perfil}[subject_type.value]
    if not db.query(modelo).filter(modelo.id == subject_id).first():
        raise HTTPException(400, f"{subject_type.value} {subject_id} não encontrado")
