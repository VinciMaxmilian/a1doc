"""Shim de compatibilidade — a implementação vive em `indoc/auth/`.

Mantido para não quebrar `from auth import get_current_user` espalhado pelos
routers. Código novo deve importar de `indoc.auth.*`.
"""
from indoc.auth.deps import get_current_user, is_admin, oauth2_scheme, require_admin
from indoc.auth.password import hash_password, verify_password
from indoc.auth.tokens import criar_access_token as create_token
from indoc.permissions.service import ADMIN_ROLES

__all__ = [
    "ADMIN_ROLES",
    "hash_password",
    "verify_password",
    "create_token",
    "get_current_user",
    "is_admin",
    "require_admin",
    "oauth2_scheme",
]
