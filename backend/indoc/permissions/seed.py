"""Semente dos perfis e atribuição padrão.

Existe porque a semente precisa acontecer em três caminhos diferentes:

- `alembic upgrade head` numa base existente (migration 0003);
- startup da aplicação, inclusive num banco criado por `create_all`;
- criação de um usuário novo, que precisa nascer com algum perfil.

Tudo aqui é idempotente: rodar duas vezes não duplica nem sobrescreve. A
migration 0003 tem a sua própria cópia dos dados de propósito — migration é
histórico e não pode mudar de efeito porque esta constante mudou.
"""
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from indoc.permissions.constants import (
    PERFIL_ADMINISTRADOR,
    PERFIL_USUARIO_PADRAO,
    PERFIS_SEMENTE,
)
from indoc.permissions.models import Perfil, PerfilPermissao, UsuarioPerfil
from indoc.permissions.service import ADMIN_ROLES
from indoc.users.models import User

logger = logging.getLogger("indoc.permissions")


def garantir_perfis(db: Session) -> dict[str, int]:
    """Cria os perfis semente que faltarem. Devolve {nome: id} de todos eles.

    Não mexe em perfil que já existe: se um administrador ajustou as permissões
    do `projetista`, o ajuste dele manda.
    """
    existentes = {p.nome: p for p in db.query(Perfil).all()}
    criados = False

    for nome, (descricao, permissoes) in PERFIS_SEMENTE.items():
        if nome in existentes:
            continue
        perfil = Perfil(nome=nome, descricao=descricao, sistema=True, ativo=True)
        perfil.permissoes = [PerfilPermissao(permission=str(p)) for p in permissoes]
        db.add(perfil)
        existentes[nome] = perfil
        criados = True

    if criados:
        try:
            db.commit()
        except IntegrityError:
            # Outro worker semeou primeiro. Reler é a resposta certa.
            db.rollback()
            existentes = {p.nome: p for p in db.query(Perfil).all()}
        else:
            logger.info("Perfis semente verificados")

    return {nome: p.id for nome, p in existentes.items()}


def perfil_padrao_para(role: str) -> str:
    """Perfil que um usuário recebe ao ser criado, a partir do papel legado."""
    return PERFIL_ADMINISTRADOR if role in ADMIN_ROLES else PERFIL_USUARIO_PADRAO


def atribuir_perfil_padrao(db: Session, user: User) -> None:
    """Dá ao usuário o perfil global correspondente ao seu papel.

    Sem isto um usuário novo nasceria sem permissão nenhuma — a ACL é
    default-deny. Idempotente: não duplica se já houver atribuição.
    """
    ids = garantir_perfis(db)
    perfil_id = ids[perfil_padrao_para(user.role or "user")]

    ja_tem = db.query(UsuarioPerfil).filter(
        UsuarioPerfil.usuario_id == user.id,
        UsuarioPerfil.perfil_id == perfil_id,
        UsuarioPerfil.resource_type.is_(None),
    ).first()
    if ja_tem:
        return

    db.add(UsuarioPerfil(usuario_id=user.id, perfil_id=perfil_id,
                         resource_type=None, resource_id=None))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


__all__ = ["garantir_perfis", "perfil_padrao_para", "atribuir_perfil_padrao"]
