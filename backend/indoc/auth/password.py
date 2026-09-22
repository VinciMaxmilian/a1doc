"""Hash de senha. Extraído de `backend/auth.py` na FASE 2."""
import bcrypt as _bcrypt


def hash_password(pw: str) -> str:
    # bcrypt trunca em 72 bytes; truncar explicitamente evita ValueError em senhas longas.
    return _bcrypt.hashpw(pw.encode("utf-8")[:72], _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False
