from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from .base import Base

class Usage(Base):
    __tablename__ = "usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cost_usd = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
