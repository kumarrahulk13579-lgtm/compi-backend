from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey, func
from .base import Base

class Trace(Base):
    __tablename__ = "traces"

    id = Column(Integer, primary_key=True)
    trace_id = Column(String, nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    step = Column(String, nullable=False)
    input = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)
    duration_ms = Column(Float, nullable=True)
    cost_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
