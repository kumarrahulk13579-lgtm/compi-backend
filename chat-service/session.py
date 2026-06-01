import os
import json
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SESSION_TTL = 60 * 30  # 30 minutes inactivity timeout

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def _key(conversation_id: int) -> str:
    return f"session:{conversation_id}"


def get(conversation_id: int) -> dict:
    data = _get_client().get(_key(conversation_id))
    if data:
        return json.loads(data)
    return {"fixed": {}, "dynamic": {}, "system": {}}


def save(conversation_id: int, session: dict):
    _get_client().setex(_key(conversation_id), SESSION_TTL, json.dumps(session))


def update_fixed(conversation_id: int, updates: dict):
    session = get(conversation_id)
    session["fixed"].update(updates)
    save(conversation_id, session)


def update_dynamic(conversation_id: int, updates: dict):
    session = get(conversation_id)
    session["dynamic"].update(updates)
    save(conversation_id, session)


def update_system(conversation_id: int, updates: dict):
    session = get(conversation_id)
    session["system"].update(updates)
    save(conversation_id, session)


def clear(conversation_id: int):
    _get_client().delete(_key(conversation_id))
