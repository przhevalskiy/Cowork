from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.api.routes import chat_router, discussions_router, hive_router, attachments_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print("Starting Cowork API server...")
    print(f"Debug mode: {settings.debug}")
    print(f"CORS origins: {settings.cors_origins_list}")
    print(f"Claude: {'configured' if settings.anthropic_api_key else 'missing API key'}")

    yield

    print("Shutting down Cowork API server...")


app = FastAPI(
    title="Cowork API",
    description="Marketing Communications Intake API",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(discussions_router)
app.include_router(hive_router)
app.include_router(attachments_router)


@app.get("/")
async def root():
    return {
        "name": "Cowork API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "healthy",
        "providers": {
            "claude": bool(settings.anthropic_api_key),
        },
    }
