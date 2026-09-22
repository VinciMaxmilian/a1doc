"""Dependências FastAPI da autorização.

Os endpoints não chamam o `PermissionService` na mão: declaram o que exigem.

    @router.get("/{doc_id}")
    def detalhe(doc_id: int, _=Depends(exige_documento(Permission.READ))):
        ...

O recurso é extraído do path pelo próprio guard, então não há como um endpoint
esquecer de checar — que é a regra da FASE 1: nenhuma lógica de autorização
replicada fora deste módulo.
"""
from fastapi import Depends, HTTPException, Path
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from indoc.permissions.constants import Permission
from indoc.permissions.service import (
    GLOBAL,
    PermissionService,
    Recurso,
    ambiente,
    area,
    documento,
    projeto,
)
from indoc.users.models import User


def get_permissions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PermissionService:
    """Serviço de permissões do usuário atual, vivo por requisição."""
    return PermissionService(db, user)


def exige(permission: Permission, recurso: Recurso = GLOBAL):
    """Guard para permissão em recurso fixo (normalmente global)."""

    def _guard(perms: PermissionService = Depends(get_permissions)) -> PermissionService:
        perms.exigir(permission, recurso)
        return perms

    return _guard


def exige_documento(permission: Permission):
    def _guard(
        doc_id: int = Path(...),
        perms: PermissionService = Depends(get_permissions),
    ) -> PermissionService:
        perms.exigir(permission, documento(doc_id))
        return perms

    return _guard


def exige_projeto(permission: Permission):
    def _guard(
        projeto_id: int = Path(...),
        perms: PermissionService = Depends(get_permissions),
    ) -> PermissionService:
        perms.exigir(permission, projeto(projeto_id))
        return perms

    return _guard


def exige_area(permission: Permission):
    def _guard(
        area_id: int = Path(...),
        perms: PermissionService = Depends(get_permissions),
    ) -> PermissionService:
        perms.exigir(permission, area(area_id))
        return perms

    return _guard


def exige_ambiente(permission: Permission):
    def _guard(
        ambiente_id: int = Path(...),
        perms: PermissionService = Depends(get_permissions),
    ) -> PermissionService:
        perms.exigir(permission, ambiente(ambiente_id))
        return perms

    return _guard


def exige_admin(perms: PermissionService = Depends(get_permissions)) -> PermissionService:
    """Operações de administração da própria ACL.

    Distinta de `exige(MANAGE_PERMISSIONS)` de propósito: quem pode conceder
    permissões num projeto não deveria poder criar perfis novos na instalação.
    """
    if not perms.is_admin:
        raise HTTPException(403, "Acesso restrito a Admin/Dev")
    return perms


__all__ = [
    "get_permissions",
    "exige",
    "exige_documento",
    "exige_projeto",
    "exige_area",
    "exige_ambiente",
    "exige_admin",
]
