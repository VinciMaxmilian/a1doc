
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from auth import hash_password, require_admin
from database import get_db

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("", response_model=list[schemas.UsuarioAdminOut])
def listar(db: Session = Depends(get_db), _=Depends(require_admin)):
    return db.query(models.User).order_by(models.User.id).all()


@router.post("", response_model=schemas.UsuarioAdminOut, status_code=201)
def criar(data: schemas.UsuarioCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(400, "Username já existe")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(400, "Email já existe")
    user = models.User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{uid}", response_model=schemas.UsuarioAdminOut)
def atualizar(uid: int, data: schemas.UsuarioUpdate, db: Session = Depends(get_db),
              admin=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == uid).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    if uid == admin.id:
        raise HTTPException(400, "Não é possível alterar a própria conta aqui")
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{uid}", response_model=schemas.OkOut)
def deletar(uid: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    if uid == admin.id:
        raise HTTPException(400, "Não é possível deletar a própria conta")
    user = db.query(models.User).filter(models.User.id == uid).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    if db.query(models.Documento).filter(models.Documento.responsavel_id == uid).first():
        raise HTTPException(
            400, "Usuário é responsável por documentos; desative a conta em vez de excluir"
        )
    db.delete(user)
    db.commit()
    return {"ok": True}
