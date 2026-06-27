from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from db.models.conversation import Conversation
from db.models.message import Message
from db.models.limits import Limit
import spend

VALID_SCOPES = {"user_guest", "user_registered", "global_guest", "global_total"}



def create_conversation(user_id: int, title: str, db: Session):
    conversation = Conversation(user_id=user_id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversations(user_id: int, db: Session):
    return db.query(Conversation).filter_by(user_id=user_id).all()



def get_messages(conversation_id: int, user_id: int, db: Session):
    conversation = db.query(Conversation).filter_by(id=conversation_id, user_id=user_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return db.query(Message).filter_by(conversation_id=conversation_id).all()


def get_limits(db: Session):
    rows = db.query(Limit).order_by(Limit.scope).all()
    return [
        {"scope": r.scope, "unit": r.unit, "amount": float(r.amount), "updated_at": r.updated_at}
        for r in rows
    ]


def update_limits(updates: dict, admin_id: int, db: Session):
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided")
    for scope, amount in updates.items():
        if scope not in VALID_SCOPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown scope: {scope}")
        if amount is None or float(amount) < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid amount for {scope}")

    for scope, amount in updates.items():
        row = db.query(Limit).filter_by(scope=scope, unit="cost_usd").first()
        if row is None:
            row = Limit(scope=scope, unit="cost_usd", amount=amount)
            db.add(row)
        else:
            row.amount = amount
        row.updated_by = admin_id
    db.commit()

    spend.invalidate_limits_cache()
    return get_limits(db)
