from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from indoc.core.database import Base


class Ambiente(Base):
    __tablename__ = "ambientes"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    areas = relationship("Area", back_populates="ambiente", cascade="all, delete-orphan")


class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    ambiente_id = Column(Integer, ForeignKey("ambientes.id"), nullable=False)
    ambiente = relationship("Ambiente", back_populates="areas")
    projetos = relationship("Projeto", back_populates="area", cascade="all, delete-orphan")


class Projeto(Base):
    __tablename__ = "projetos"
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)
    area = relationship("Area", back_populates="projetos")
