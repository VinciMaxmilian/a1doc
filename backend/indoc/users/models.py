from sqlalchemy import Boolean, Column, DateTime, Integer, String

from indoc.core.database import Base


class User(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Papel legado. A autorização agora é resolvida pela ACL (FASE 1); este
    # campo sobrevive porque `Atividade.role_requerido` ainda o usa como
    # restrição de workflow, e porque a migration 0003 o traduz em perfis.
    # A FASE 11 (responsáveis) deve aposentá-lo.
    role = Column(String(20), default="user")  # dev, admin, user

    is_active = Column(Boolean, default=True)

    # ── FASE 1 ── todos nullable: instalação existente migra sem preencher.
    departamento = Column(String(200), nullable=True)
    cargo = Column(String(200), nullable=True)
    ultimo_login = Column(DateTime, nullable=True)
    bloqueado_em = Column(DateTime, nullable=True)
    motivo_bloqueio = Column(String(500), nullable=True)
