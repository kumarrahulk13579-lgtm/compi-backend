from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector
from .base import Base

class Tool(Base):
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=False)
    description_hash = Column(String, nullable=False)
    parameters = Column(JSON, nullable=False, default={})
    state_schema = Column(JSON, nullable=False, default={})
    response_types = Column(JSON, nullable=False, default=["text"])
    enabled = Column(Boolean, default=True)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, server_default=func.now())
