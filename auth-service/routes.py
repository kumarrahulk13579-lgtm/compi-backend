from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import get_db
import controller

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    return controller.register(body.email, body.password, body.name, db)


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    return controller.login(body.email, body.password, db)


@router.get("/google")
async def google_login(request: Request):
    return await controller.google_login(request)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    return await controller.google_callback(request, db)
