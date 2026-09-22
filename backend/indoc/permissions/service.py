"""PermissionService — o único lugar que decide se alguém pode algo.

A FASE 1 exige que nenhum endpoint replique lógica de autorização. Tudo passa
por aqui.

## Ordem de resolução

Um recurso é resolvido para a sua cadeia de ancestrais, do mais amplo ao mais
específico:

    global -> ambiente -> area -> projeto -> documento

A avaliação percorre a cadeia ao CONTRÁRIO (do mais específico para o mais
amplo) e para no primeiro nível que tenha alguma regra aplicável ao usuário.
Dentro de um nível:

1. há negação explícita (`ACLEntry.allow=False`)  -> NEGADO
2. há concessão explícita (`ACLEntry.allow=True`) -> PERMITIDO
3. há perfil atribuído nesse escopo que concede   -> PERMITIDO
4. nada                                           -> sobe um nível

Esgotada a cadeia sem regra alguma: NEGADO (default deny).

Consequências desejadas:

- o mais específico sobrescreve o herdado (um `deny` no documento derruba um
  `allow` no projeto);
- dentro de um mesmo nível, negar vence conceder;
- uma negação explícita vence o perfil no mesmo nível.

## Duas formas de conceder

`Perfil`/`PerfilPermissao` é o caminho normal: um pacote nomeado de permissões
atribuído por `UsuarioPerfil`, opcionalmente restrito a um recurso.

`ACLEntry` é a exceção pontual — conceder ou negar UMA permissão a UM sujeito
sobre UM recurso. É o que permite "este fornecedor não vê este documento"
sem inventar um perfil novo.

## Por que não existe coluna `inherited`

O roadmap sugere um campo `inherited` na ACL. Materializar linhas herdadas
exigiria reescrever descendentes a cada mudança e conviver com o risco de
dessincronizarem. Aqui a herança é calculada na resolução: existe linha só onde
alguém de fato concedeu ou negou algo. O efeito observável é o mesmo e não há
estado derivado para corromper.
"""
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from indoc.documents.models import Documento
from indoc.hierarchy.models import Area, Projeto
from indoc.permissions.constants import (
    QUALQUER_PERMISSAO,
    Permission,
    ResourceType,
    SubjectType,
)
from indoc.permissions.models import ACLEntry, PerfilPermissao, UsuarioGrupo, UsuarioPerfil
from indoc.users.models import User

# Papéis legados com acesso irrestrito. Mantidos por compatibilidade e como
# válvula de segurança: um erro de configuração da ACL não pode deixar a
# instalação sem ninguém capaz de consertá-la.
ADMIN_ROLES = ("admin", "dev")


@dataclass(frozen=True)
class Recurso:
    """Um nó da hierarquia. `GLOBAL` é a raiz e não tem id."""

    tipo: ResourceType
    id: Optional[int] = None

    def __post_init__(self) -> None:
        if self.tipo == ResourceType.GLOBAL and self.id is not None:
            raise ValueError("recurso global não tem id")
        if self.tipo != ResourceType.GLOBAL and self.id is None:
            raise ValueError(f"recurso '{self.tipo}' exige id")

    @property
    def chave(self) -> tuple[str, Optional[int]]:
        return (self.tipo.value, self.id)


GLOBAL = Recurso(ResourceType.GLOBAL)


def ambiente(id_: int) -> Recurso:
    return Recurso(ResourceType.AMBIENTE, id_)


def area(id_: int) -> Recurso:
    return Recurso(ResourceType.AREA, id_)


def projeto(id_: int) -> Recurso:
    return Recurso(ResourceType.PROJETO, id_)


def documento(id_: int) -> Recurso:
    return Recurso(ResourceType.DOCUMENTO, id_)


def expandir(permissoes: Iterable[str]) -> set[str]:
    """Resolve o curinga '*' para o conjunto completo de permissões."""
    perms = set(permissoes)
    if QUALQUER_PERMISSAO in perms:
        return {p.value for p in Permission}
    return perms


class PermissionService:
    """Resolve permissões para UM usuário. Instância viva por requisição.

    Sujeitos, perfis e linhas de ACL são carregados de uma vez e reaproveitados:
    verificar 200 documentos não dispara 200 queries.
    """

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self._grupos: Optional[set[int]] = None
        self._perfis: Optional[list[UsuarioPerfil]] = None
        self._perms_perfil: Optional[dict[int, set[str]]] = None
        self._entries: Optional[list[ACLEntry]] = None
        self._cadeias: dict[tuple[str, Optional[int]], list[Recurso]] = {}

    # ── carga ────────────────────────────────────────────────────────────

    @property
    def is_admin(self) -> bool:
        return self.user.role in ADMIN_ROLES

    def _grupos_do_usuario(self) -> set[int]:
        if self._grupos is None:
            linhas = self.db.query(UsuarioGrupo.grupo_id).filter(
                UsuarioGrupo.usuario_id == self.user.id
            ).all()
            self._grupos = {gid for (gid,) in linhas}
        return self._grupos

    def _perfis_do_usuario(self) -> list[UsuarioPerfil]:
        if self._perfis is None:
            self._perfis = self.db.query(UsuarioPerfil).filter(
                UsuarioPerfil.usuario_id == self.user.id
            ).all()
        return self._perfis

    def _permissoes_por_perfil(self) -> dict[int, set[str]]:
        if self._perms_perfil is None:
            ids = {up.perfil_id for up in self._perfis_do_usuario()}
            mapa: dict[int, set[str]] = {pid: set() for pid in ids}
            if ids:
                linhas = self.db.query(
                    PerfilPermissao.perfil_id, PerfilPermissao.permission
                ).filter(PerfilPermissao.perfil_id.in_(ids)).all()
                for pid, perm in linhas:
                    mapa[pid].add(perm)
            self._perms_perfil = {pid: expandir(perms) for pid, perms in mapa.items()}
        return self._perms_perfil

    def _sujeitos_base(self) -> set[tuple[str, int]]:
        """Sujeitos que valem em qualquer recurso: o usuário e seus grupos."""
        base = {(SubjectType.USUARIO.value, self.user.id)}
        base |= {(SubjectType.GRUPO.value, gid) for gid in self._grupos_do_usuario()}
        return base

    def _entries_do_usuario(self) -> list[ACLEntry]:
        """Toda linha de ACL que pode se aplicar a este usuário.

        Inclui as dos perfis atribuídos; o escopo do perfil é conferido depois,
        nível a nível, em `_sujeitos_em`.
        """
        if self._entries is None:
            condicoes = [
                (ACLEntry.subject_type == tipo) & (ACLEntry.subject_id == sid)
                for tipo, sid in self._sujeitos_base()
            ]
            perfil_ids = {up.perfil_id for up in self._perfis_do_usuario()}
            if perfil_ids:
                condicoes.append(
                    (ACLEntry.subject_type == SubjectType.PERFIL.value)
                    & (ACLEntry.subject_id.in_(perfil_ids))
                )
            self._entries = self.db.query(ACLEntry).filter(or_(*condicoes)).all()
        return self._entries

    # ── cadeia de herança ────────────────────────────────────────────────

    def cadeia(self, recurso: Recurso) -> list[Recurso]:
        """Ancestrais do recurso, do mais amplo ao mais específico.

        Memorizada por recurso. Um recurso cujo pai não exista mais degrada
        para a cadeia que der para montar, em vez de estourar — resolução de
        permissão não é lugar de 500.
        """
        if recurso.chave in self._cadeias:
            return self._cadeias[recurso.chave]

        cadeia: list[Recurso] = [GLOBAL]

        if recurso.tipo == ResourceType.DOCUMENTO:
            doc = self.db.query(
                Documento.ambiente_id, Documento.area_id, Documento.projeto_id
            ).filter(Documento.id == recurso.id).first()
            if doc:
                cadeia += [ambiente(doc.ambiente_id), area(doc.area_id), projeto(doc.projeto_id)]
            cadeia.append(recurso)

        elif recurso.tipo == ResourceType.PROJETO:
            proj = self.db.query(Projeto.area_id).filter(Projeto.id == recurso.id).first()
            if proj:
                ar = self.db.query(Area.ambiente_id).filter(Area.id == proj.area_id).first()
                if ar:
                    cadeia.append(ambiente(ar.ambiente_id))
                cadeia.append(area(proj.area_id))
            cadeia.append(recurso)

        elif recurso.tipo == ResourceType.AREA:
            ar = self.db.query(Area.ambiente_id).filter(Area.id == recurso.id).first()
            if ar:
                cadeia.append(ambiente(ar.ambiente_id))
            cadeia.append(recurso)

        elif recurso.tipo == ResourceType.AMBIENTE:
            cadeia.append(recurso)

        self._cadeias[recurso.chave] = cadeia
        return cadeia

    def _sujeitos_em(self, cadeia: list[Recurso]) -> set[tuple[str, int]]:
        """Sujeitos válidos nesta cadeia, incluindo perfis cujo escopo a cobre."""
        sujeitos = self._sujeitos_base()
        chaves = {r.chave for r in cadeia}
        for up in self._perfis_do_usuario():
            escopo = (up.resource_type, up.resource_id)
            if up.resource_type is None or escopo in chaves:
                sujeitos.add((SubjectType.PERFIL.value, up.perfil_id))
        return sujeitos

    # ── decisão ──────────────────────────────────────────────────────────

    def _decisao_no_nivel(
        self,
        nivel: Recurso,
        permission: str,
        sujeitos: set[tuple[str, int]],
    ) -> Optional[bool]:
        """True/False se este nível decide; None se não há regra aqui."""
        explicitas = [
            e for e in self._entries_do_usuario()
            if e.resource_type == nivel.tipo.value
            and e.resource_id == nivel.id
            and e.permission in (permission, QUALQUER_PERMISSAO)
            and (e.subject_type, e.subject_id) in sujeitos
        ]
        if explicitas:
            # Negar vence conceder dentro do mesmo nível.
            return all(e.allow for e in explicitas)

        # Nenhuma regra explícita: um perfil atribuído NESTE escopo concede?
        perms = self._permissoes_por_perfil()
        for up in self._perfis_do_usuario():
            no_escopo = (
                (up.resource_type is None and nivel.tipo == ResourceType.GLOBAL)
                or (up.resource_type, up.resource_id) == nivel.chave
            )
            if no_escopo and permission in perms.get(up.perfil_id, ()):
                return True

        return None

    def pode(self, permission: str, recurso: Recurso = GLOBAL) -> bool:
        if self.is_admin:
            return True

        cadeia = self.cadeia(recurso)
        sujeitos = self._sujeitos_em(cadeia)

        # Do mais específico para o mais amplo: o primeiro nível com regra decide.
        for nivel in reversed(cadeia):
            decisao = self._decisao_no_nivel(nivel, permission, sujeitos)
            if decisao is not None:
                return decisao

        return False

    def exigir(self, permission: str, recurso: Recurso = GLOBAL) -> None:
        """Versão que interrompe a requisição. Levanta 403."""
        if not self.pode(permission, recurso):
            from fastapi import HTTPException

            raise HTTPException(403, f"Sem permissão '{permission}' neste recurso")

    def permissoes_em(self, recurso: Recurso = GLOBAL) -> set[str]:
        """Permissões efetivas do usuário no recurso. Serve a UI."""
        return {p.value for p in Permission if self.pode(p.value, recurso)}

    # ── filtros de listagem ──────────────────────────────────────────────
    #
    # Sem isto a ACL protegeria o acesso direto a um documento enquanto a
    # listagem continuaria mostrando tudo — que é a falha D1 do roadmap.

    def projetos_legiveis(self, permission: str = Permission.READ) -> Optional[set[int]]:
        """Ids de projeto onde o usuário tem a permissão.

        Devolve None quando não há restrição (admin): o chamador então não
        filtra, em vez de montar um IN com a base inteira.
        """
        if self.is_admin:
            return None
        ids = [pid for (pid,) in self.db.query(Projeto.id).all()]
        return {pid for pid in ids if self.pode(permission, projeto(pid))}

    def documentos_com_regra_propria(
        self, permission: str = Permission.READ
    ) -> tuple[set[int], set[int]]:
        """Documentos com regra no PRÓPRIO documento: (concedidos, negados).

        Uma regra nesse nível sobrescreve a herdada do projeto nos dois
        sentidos, então a listagem precisa somar os concedidos e subtrair os
        negados.
        """
        if self.is_admin:
            return set(), set()

        candidatos = {
            e.resource_id for e in self._entries_do_usuario()
            if e.resource_type == ResourceType.DOCUMENTO.value and e.resource_id is not None
        }
        candidatos |= {
            up.resource_id for up in self._perfis_do_usuario()
            if up.resource_type == ResourceType.DOCUMENTO.value and up.resource_id is not None
        }

        concedidos: set[int] = set()
        negados: set[int] = set()
        for doc_id in candidatos:
            alvo = documento(doc_id)
            sujeitos = self._sujeitos_em(self.cadeia(alvo))
            decisao = self._decisao_no_nivel(alvo, permission, sujeitos)
            if decisao is True:
                concedidos.add(doc_id)
            elif decisao is False:
                negados.add(doc_id)
        return concedidos, negados


def permissoes_do_perfil(db: Session, perfil_id: int) -> set[str]:
    linhas = db.query(PerfilPermissao.permission).filter(
        PerfilPermissao.perfil_id == perfil_id
    ).all()
    return expandir(p for (p,) in linhas)


__all__ = [
    "PermissionService",
    "Recurso",
    "GLOBAL",
    "ambiente",
    "area",
    "projeto",
    "documento",
    "permissoes_do_perfil",
    "expandir",
    "ADMIN_ROLES",
]
