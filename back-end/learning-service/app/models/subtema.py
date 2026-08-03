from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Materia(Base):
    __tablename__ = "materia"

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)

    temas = relationship("Tema", back_populates="materia")


class Tema(Base):
    __tablename__ = "tema"

    id = Column(Integer, primary_key=True)
    materia_id = Column(Integer, ForeignKey("materia.id"))
    nome = Column(String(100), nullable=False)
    ordem = Column(Integer, nullable=False, default=0)

    materia = relationship("Materia", back_populates="temas")
    subtemas = relationship("Subtema", back_populates="tema")


class Subtema(Base):
    __tablename__ = "subtema"

    id = Column(Integer, primary_key=True)
    tema_id = Column(Integer, ForeignKey("tema.id"))
    nome = Column(String(100), nullable=False)
    ordem = Column(Integer, nullable=False, default=0)
    videoaula_base_url = Column(String(255), nullable=True)
    videoaula_revisao_url = Column(String(255), nullable=True)
    # Texto rico em palavras-chave (não exibido ao aluno) usado só para dar
    # sinal semântico ao classificador de IA (embeddings). Ex: para
    # "Membrana Plasmática" -> "bicamada lipídica, transporte, osmose,
    # difusão, bomba de sódio e potássio, permeabilidade seletiva".
    descricao_ia = Column(Text, nullable=True)

    tema = relationship("Tema", back_populates="subtemas")
