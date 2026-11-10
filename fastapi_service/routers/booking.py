import hashlib
import hmac
import logging
import os
import time
from typing import Optional, Union

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..database import db

logger = logging.getLogger(__name__)

router = APIRouter()

TOKEN_MAX_AGE_SECONDS = 120


def _get_lock_secret() -> str:
    return os.getenv("INTERNAL_LOCK_SECRET", "dev-internal-lock-secret")


def verify_internal_token(token: Optional[str]) -> str:
    """Verify HMAC token formatted as '<timestamp>:<user_id>:<signature>'."""
    secret = _get_lock_secret()
    if not token or not secret:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    parts = token.split(":")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid token format")

    ts_str, user_id, provided_sig = parts
    try:
        ts = int(ts_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token timestamp")

    if abs(int(time.time()) - ts) > TOKEN_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Token expired")

    payload = f"{ts_str}:{user_id}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    return user_id


class LockRequest(BaseModel):
    court_id: Union[int, str]
    date: str
    start_time: str
    end_time: Optional[str] = None


@router.post("/api/v1/lock-slot/")
async def lock_court_slot(
    req: LockRequest,
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
):
    verified_user_id = verify_internal_token(x_internal_token)

    redis = db.redis_client
    if not redis:
        raise HTTPException(status_code=500, detail="Redis not connected")

    lock_key = f"lock:court_{req.court_id}_{req.date}_{req.start_time}"
    logger.debug("Attempting lock for key=%s user_id=%s", lock_key, verified_user_id)

    acquired = await redis.set(lock_key, str(verified_user_id), ex=600, nx=True)
    if acquired:
        return {"status": "success", "message": "Đã khóa sân"}

    current_holder = await redis.get(lock_key)
    if current_holder and str(current_holder) == str(verified_user_id):
        await redis.expire(lock_key, 600)
        return {"status": "success", "message": "Gia hạn thành công"}

    raise HTTPException(status_code=409, detail="Sân này vừa có người khác giữ chỗ!")
