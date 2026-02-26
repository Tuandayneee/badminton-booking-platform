from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware



# Import db và routers
from .database import db
from .routers import search, websocket, booking

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("FastAPI: Starting up...")
    await db.connect()
    yield
    # Shutdown
    print("FastAPI: Shutting down...")
    await db.disconnect()

app = FastAPI(lifespan=lifespan)

# Cấu hình CORS (Để Frontend gọi được API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000", 
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "*"  
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(search.router)
app.include_router(websocket.router)
app.include_router(booking.router)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "FastAPI Badminton Service"}