"""Catálogo de ações auditadas (FASE 3).

Enum em vez de string solta para que a tela de auditoria possa oferecer a lista
de filtros sem adivinhar, e para que um erro de digitação não crie uma ação
fantasma que ninguém vai encontrar depois.
"""
from enum import StrEnum


class Action(StrEnum):
    # ── autenticação ──
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_INVALIDO = "login_invalido"
    LOGIN_BLOQUEADO = "login_bloqueado"
    SESSAO_REVOGADA = "sessao_revogada"
    SESSAO_REUSO_DETECTADO = "sessao_reuso_detectado"

    # ── ciclo de vida de entidades ──
    CRIACAO = "criacao"
    EDICAO = "edicao"
    EXCLUSAO = "exclusao"

    # ── documentos ──
    VISUALIZACAO = "visualizacao"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    REVISAO = "revisao"
    ALTERACAO_METADATA = "alteracao_metadata"
    APROVACAO = "aprovacao"
    REPROVACAO = "reprovacao"
    TRANSICAO = "transicao"

    # ── governança ──
    ALTERACAO_PERMISSAO = "alteracao_permissao"
    ALTERACAO_WORKFLOW = "alteracao_workflow"

    # ── reservadas para fases seguintes ──
    # Declaradas desde já para que a tela de filtros e os relatórios não
    # precisem mudar quando as fases correspondentes chegarem.
    COMENTARIO = "comentario"          # FASE 16
    ASSINATURA = "assinatura"          # FASE 36
    GRD = "grd"                        # FASE 23
    EXPORTACAO = "exportacao"          # FASE 58


ACOES = tuple(a.value for a in Action)


# Ações que só fazem sentido com um documento no contexto. Serve de conferência
# no modo estrito dos testes — não para bloquear gravação em produção.
ACOES_DE_DOCUMENTO = frozenset({
    Action.VISUALIZACAO, Action.DOWNLOAD, Action.UPLOAD, Action.REVISAO,
    Action.ALTERACAO_METADATA, Action.APROVACAO, Action.REPROVACAO, Action.TRANSICAO,
})
