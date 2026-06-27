from sqlalchemy import Column, Integer, String, Numeric, DateTime, UniqueConstraint, func
from .base import Base

class Limit(Base):
    __tablename__ = "limits"
    __table_args__ = (
        UniqueConstraint("scope", "unit", name="uq_limits_scope_unit"),
    )

    id = Column(Integer, primary_key=True)
    scope = Column(String, nullable=False)      # 'user_guest' | 'user_registered' | 'global_guest'
    unit = Column(String, nullable=False, server_default="cost_usd")   # future: 'tokens'
    amount = Column(Numeric(10, 4), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, nullable=True)  # admin user id (no FK; keep simple)
