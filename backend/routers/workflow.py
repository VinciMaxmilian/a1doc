from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

import models
import schemas
from auth import get_current_user, require_admin
from database import get_db

router = APIRouter(prefix="/workflow", tags=["workflow"])


def _transicao_out(t: models.ConfigTransicao) -> dict:
    return {
        "id": t.id,
        "atividade_origem_id": t.atividade_origem_id,
        "atividade_origem_nome": t.atividade_origem.nome,
        "acao": t.acao,
        "atividade_destino_id": t.atividade_destino_id,
        "atividade_destino_nome": t.atividade_destino.nome,
        "gera_nova_revisao": t.gera_nova_revisao,
    }


def _atividade_ou_400(db: Session, ativ_id: int, rotulo: str) -> models.Atividade:
    ativ = db.query(models.Atividade).filter(models.Atividade.id == ativ_id).first()
    if not ativ:
        raise HTTPException(400, f"Atividade {rotulo} não encontrada")
    return ativ


# ────────────────────────── fluxos ──────────────────────────

@router.get("/fluxos", response_model=list[schemas.FluxoOut])
def listar_fluxos(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.Fluxo).options(
        joinedload(models.Fluxo.atividades)
    ).order_by(models.Fluxo.numero).all()


@router.post("/fluxos", response_model=schemas.FluxoOut, status_code=201)
def criar_fluxo(data: schemas.FluxoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    max_num = db.query(func.max(models.Fluxo.numero)).scalar()
    proximo = 0 if max_num is None else max_num + 1
    obj = models.Fluxo(numero=proximo, nome=data.nome, descricao=data.descricao)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/fluxos/{id}", response_model=schemas.OkOut)
def deletar_fluxo(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Fluxo).filter(models.Fluxo.id == id).first()
    if not obj:
        raise HTTPException(404, "Não encontrado")
    ativ_ids = [a.id for a in obj.atividades]
    if ativ_ids and db.query(models.Documento).filter(
        models.Documento.atividade_atual_id.in_(ativ_ids)
    ).first():
        raise HTTPException(400, "Há documentos em atividades deste fluxo")
    db.delete(obj)
    db.commit()
    return {"ok": True}


# ────────────────────────── atividades ──────────────────────────

@router.get("/atividades", response_model=list[schemas.AtividadeOut])
def listar_atividades(fluxo_id: Optional[int] = None, db: Session = Depends(get_db),
                      _=Depends(get_current_user)):
    q = db.query(models.Atividade)
    if fluxo_id:
        q = q.filter(models.Atividade.fluxo_id == fluxo_id)
    return q.order_by(models.Atividade.ordem, models.Atividade.id).all()


@router.post("/atividades", response_model=schemas.AtividadeOut, status_code=201)
def criar_atividade(data: schemas.AtividadeCreate, db: Session = Depends(get_db),
                    _=Depends(require_admin)):
    if not db.query(models.Fluxo).filter(models.Fluxo.id == data.fluxo_id).first():
        raise HTTPException(400, "Fluxo não encontrado")
    obj = models.Atividade(
        nome=data.nome, fluxo_id=data.fluxo_id,
        ordem=data.ordem, role_requerido=data.role_requerido,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/atividades/{id}", response_model=schemas.OkOut)
def deletar_atividade(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Atividade).filter(models.Atividade.id == id).first()
    if not obj:
        raise HTTPException(404, "Não encontrado")
    if db.query(models.Documento).filter(models.Documento.atividade_atual_id == id).first():
        raise HTTPException(400, "Há documentos nesta atividade")
    # Transições que apontam para cá não são removidas em cascata (só as de origem).
    db.query(models.ConfigTransicao).filter(
        models.ConfigTransicao.atividade_destino_id == id
    ).delete(synchronize_session=False)
    db.delete(obj)
    db.commit()
    return {"ok": True}


# ────────────────────────── transições ──────────────────────────

@router.get("/transicoes", response_model=list[schemas.TransicaoOut])
def listar_transicoes(db: Session = Depends(get_db), _=Depends(get_current_user)):
    transicoes = db.query(models.ConfigTransicao).options(
        joinedload(models.ConfigTransicao.atividade_origem),
        joinedload(models.ConfigTransicao.atividade_destino),
    ).all()
    return [_transicao_out(t) for t in transicoes]


@router.post("/transicoes", response_model=schemas.TransicaoOut)
def criar_transicao(data: schemas.ConfigTransicaoCreate, db: Session = Depends(get_db),
                    _=Depends(require_admin)):
    _atividade_ou_400(db, data.atividade_origem_id, "de origem")
    _atividade_ou_400(db, data.atividade_destino_id, "de destino")

    obj = db.query(models.ConfigTransicao).filter(
        models.ConfigTransicao.atividade_origem_id == data.atividade_origem_id,
        models.ConfigTransicao.acao == data.acao,
    ).first()
    if obj:
        obj.atividade_destino_id = data.atividade_destino_id
        obj.gera_nova_revisao = data.gera_nova_revisao
    else:
        obj = models.ConfigTransicao(**data.model_dump())
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return _transicao_out(obj)


@router.delete("/transicoes/{id}", response_model=schemas.OkOut)
def deletar_transicao(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.ConfigTransicao).filter(models.ConfigTransicao.id == id).first()
    if not obj:
        raise HTTPException(404, "Não encontrado")
    db.delete(obj)
    db.commit()
    return {"ok": True}
