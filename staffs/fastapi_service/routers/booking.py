from fastapi import APIRouter, HTTPException, Body
from ..database import db
from pydantic import BaseModel
from typing import Union
import asyncio

router = APIRouter()

class LockRequest(BaseModel):
    court_id: Union[int, str] 
    date: str
    start_time: str
    end_time: str
    user_id: Union[int, str]  

@router.post("/api/v1/lock-slot/")
async def lock_court_slot(req: LockRequest):
    redis = db.redis_client
    if not redis:
        raise HTTPException(status_code=500, detail="Redis not connected")
    
    lock_key = f"lock:court_{req.court_id}_{req.date}_{req.start_time}"
    print(f"👉 FASTAPI KEY: {lock_key}")

    current_holder = await redis.get(lock_key)
    if current_holder:
        # So sánh User ID 
        if str(current_holder) != str(req.user_id):
            raise HTTPException(status_code=409, detail="Sân này vừa có người khác giữ chỗ!")
        
        await redis.expire(lock_key, 600)
        return {"status": "success", "message": "Gia hạn thành công"}

    # Set lock
    await redis.setex(lock_key, 600, str(req.user_id))
    return {"status": "success", "message": "Đã khóa sân"}