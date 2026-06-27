from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from models import get_db
from middleware import verify_token
import controller

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    name: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class UpgradeRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    name: str | None = None


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    return controller.register(body.email, body.password, body.name, db)


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    return controller.login(body.email, body.password, db)


@router.post("/guest")
def guest(db: Session = Depends(get_db)):
    return controller.create_guest(db)


@router.post("/upgrade")
def upgrade(body: UpgradeRequest, db: Session = Depends(get_db), payload: dict = Depends(verify_token)):
    return controller.upgrade_guest(int(payload["sub"]), body.email, body.password, body.name, db)


@router.get("/google")
async def google_login(request: Request):
    return await controller.google_login(request)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    return await controller.google_callback(request, db)
