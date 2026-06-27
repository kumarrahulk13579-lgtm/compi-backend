"""Consumption tracking + limit checks, backed by Redis counters.

Spend is recorded through tracer.log() (the single cost site). Limits live in the
DB `limits` table (admin-editable) and are cached in Redis. Counters are keyed by
UTC date so they reset daily for free.
"""
import os
import sys
import json
import logging
from datetime import datetime, timezone

import redis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SessionLocal
from db.models.limits import Limit

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SPEND_TTL = 60 * 60 * 48          # 48h — reclaims yesterday's keys
LIMITS_CACHE_KEY = "limits:cfg"
LIMITS_CACHE_TTL = 60

# Fail-closed default for the guest global backstop if config/redis is unavailable.
DEFAULT_GLOBAL_GUEST = 10.00

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _user_key(user_id: int) -> str:
    return f"spend:user:{user_id}:{_today()}"


def _global_key() -> str:
    return f"spend:guest:global:{_today()}"


def _total_key() -> str:
    return f"spend:total:{_today()}"


def _incr(key: str, amount: float):
    client = _get_client()
    total = client.incrbyfloat(key, amount)
    # set expiry only if not already set (atomic NX) — avoids sliding window / leaked keys
    client.expire(key, SPEND_TTL, nx=True)
    return total


# ---- recording -------------------------------------------------------------

def record(user_id: int, is_registered: bool, cost_usd: float) -> None:
    """Accumulate spend. Best-effort: never raises into the request path."""
    if not cost_usd:
        return
    try:
        _incr(_user_key(user_id), cost_usd)
        _incr(_total_key(), cost_usd)          # every user counts toward the overall ceiling
        if not is_registered:
            _incr(_global_key(), cost_usd)
    except Exception:
        logger.warning("spend.record failed", exc_info=True)


# ---- limits config ---------------------------------------------------------

def _load_limits_from_db() -> dict:
    db = SessionLocal()
    try:
        rows = db.query(Limit).filter_by(unit="cost_usd").all()
        return {r.scope: float(r.amount) for r in rows}
    finally:
        db.close()


def get_limits() -> dict:
    client = _get_client()
    try:
        cached = client.get(LIMITS_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception:
        logger.warning("limits cache read failed", exc_info=True)
    cfg = _load_limits_from_db()
    try:
        client.setex(LIMITS_CACHE_KEY, LIMITS_CACHE_TTL, json.dumps(cfg))
    except Exception:
        pass
    return cfg


def invalidate_limits_cache() -> None:
    try:
        _get_client().delete(LIMITS_CACHE_KEY)
    except Exception:
        pass


# ---- enforcement -----------------------------------------------------------

def _user_scope(is_registered: bool) -> str:
    return "user_registered" if is_registered else "user_guest"


def check_allowed(user_id: int, is_registered: bool) -> tuple[bool, dict]:
    """Returns (allowed, info). Asymmetric failure policy: on Redis/config error,
    fail-open for registered users, fail-closed for guests (the abuse surface)."""
    try:
        limits = get_limits()
        client = _get_client()

        # Overall circuit breaker — total spend across everyone. Applies if configured.
        total_limit = limits.get("global_total")
        if total_limit is not None:
            total_used = float(client.get(_total_key()) or 0)
            if total_used >= total_limit:
                return False, {
                    "scope": "global_total", "limit": total_limit, "used": total_used,
                    "message": "The service is at capacity right now. Please try again later.",
                }

        # Global guest backstop — the real protection against new-browser resets.
        if not is_registered:
            global_limit = limits.get("global_guest")
            if global_limit is None:
                global_limit = DEFAULT_GLOBAL_GUEST   # fail-closed: backstop always on
            global_used = float(client.get(_global_key()) or 0)
            if global_used >= global_limit:
                return False, {
                    "scope": "global_guest", "limit": global_limit, "used": global_used,
                    "message": "Guest capacity has been reached for today. Please sign up to continue.",
                }

        scope = _user_scope(is_registered)
        user_limit = limits.get(scope)
        if user_limit is not None:
            user_used = float(client.get(_user_key(user_id)) or 0)
            if user_used >= user_limit:
                msg = ("You've reached your daily usage limit. It resets tomorrow."
                       if is_registered else
                       "You've reached the guest usage limit. Please sign up to keep chatting.")
                return False, {"scope": scope, "limit": user_limit, "used": user_used, "message": msg}

        return True, {}
    except Exception:
        logger.warning("check_allowed failed; fail-%s for user %s",
                       "open" if is_registered else "closed", user_id, exc_info=True)
        if is_registered:
            return True, {}
        return False, {"scope": "error",
                       "message": "Service is temporarily unavailable. Please try again shortly."}


def usage_snapshot(user_id: int, is_registered: bool) -> dict:
    limits = get_limits()
    client = _get_client()
    scope = _user_scope(is_registered)
    user_limit = limits.get(scope)
    user_used = float(client.get(_user_key(user_id)) or 0)

    out = {
        "period": "day",
        "user": {
            "used": round(user_used, 4),
            "limit": user_limit,
            "remaining": (round(max(user_limit - user_used, 0), 4) if user_limit is not None else None),
            "tier": "registered" if is_registered else "guest",
        },
    }
    if not is_registered:
        global_limit = limits.get("global_guest", DEFAULT_GLOBAL_GUEST)
        global_used = float(client.get(_global_key()) or 0)
        out["global_guest"] = {
            "used": round(global_used, 4),
            "limit": global_limit,
            "remaining": round(max(global_limit - global_used, 0), 4),
        }
    return out
