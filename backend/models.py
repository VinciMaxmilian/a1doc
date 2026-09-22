"""Ponto de entrada único dos models — e shim de compatibilidade.

Os models vivem em `indoc/<dominio>/models.py`. Este módulo reexporta todos eles
para que `import models; models.Documento` continue funcionando em routers,
tasks, testes e no `env.py` do Alembic.

Importante: importar ESTE módulo é o que garante que todas as classes estejam
registradas em `Base.metadata` antes do SQLAlchemy configurar os mappers — as
`relationship()` são resolvidas por nome de classe. Código novo pode importar
direto de `indoc.<dominio>.models`, mas quem cria o engine/metadata (Alembic,
fixtures de teste) deve continuar passando por aqui.
"""
from indoc.core.database import Base
from indoc.core.time import utcnow
from indoc.documents.models import (
    CampoFormulario,
    Documento,
    DocumentoArquivo,
    TipoDocumento,
    UploadJob,
    ValorCampo,
)
from indoc.hierarchy.models import Ambiente, Area, Projeto
from indoc.permissions.models import (
    ACLEntry,
    Grupo,
    Perfil,
    PerfilPermissao,
    UsuarioGrupo,
    UsuarioPerfil,
)
from indoc.users.models import User
from indoc.workflow.models import Atividade, ConfigTransicao, Fluxo, HistoricoWorkflow

__all__ = [
    "Base",
    "utcnow",
    "User",
    "Ambiente",
    "Area",
    "Projeto",
    "TipoDocumento",
    "CampoFormulario",
    "Documento",
    "DocumentoArquivo",
    "ValorCampo",
    "UploadJob",
    "Grupo",
    "UsuarioGrupo",
    "Perfil",
    "PerfilPermissao",
    "UsuarioPerfil",
    "ACLEntry",
    "Fluxo",
    "Atividade",
    "ConfigTransicao",
    "HistoricoWorkflow",
]
