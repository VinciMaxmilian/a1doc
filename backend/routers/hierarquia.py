from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

import models
import schemas
from auth import get_current_user, require_admin
from database import get_db

router = APIRouter(prefix="/hierarquia", tags=["hierarquia"])


def _bloquear_se_houver_documentos(db: Session, coluna, valor, msg: str) -> None:
    """Impede excluir um nó da hierarquia que ainda tem documentos ligados
    (a FK é NOT NULL — a exclusão estouraria como 500)."""
    if db.query(models.Documento).filter(coluna == valor).first():
        raise HTTPException(400, msg)


@router.get("", response_model=list[schemas.AmbienteTreeOut])
def arvore(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.Ambiente).options(
        joinedload(models.Ambiente.areas).joinedload(models.Area.projetos)
    ).order_by(models.Ambiente.nome).all()


# ────────────────────────── Ambientes ──────────────────────────

@router.get("/ambientes", response_model=list[schemas.AmbienteOut])
def listar_ambientes(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.Ambiente).order_by(models.Ambiente.nome).all()


@router.post("/ambientes", response_model=schemas.AmbienteOut, status_code=201)
def criar_ambiente(data: schemas.AmbienteCreate, db: Session = Depends(get_db),
                   _=Depends(require_admin)):
    obj = models.Ambiente(nome=data.nome)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/ambientes/{id}", response_model=schemas.OkOut)
def deletar_ambiente(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Ambiente).filter(models.Ambiente.id == id).first()
    if not obj:
        raise HTTPException(404, "Não encontrado")
    _bloquear_se_houver_documentos(
        db, models.Documento.ambiente_id, id, "Há documentos neste ambiente"
    )
    db.delete(obj)
    db.commit()
    return {"ok": True}


# ────────────────────────── Áreas ──────────────────────────

@router.get("/areas", response_model=list[schemas.AreaOut])
def listar_areas(ambiente_id: Optional[int] = None, db: Session = Depends(get_db),
                 _=Depends(get_current_user)):
    q = db.query(models.Area)
    if ambiente_id:
        q = q.filter(models.Area.ambiente_id == ambiente_id)
    return q.order_by(models.Area.nome).all()


@router.post("/areas", response_model=schemas.AreaOut, status_code=201)
def criar_area(data: schemas.AreaCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if not db.query(models.Ambiente).filter(models.Ambiente.id == data.ambiente_id).first():
        raise HTTPException(400, "Ambiente não encontrado")
    obj = models.Area(nome=data.nome, ambiente_id=data.ambiente_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/areas/{id}", response_model=schemas.OkOut)
def deletar_area(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Area).filter(models.Area.id == id).first()
    if not obj:
        raise HTTPException(404, "Não encontrado")
    _bloquear_se_houver_documentos(
        db, models.Documento.area_id, id, "Há documentos nesta área"
    )
    db.delete(obj)
    db.commit()
    return {"ok": True}


# ────────────────────────── Projetos ──────────────────────────

@router.get("/projetos", response_model=list[schemas.ProjetoOut])
def listar_projetos(area_id: Optional[int] = None, db: Session = Depends(get_db),
                    _=Depends(get_current_user)):
    q = db.query(models.Projeto)
    if area_id:
        q = q.filter(models.Projeto.area_id == area_id)
    return q.order_by(models.Projeto.nome).all()


@router.post("/projetos", response_model=schemas.ProjetoOut, status_code=201)
def criar_projeto(data: schemas.ProjetoCreate, db: Session = Depends(get_db),
                  _=Depends(require_admin)):
    if not db.query(models.Area).filter(models.Area.id == data.area_id).first():
        raise HTTPException(400, "Área não encontrada")
    obj = models.Projeto(nome=data.nome, area_id=data.area_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/projetos/{id}", response_model=schemas.OkOut)
def deletar_projeto(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.Projeto).filter(models.Projeto.id == id).first()
    if not obj:
        raise HTTPException(404, "Não encontrado")
    _bloquear_se_houver_documentos(
        db, models.Documento.projeto_id, id, "Há documentos neste projeto"
    )
    db.delete(obj)
    db.commit()
    return {"ok": True}


# ────────────────────────── Tipos de Documento ──────────────────────────

@router.get("/tipos-documento", response_model=list[schemas.TipoDocumentoOut])
def listar_tipos(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.TipoDocumento).order_by(models.TipoDocumento.nome).all()


@router.post("/tipos-documento", response_model=schemas.TipoDocumentoOut, status_code=201)
def criar_tipo(data: schemas.TipoDocumentoCreate, db: Session = Depends(get_db),
               _=Depends(require_admin)):
    obj = models.TipoDocumento(nome=data.nome)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/tipos-documento/{id}", response_model=schemas.OkOut)
def deletar_tipo(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.TipoDocumento).filter(models.TipoDocumento.id == id).first()
    if not obj:
        raise HTTPException(404, "Não encontrado")
    _bloquear_se_houver_documentos(
        db, models.Documento.tipo_documento_id, id, "Há documentos deste tipo"
    )
    db.delete(obj)
    db.commit()
    return {"ok": True}


# ────────────────────────── Campos do Formulário ──────────────────────────

@router.get("/tipos-documento/{tipo_id}/campos", response_model=list[schemas.CampoFormularioOut])
def listar_campos(tipo_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.CampoFormulario).filter(
        models.CampoFormulario.tipo_documento_id == tipo_id
    ).order_by(models.CampoFormulario.ordem).all()


@router.post("/tipos-documento/{tipo_id}/campos",
             response_model=schemas.CampoFormularioOut, status_code=201)
def criar_campo(tipo_id: int, data: schemas.CampoFormularioCreate,
                db: Session = Depends(get_db), _=Depends(require_admin)):
    if not db.query(models.TipoDocumento).filter(models.TipoDocumento.id == tipo_id).first():
        raise HTTPException(400, "Tipo de documento não encontrado")
    if data.tipo == "select" and not data.opcoes:
        raise HTTPException(400, "Campo do tipo 'select' exige ao menos uma opção")
    obj = models.CampoFormulario(
        tipo_documento_id=tipo_id, nome=data.nome,
        tipo=data.tipo, opcoes=data.opcoes, ordem=data.ordem,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/campos/{id}", response_model=schemas.OkOut)
def deletar_campo(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = db.query(models.CampoFormulario).filter(models.CampoFormulario.id == id).first()
    if not obj:
        raise HTTPException(404, "Não encontrado")
    db.query(models.ValorCampo).filter(models.ValorCampo.campo_id == id).delete(
        synchronize_session=False
    )
    db.delete(obj)
    db.commit()
    return {"ok": True}
