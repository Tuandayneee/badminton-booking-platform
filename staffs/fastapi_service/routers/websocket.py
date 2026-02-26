from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..database import db
import asyncio

router = APIRouter()

@router.websocket("/ws/court-status/{center_id}")
async def court_status_websocket(websocket: WebSocket, center_id: int):
    await websocket.accept()
    if not db.redis_client:
        await websocket.close()
        return

    pubsub = db.redis_client.pubsub()
    channel_name = f"center_{center_id}_updates"
    await pubsub.subscribe(channel_name)
    
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                await websocket.send_text(message['data'])
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        await pubsub.unsubscribe(channel_name)