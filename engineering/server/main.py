"""
main.py — FastAPI application for Aego Cyber Cafe, Nyatike, Migori County, Kenya.

Lightweight server that ties together all services:
  - CV writing
  - Government services (KRA, eCitizen, NHIF, NSSF, NTSA, HELB)
  - Translation (English, Swahili, Dholuo, Kikuyu)
  - Voice pipeline (Whisper STT + Piper TTS + Ollama LLM)
  - M-Pesa payments
  - WhatsApp & Telegram bots
  - Staff admin dashboard

Designed for Raspberry Pi 5 (8GB RAM) — minimal memory footprint.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import cfg
from session_manager import SessionManager
from queue import RequestQueue

# ── Logging Setup ─────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("aego")

# ── Shared State ──────────────────────────────────────────────

session_mgr = SessionManager(ttl_seconds=cfg.SESSION_TTL_MINUTES * 60)
request_queue = RequestQueue(timeout=cfg.QUEUE_TIMEOUT, max_retries=cfg.QUEUE_MAX_RETRIES)

# ── Lifespan Handler ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    logger.info("=" * 60)
    logger.info("  🅰️  Aego Cyber Cafe — Server Starting")
    logger.info(f"  📍 Nyatike, Migori County, Kenya")
    logger.info(f"  🤖 Ollama: {cfg.OLLAMA_HOST} ({cfg.OLLAMA_MODEL})")
    logger.info(f"  📂 Data: {cfg.DATA_DIR}")
    logger.info(f"  📂 Output: {cfg.OUTPUT_DIR}")
    logger.info("=" * 60)

    # Ensure directories
    cfg.ensure_dirs()

    # Start request queue processor
    queue_task = asyncio.create_task(request_queue.run())

    # Initialize route modules
    _init_routes()

    # Warm up Ollama connection (non-blocking check)
    asyncio.create_task(_check_ollama())

    logger.info("Server ready — accepting connections")

    yield

    # Shutdown
    logger.info("Server shutting down...")
    await request_queue.shutdown()
    queue_task.cancel()
    try:
        await queue_task
    except asyncio.CancelledError:
        pass
    logger.info("Server stopped")


def _init_routes() -> None:
    """Initialize all route modules with their dependencies."""
    from routes import cv, gov, translate, voice, mpesa, admin, whatsapp, telegram

    cv.init(session_mgr, cfg.SKILLS_DIR, cfg.OUTPUT_DIR)
    gov.init(session_mgr, cfg.SKILLS_DIR, cfg.OUTPUT_DIR)
    translate.init(request_queue)
    voice.init(request_queue, cfg.VOICE_CONFIG)
    mpesa.init()
    admin.init(session_mgr)
    whatsapp.init()
    telegram.init()

    logger.info("All route modules initialized")


async def _check_ollama() -> None:
    """Check Ollama availability at startup."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{cfg.OLLAMA_HOST}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]
                logger.info(f"Ollama connected — models: {model_names}")
            else:
                logger.warning(f"Ollama responded with status {resp.status_code}")
    except Exception as e:
        logger.warning(f"Ollama not reachable: {e} — LLM features will fail")


# ── FastAPI Application ──────────────────────────────────────

app = FastAPI(
    title="Aego Cyber Cafe API",
    description=(
        "Backend API for Aego Cyber Cafe, Nyatike, Migori County, Kenya.\n\n"
        "Services: CV writing, government forms, translation, voice assistant, "
        "M-Pesa payments, WhatsApp/Telegram bots."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Logging Middleware ────────────────────────────────

@app.middleware("http")
async def logging_middleware(request: Request, call_next) -> Response:
    """Log every request with method, path, status, and duration."""
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000

    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} ({elapsed:.0f}ms)"
    )

    return response


# ── Error Handling Middleware ─────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all error handler — never leak internal details."""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error. Please try again.",
            "data": None,
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": "Endpoint not found.",
            "data": None,
        },
    )


# ── Mount Route Modules ──────────────────────────────────────

from routes import cv, gov, translate, voice, mpesa, admin, whatsapp, telegram

app.include_router(cv.router)
app.include_router(gov.router)
app.include_router(translate.router)
app.include_router(voice.router)
app.include_router(mpesa.router)
app.include_router(admin.router)
app.include_router(whatsapp.router)
app.include_router(telegram.router)


# ── Health Check ──────────────────────────────────────────────

@app.get("/api/health", tags=["system"])
async def health_check() -> dict:
    """
    Health check endpoint.
    Returns server status, queue state, and active sessions.
    """
    import httpx

    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{cfg.OLLAMA_HOST}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "Aego Cyber Cafe API",
        "version": "1.0.0",
        "ollama": "connected" if ollama_ok else "unreachable",
        "model": cfg.OLLAMA_MODEL,
        "queue": request_queue.status(),
        "active_sessions": await session_mgr.count_active(),
    }


# ── Static File Serving for Kiosk UI ─────────────────────────

kiosk_path = Path(cfg.KIOSK_DIR)
if kiosk_path.exists():
    app.mount("/kiosk", StaticFiles(directory=str(kiosk_path), html=True), name="kiosk")
    logger.info(f"Kiosk UI mounted at /kiosk/ ({kiosk_path})")
else:
    logger.warning(f"Kiosk directory not found: {kiosk_path}")


# ── Root Redirect ─────────────────────────────────────────────

@app.get("/", tags=["system"])
async def root() -> dict:
    """Root endpoint — service info."""
    return {
        "service": "Aego Cyber Cafe API",
        "location": "Nyatike, Migori County, Kenya",
        "version": "1.0.0",
        "docs": "/docs",
        "kiosk": "/kiosk/",
        "health": "/api/health",
    }


# ── Run ──────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=cfg.HOST,
        port=cfg.PORT,
        workers=cfg.WORKERS,
        log_level=cfg.LOG_LEVEL,
        access_log=False,  # We handle logging ourselves
    )
