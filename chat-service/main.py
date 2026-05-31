import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from contextlib import asynccontextmanager
from routes import router
import tool_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    tool_registry.register_all_tools()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(router, prefix="/chat")
