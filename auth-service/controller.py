import os
import jwt
from datetime import datetime, timedelta, timezone
import bcrypt
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse
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


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_token(user_id: int, *, role: str, is_registered: bool) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "is_registered": is_registered,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _email_in_use(email: str, db: Session, exclude_user_id: int | None = None) -> bool:
    """True if `email` already belongs to some account (email identity or users.email)."""
    if db.query(UserIdentity).filter_by(provider="email", provider_user_id=email).first():
        return True
    q = db.query(User).filter(User.email == email)
    if exclude_user_id is not None:
        q = q.filter(User.id != exclude_user_id)
    return q.first() is not None


def register(email: str, password: str, name: str, db: Session):
    email = normalize_email(email)
    if _email_in_use(email, db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, name=name, role="user", is_registered=True)
    db.add(user)
    db.flush()

    identity = UserIdentity(
        user_id=user.id,
        provider="email",
        provider_user_id=email,
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
    )
    db.add(identity)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    return {"token": create_token(user.id, role=user.role, is_registered=user.is_registered)}


def login(email: str, password: str, db: Session):
    email = normalize_email(email)
    identity = db.query(UserIdentity).filter_by(provider="email", provider_user_id=email).first()
    if not identity or not bcrypt.checkpw(password.encode(), identity.password_hash.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = db.get(User, identity.user_id)
    return {"token": create_token(user.id, role=user.role, is_registered=user.is_registered)}


def create_guest(db: Session):
    user = User(email=None, name=None, role="user", is_registered=False)
    db.add(user)
    db.flush()

    identity = UserIdentity(user_id=user.id, provider="guest")
    db.add(identity)
    db.commit()

    return {"token": create_token(user.id, role=user.role, is_registered=user.is_registered)}


def upgrade_guest(user_id: int, email: str, password: str, name: str | None, db: Session):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.is_registered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already registered")

    email = normalize_email(email)
    if _email_in_use(email, db, exclude_user_id=user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    user.email = email
    user.name = name or user.name
    user.is_registered = True
    db.add(UserIdentity(
        user_id=user.id,
        provider="email",
        provider_user_id=email,
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    return {"token": create_token(user.id, role=user.role, is_registered=user.is_registered)}


async def google_login(request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    return await oauth.google.authorize_redirect(request, redirect_uri)


async def google_callback(request, db: Session):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")

    identity = db.query(UserIdentity).filter_by(provider="google", provider_user_id=user_info["sub"]).first()

    if not identity:
        user = User(
            email=normalize_email(user_info["email"]),
            name=user_info.get("name"),
            role="user",
            is_registered=True,
        )
        db.add(user)
        db.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider="google",
            provider_user_id=user_info["sub"],
        )
        db.add(identity)
        db.commit()
    else:
        user = db.get(User, identity.user_id)

    token_str = create_token(user.id, role=user.role, is_registered=user.is_registered)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(url=f"{frontend_url}/auth/callback?token={token_str}")
