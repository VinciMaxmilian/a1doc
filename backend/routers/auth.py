from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import models
import schemas
from auth import create_token, get_current_user, hash_password, require_admin, verify_password
from database import get_db
from indoc.permissions.seed import atribuir_perfil_padrao

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuário inativo")
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": user}


@router.post("/registrar", response_model=schemas.UsuarioOut, status_code=201)
def registrar(data: schemas.UsuarioCreate, db: Session = Depends(get_db),
              _: models.User = Depends(require_admin)):
    """Criação de usuário restrita a Admin/Dev (evita escalação de privilégio)."""
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(400, "Username já existe")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(400, "Email já existe")
    user = models.User(
        username=data.username, email=data.email,
        hashed_password=hash_password(data.password), role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # A ACL é default-deny: sem perfil o usuário nasceria sem poder nada.
    atribuir_perfil_padrao(db, user)
    return user


@router.get("/me", response_model=schemas.UsuarioOut)
def me(user: models.User = Depends(get_current_user)):
    return user
