from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from db.models.base import Base


class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    goal = Column(Text, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, server_default=func.now())


class PlanStep(Base):
    __tablename__ = "plan_steps"
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    depends_on = Column(Text, nullable=True)  # JSON list of earlier step_numbers
    status = Column(String, default="pending")
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
