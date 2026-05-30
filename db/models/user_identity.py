from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from .base import Base

class UserIdentity(Base):
    __tablename__ = "user_identities"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False)       # "email", "google", etc.
    provider_user_id = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)   # only for "email" provider
    created_at = Column(DateTime, server_default=func.now())
