"""Vocabulário do controle de acesso.

Três eixos: QUEM (subject), SOBRE O QUÊ (resource) e O QUE PODE (permission).
Tudo em str para gravar legível no banco e aparecer legível na auditoria.
"""
from enum import StrEnum


class SubjectType(StrEnum):
    USUARIO = "usuario"
    GRUPO = "grupo"
    PERFIL = "perfil"


class ResourceType(StrEnum):
    """Níveis da cadeia de herança, do mais amplo ao mais específico.

    GLOBAL é a raiz: uma permissão concedida ali vale para toda a instalação,
    salvo negação mais específica.
    """

    GLOBAL = "global"
    AMBIENTE = "ambiente"
    AREA = "area"
    PROJETO = "projeto"
    DOCUMENTO = "documento"


# Do mais amplo ao mais específico. A resolução percorre ao contrário.
CADEIA_HERANCA: tuple[ResourceType, ...] = (
    ResourceType.GLOBAL,
    ResourceType.AMBIENTE,
    ResourceType.AREA,
    ResourceType.PROJETO,
    ResourceType.DOCUMENTO,
)


class Permission(StrEnum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    REVISE = "revise"
    COMMENT = "comment"
    APPROVE = "approve"
    REJECT = "reject"
    DISTRIBUTE = "distribute"
    MANAGE_PERMISSIONS = "manage_permissions"
    MANAGE_WORKFLOW = "manage_workflow"
    MANAGE_METADATA = "manage_metadata"


TODAS_PERMISSOES: tuple[str, ...] = tuple(p.value for p in Permission)

# Curinga aceito em ACLEntry.permission e PerfilPermissao.permission.
# Guardado como valor literal para que uma linha "*" no banco seja óbvia.
QUALQUER_PERMISSAO = "*"


# ── Perfis semente ──────────────────────────────────────────────────────────
# Criados pela migration 0003. `sistema=True` impede exclusão pela API.
#
# PERFIL_USUARIO_PADRAO reproduz exatamente o que um usuário `role="user"` já
# podia fazer antes da FASE 1 — ver a nota sobre compatibilidade em
# `docs/permissions.md`. Ele existe para que a introdução da ACL não tire
# acesso de ninguém numa instalação existente.

PERFIL_ADMINISTRADOR = "administrador"
PERFIL_USUARIO_PADRAO = "usuario_padrao"
PERFIL_CONTROLE_DOCUMENTAL = "controle_documental"
PERFIL_PROJETISTA = "projetista"
PERFIL_REVISOR = "revisor"
PERFIL_APROVADOR = "aprovador"
PERFIL_FORNECEDOR = "fornecedor"
PERFIL_CLIENTE = "cliente"
PERFIL_CONSULTA = "consulta"

PERFIS_SEMENTE: dict[str, tuple[str, tuple[str, ...]]] = {
    PERFIL_ADMINISTRADOR: (
        "Acesso total. Equivale aos papéis 'admin' e 'dev' anteriores.",
        (QUALQUER_PERMISSAO,),
    ),
    PERFIL_USUARIO_PADRAO: (
        "Compatibilidade: o que todo usuário autenticado já podia fazer antes da ACL.",
        (
            Permission.READ, Permission.CREATE, Permission.UPLOAD,
            Permission.DOWNLOAD, Permission.REVISE,
            Permission.APPROVE, Permission.REJECT,
        ),
    ),
    PERFIL_CONTROLE_DOCUMENTAL: (
        "Controle documental: administra metadados, distribui e revisa.",
        (
            Permission.READ, Permission.CREATE, Permission.UPDATE,
            Permission.DOWNLOAD, Permission.UPLOAD, Permission.REVISE,
            Permission.COMMENT, Permission.DISTRIBUTE, Permission.MANAGE_METADATA,
        ),
    ),
    PERFIL_PROJETISTA: (
        "Elabora e emite documentos da sua disciplina.",
        (
            Permission.READ, Permission.CREATE, Permission.UPDATE,
            Permission.DOWNLOAD, Permission.UPLOAD, Permission.REVISE,
            Permission.COMMENT,
        ),
    ),
    PERFIL_REVISOR: (
        "Analisa e comenta, sem aprovar.",
        (Permission.READ, Permission.DOWNLOAD, Permission.COMMENT),
    ),
    PERFIL_APROVADOR: (
        "Aprova ou reprova documentos submetidos.",
        (
            Permission.READ, Permission.DOWNLOAD, Permission.COMMENT,
            Permission.APPROVE, Permission.REJECT,
        ),
    ),
    PERFIL_FORNECEDOR: (
        "Externo: envia documentos e revisões do próprio escopo.",
        (
            Permission.READ, Permission.DOWNLOAD, Permission.UPLOAD,
            Permission.REVISE, Permission.COMMENT,
        ),
    ),
    PERFIL_CLIENTE: (
        "Externo: consulta e comenta o que lhe foi distribuído.",
        (Permission.READ, Permission.DOWNLOAD, Permission.COMMENT),
    ),
    PERFIL_CONSULTA: (
        "Somente leitura.",
        (Permission.READ,),
    ),
}
