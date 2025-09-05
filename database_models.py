from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///database/game.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

# Модель игрока
class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    score = Column(Integer, default=0)
    is_leader = Column(Boolean, default=False)

# Модель игры
class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, index=True)
    current_round = Column(Integer, default=0)

# Инициализация БД
def init_db():
    Base.metadata.create_all(bind=engine)
