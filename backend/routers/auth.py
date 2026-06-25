from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from auth import hash_password, verify_password, create_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_dict(u):
    return {"id": u.id, "username": u.username, "email": u.email, "role": u.role}


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": _user_dict(user)}


@router.post("/registrar")
def registrar(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(400, "Username já existe")
    user = models.User(
        username=data.username, email=data.email,
        hashed_password=hash_password(data.password), role=data.role
    )
    db.add(user); db.commit(); db.refresh(user)
    return _user_dict(user)


@router.get("/me")
def me(user: models.User = Depends(get_current_user)):
    return _user_dict(user)
