import os
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import db
from .routers import booking, search

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI service starting up")
    await db.connect()
    yield
    logger.info("FastAPI service shutting down")
    await db.disconnect()


app = FastAPI(title="BadmintonPro Realtime Service", lifespan=lifespan)

cors_origins_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000",
)
allowed_origins = [
    origin.strip()
    for origin in cors_origins_raw.split(",")
    if origin.strip() and origin.strip() != "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Internal-Token"],
)

app.include_router(search.router)
app.include_router(booking.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "FastAPI Badminton Service"}
