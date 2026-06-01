import os
import jwt
from datetime import datetime, timedelta, timezone
import bcrypt
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from authlib.integrations.starlette_client import OAuth

from db.models.user import User
from db.models.user_identity import UserIdentity

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def register(email: str, password: str, name: str, db: Session):
    existing = db.query(UserIdentity).filter_by(provider="email", provider_user_id=email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(email=email, name=name)
    db.add(user)
    db.flush()

    identity = UserIdentity(
        user_id=user.id,
        provider="email",
        provider_user_id=email,
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
    )
    db.add(identity)
    db.commit()

    return {"token": create_token(user.id)}


def login(email: str, password: str, db: Session):
    identity = db.query(UserIdentity).filter_by(provider="email", provider_user_id=email).first()
    if not identity or not bcrypt.checkpw(password.encode(), identity.password_hash.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return {"token": create_token(identity.user_id)}


async def google_login(request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    return await oauth.google.authorize_redirect(request, redirect_uri)


async def google_callback(request, db: Session):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")

    identity = db.query(UserIdentity).filter_by(provider="google", provider_user_id=user_info["sub"]).first()

    if not identity:
        user = User(email=user_info["email"], name=user_info.get("name"))
        db.add(user)
        db.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider="google",
            provider_user_id=user_info["sub"],
        )
        db.add(identity)
        db.commit()

    return {"token": create_token(identity.user_id)}
