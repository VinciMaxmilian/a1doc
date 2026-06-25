from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import require_admin, hash_password
import models, schemas

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


def _u(u):
    return {"id": u.id, "username": u.username, "email": u.email, "role": u.role, "is_active": u.is_active}


@router.get("")
def listar(db: Session = Depends(get_db), _=Depends(require_admin)):
    return [_u(u) for u in db.query(models.User).order_by(models.User.id).all()]


@router.post("")
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
    db.add(user); db.commit(); db.refresh(user)
    return _u(user)


@router.put("/{uid}")
def atualizar(uid: int, data: schemas.UsuarioUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
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
    return _u(user)


@router.delete("/{uid}")
def deletar(uid: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    if uid == admin.id:
        raise HTTPException(400, "Não é possível deletar a própria conta")
    user = db.query(models.User).filter(models.User.id == uid).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    db.delete(user); db.commit()
    return {"ok": True}
