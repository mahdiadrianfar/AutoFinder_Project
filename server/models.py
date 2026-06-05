import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

from server.database.connection import engine

Base = declarative_base()


class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(1024), unique=True, nullable=False, index=True)
    title = Column(String(512), nullable=True)
    price = Column(String(128), nullable=True)
    price_value = Column(Integer, nullable=True)
    location = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    source = Column(String(64), nullable=True, default="divar")
    scraped_at = Column(DateTime(timezone=True),
                        default=datetime.datetime.utcnow)
    raw_data = Column(Text, nullable=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
