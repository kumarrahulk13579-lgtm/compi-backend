import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from routes import router

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("JWT_SECRET_KEY"))

app.include_router(router, prefix="/auth")
