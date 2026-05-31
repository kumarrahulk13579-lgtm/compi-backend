from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from pgvector.sqlalchemy import Vector
from .base import Base

class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, server_default=func.now())
