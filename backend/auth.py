from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import models
from config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from database import get_db

ADMIN_ROLES = ("admin", "dev")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(pw: str) -> str:
    # bcrypt trunca em 72 bytes; truncar explicitamente evita ValueError em senhas longas.
    return _bcrypt.hashpw(pw.encode("utf-8")[:72], _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    data = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        # `from None`: o motivo exato da falha do token não vai para o cliente.
        raise HTTPException(status_code=401, detail="Token inválido") from None
    user = db.query(models.User).filter(
        models.User.id == uid, models.User.is_active.is_(True)
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


def is_admin(user: models.User) -> bool:
    return user.role in ADMIN_ROLES


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Acesso restrito a Admin/Dev")
    return user
