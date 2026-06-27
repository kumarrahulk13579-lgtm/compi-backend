from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
from .base import Base

class UserIdentity(Base):
    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_user_identities_provider_user"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False)       # "email", "google", "guest"
    provider_user_id = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)   # only for "email" provider
    created_at = Column(DateTime, server_default=func.now())
