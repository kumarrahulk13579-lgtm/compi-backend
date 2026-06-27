from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, text
from .base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=True)   # nullable: guests have no email
    name = Column(String, nullable=True)
    role = Column(String, nullable=False, server_default="user")          # "admin" | "user"
    is_registered = Column(Boolean, nullable=False, server_default=text("false"))  # guest=false
    created_at = Column(DateTime, server_default=func.now())
