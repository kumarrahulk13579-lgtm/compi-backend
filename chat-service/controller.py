from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from db.models.conversation import Conversation
from db.models.message import Message


def create_conversation(user_id: int, title: str, db: Session):
    conversation = Conversation(user_id=user_id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversations(user_id: int, db: Session):
    return db.query(Conversation).filter_by(user_id=user_id).all()


def send_message(conversation_id: int, user_id: int, content: str, db: Session):
    conversation = db.query(Conversation).filter_by(id=conversation_id, user_id=user_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    user_message = Message(conversation_id=conversation_id, role="user", content=content)
    db.add(user_message)

    assistant_message = Message(conversation_id=conversation_id, role="assistant", content=content)
    db.add(assistant_message)

    db.commit()
    db.refresh(assistant_message)
    return assistant_message


def get_messages(conversation_id: int, user_id: int, db: Session):
    conversation = db.query(Conversation).filter_by(id=conversation_id, user_id=user_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return db.query(Message).filter_by(conversation_id=conversation_id).all()
