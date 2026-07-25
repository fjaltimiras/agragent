import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from app.routers import chat, conversations, uploads, detect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Agro Agent started")
    logger.info("Routers: /api/chat, /api/conversations, /api/upload")
    yield
    logger.info("Agro Agent shutting down")


app = FastAPI(
    title="agragent API",
    description="API para el agente agrónomo conversacional con IA",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversations"])
app.include_router(uploads.router, prefix="/api/upload", tags=["Uploads"])
app.include_router(detect.router, prefix="/api/detect", tags=["Detection"])


@app.get("/", tags=["Root"])
async def root():
    """API root — redirect to docs or show status."""
    return {
        "service": "agragent API",
        "version": "1.0.0",
        "endpoints": ["/api/chat", "/api/detect", "/api/conversations", "/api/upload", "/health"],
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "agragent API",
        "version": "1.0.0",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler — returns JSON error response for unexpected errors."""
    logger.error(f"Unhandled exception on {request.method} {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "detail": str(exc),
            "path": str(request.url),
        },
    )
