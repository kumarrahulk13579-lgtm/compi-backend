from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import get_db
from middleware import verify_token
import controller

router = APIRouter()


class ConversationRequest(BaseModel):
    title: str


class MessageRequest(BaseModel):
    content: str


@router.post("/conversations")
def create_conversation(body: ConversationRequest, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    return controller.create_conversation(int(token["sub"]), body.title, db)


@router.get("/conversations")
def get_conversations(db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    return controller.get_conversations(int(token["sub"]), db)


@router.post("/conversations/{conversation_id}/messages")
def send_message(conversation_id: int, body: MessageRequest, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    return controller.send_message(conversation_id, int(token["sub"]), body.content, db)


@router.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: int, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    return controller.get_messages(conversation_id, int(token["sub"]), db)
