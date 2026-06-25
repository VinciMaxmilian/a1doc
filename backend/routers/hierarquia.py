from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import require_admin, get_current_user
import models, schemas

router = APIRouter(prefix="/hierarquia", tags=["hierarquia"])


@router.get("")
def arvore(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [_amb(a) for a in db.query(models.Ambiente).all()]


def _amb(a):
    return {"id": a.id, "nome": a.nome, "areas": [_area(ar) for ar in a.areas]}


def _area(ar):
    return {"id": ar.id, "nome": ar.nome, "ambiente_id": ar.ambiente_id,
            "projetos": [{"id": p.id, "nome": p.nome, "area_id": p.area_id} for p in ar.projetos]}


# Ambientes
@router.get("/ambientes")
def listar_ambientes(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [{"id": a.id, "nome": a.nome} for a in db.query(models.Ambiente).all()]


@router.post("/ambientes")
def criar_ambiente(data: schemas.AmbienteCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = models.Ambiente(nome=data.nome)
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id, "nome": obj.nome}


@router.delete("/ambientes/{id}")
def deletar_ambiente(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Ambiente).filter(models.Ambiente.id == id).first()
    if not obj: raise HTTPException(404, "Não encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}


# Areas
@router.get("/areas")
def listar_areas(ambiente_id: int = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(models.Area)
    if ambiente_id: q = q.filter(models.Area.ambiente_id == ambiente_id)
    return [{"id": a.id, "nome": a.nome, "ambiente_id": a.ambiente_id} for a in q.all()]


@router.post("/areas")
def criar_area(data: schemas.AreaCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = models.Area(nome=data.nome, ambiente_id=data.ambiente_id)
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id, "nome": obj.nome, "ambiente_id": obj.ambiente_id}


@router.delete("/areas/{id}")
def deletar_area(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Area).filter(models.Area.id == id).first()
    if not obj: raise HTTPException(404, "Não encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}


# Projetos
@router.get("/projetos")
def listar_projetos(area_id: int = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(models.Projeto)
    if area_id: q = q.filter(models.Projeto.area_id == area_id)
    return [{"id": p.id, "nome": p.nome, "area_id": p.area_id} for p in q.all()]


@router.post("/projetos")
def criar_projeto(data: schemas.ProjetoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = models.Projeto(nome=data.nome, area_id=data.area_id)
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id, "nome": obj.nome, "area_id": obj.area_id}


@router.delete("/projetos/{id}")
def deletar_projeto(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Projeto).filter(models.Projeto.id == id).first()
    if not obj: raise HTTPException(404, "Não encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}


# Tipos de Documento
@router.get("/tipos-documento")
def listar_tipos(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [{"id": t.id, "nome": t.nome} for t in db.query(models.TipoDocumento).all()]


@router.post("/tipos-documento")
def criar_tipo(data: schemas.TipoDocumentoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = models.TipoDocumento(nome=data.nome)
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id, "nome": obj.nome}


@router.delete("/tipos-documento/{id}")
def deletar_tipo(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.TipoDocumento).filter(models.TipoDocumento.id == id).first()
    if not obj: raise HTTPException(404, "Não encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}


# Campos do Formulário
@router.get("/tipos-documento/{tipo_id}/campos")
def listar_campos(tipo_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    campos = db.query(models.CampoFormulario).filter(
        models.CampoFormulario.tipo_documento_id == tipo_id
    ).order_by(models.CampoFormulario.ordem).all()
    return [{"id": c.id, "nome": c.nome, "tipo": c.tipo, "opcoes": c.opcoes, "ordem": c.ordem} for c in campos]


@router.post("/tipos-documento/{tipo_id}/campos")
def criar_campo(tipo_id: int, data: schemas.CampoFormularioCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = models.CampoFormulario(
        tipo_documento_id=tipo_id, nome=data.nome,
        tipo=data.tipo, opcoes=data.opcoes, ordem=data.ordem
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id, "nome": obj.nome, "tipo": obj.tipo, "opcoes": obj.opcoes, "ordem": obj.ordem}


@router.delete("/campos/{id}")
def deletar_campo(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.CampoFormulario).filter(models.CampoFormulario.id == id).first()
    if not obj: raise HTTPException(404, "Não encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}
