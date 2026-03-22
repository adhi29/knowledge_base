"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.storage.database import init_db
from src.api.routes.auth_routes import router as auth_router
from src.api.routes.chat import router as chat_router
from src.api.routes.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    init_db()
    print("✓ Database initialized")
    yield


app = FastAPI(
    title="Banking Knowledge Chatbot API",
    description="AI-powered RAG chatbot for Citi Banking Operations",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(admin_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "banking-chatbot-poc"}
