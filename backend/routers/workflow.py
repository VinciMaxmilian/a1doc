from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import require_admin, get_current_user
import models, schemas

router = APIRouter(prefix="/workflow", tags=["workflow"])


def _fluxo(f):
    return {"id": f.id, "numero": f.numero, "nome": f.nome, "descricao": f.descricao,
            "atividades": [{"id": a.id, "nome": a.nome, "fluxo_id": a.fluxo_id} for a in f.atividades]}


@router.get("/fluxos")
def listar_fluxos(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [_fluxo(f) for f in db.query(models.Fluxo).order_by(models.Fluxo.numero).all()]


@router.post("/fluxos")
def criar_fluxo(data: schemas.FluxoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    from sqlalchemy import func
    max_num = db.query(func.max(models.Fluxo.numero)).scalar()
    proximo = 0 if max_num is None else max_num + 1
    obj = models.Fluxo(numero=proximo, nome=data.nome, descricao=data.descricao)
    db.add(obj); db.commit(); db.refresh(obj)
    return _fluxo(obj)


@router.delete("/fluxos/{id}")
def deletar_fluxo(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Fluxo).filter(models.Fluxo.id == id).first()
    if not obj: raise HTTPException(404, "Não encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}


@router.get("/atividades")
def listar_atividades(fluxo_id: int = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(models.Atividade)
    if fluxo_id: q = q.filter(models.Atividade.fluxo_id == fluxo_id)
    return [{"id": a.id, "nome": a.nome, "fluxo_id": a.fluxo_id} for a in q.all()]


@router.post("/atividades")
def criar_atividade(data: schemas.AtividadeCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = models.Atividade(nome=data.nome, fluxo_id=data.fluxo_id)
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id, "nome": obj.nome, "fluxo_id": obj.fluxo_id}


@router.delete("/atividades/{id}")
def deletar_atividade(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Atividade).filter(models.Atividade.id == id).first()
    if not obj: raise HTTPException(404, "Não encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}


@router.get("/transicoes")
def listar_transicoes(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [
        {"id": t.id,
         "atividade_origem_id": t.atividade_origem_id,
         "atividade_origem_nome": t.atividade_origem.nome,
         "acao": t.acao,
         "atividade_destino_id": t.atividade_destino_id,
         "atividade_destino_nome": t.atividade_destino.nome,
         "gera_nova_revisao": t.gera_nova_revisao}
        for t in db.query(models.ConfigTransicao).all()
    ]


@router.post("/transicoes")
def criar_transicao(data: schemas.ConfigTransicaoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    existente = db.query(models.ConfigTransicao).filter(
        models.ConfigTransicao.atividade_origem_id == data.atividade_origem_id,
        models.ConfigTransicao.acao == data.acao
    ).first()
    if existente:
        existente.atividade_destino_id = data.atividade_destino_id
        existente.gera_nova_revisao = data.gera_nova_revisao
        db.commit(); db.refresh(existente); obj = existente
    else:
        obj = models.ConfigTransicao(**data.model_dump())
        db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id, "atividade_origem_id": obj.atividade_origem_id,
            "acao": obj.acao, "atividade_destino_id": obj.atividade_destino_id,
            "gera_nova_revisao": obj.gera_nova_revisao}


@router.delete("/transicoes/{id}")
def deletar_transicao(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.ConfigTransicao).filter(models.ConfigTransicao.id == id).first()
    if not obj: raise HTTPException(404, "Não encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}
