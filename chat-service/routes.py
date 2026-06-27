from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from models import get_db
from middleware import verify_token, require_role
import controller
import agent
import spend

router = APIRouter()


class ConversationRequest(BaseModel):
    title: str


class MessageRequest(BaseModel):
    content: str


class LimitUpdate(BaseModel):
    """Set one or more consumption caps (USD). Omit a field to leave it unchanged."""
    model_config = ConfigDict(extra="forbid")

    user_guest: float | None = Field(default=None, ge=0)
    user_registered: float | None = Field(default=None, ge=0)
    global_guest: float | None = Field(default=None, ge=0)
    global_total: float | None = Field(default=None, ge=0)


@router.post("/conversations")
def create_conversation(body: ConversationRequest, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    return controller.create_conversation(int(token["sub"]), body.title, db)


@router.get("/conversations")
def get_conversations(db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    return controller.get_conversations(int(token["sub"]), db)


@router.post("/conversations/{conversation_id}/messages")
def send_message(conversation_id: int, body: MessageRequest, token: dict = Depends(verify_token)):
    user_id = int(token["sub"])
    is_registered = bool(token.get("is_registered", False))

    # Pre-turn gate: block already-over users with a real HTTP status before streaming.
    allowed, info = spend.check_allowed(user_id, is_registered)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"scope": info.get("scope"), "message": info.get("message")},
        )

    return StreamingResponse(
        agent.run(body.content, conversation_id, user_id, is_registered),
        media_type="text/event-stream",
    )


@router.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: int, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    return controller.get_messages(conversation_id, int(token["sub"]), db)


@router.get("/me/usage")
def my_usage(token: dict = Depends(verify_token)):
    return spend.usage_snapshot(int(token["sub"]), bool(token.get("is_registered", False)))


@router.get("/admin/limits")
def admin_get_limits(db: Session = Depends(get_db), admin: dict = Depends(require_role("admin"))):
    return controller.get_limits(db)


@router.put("/admin/limits")
def admin_update_limits(body: LimitUpdate, db: Session = Depends(get_db), admin: dict = Depends(require_role("admin"))):
    updates = body.model_dump(exclude_none=True)
    return controller.update_limits(updates, int(admin["sub"]), db)
