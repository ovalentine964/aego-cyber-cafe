"""
routes/telegram.py — Telegram webhook for Aego Cyber Cafe.

Endpoints:
  POST /api/telegram/webhook — receive Telegram messages

Handles text, voice, and photo messages. Routes to appropriate service.
Uses python-telegram-bot for sending responses.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from config import cfg
from models import APIResponse

logger = logging.getLogger("aego.routes.telegram")
router = APIRouter(prefix="/api/telegram", tags=["telegram"])

# Conversation state per chat
_conversations: dict[int, dict[str, Any]] = {}

# Telegram Bot API base
_TG_API = "https://api.telegram.org/bot{token}"


def init() -> None:
    """Initialize route dependencies."""
    pass


async def _tg_api(method: str, **kwargs) -> dict:
    """Call Telegram Bot API."""
    if not cfg.TELEGRAM_TOKEN:
        logger.warning("Telegram not configured")
        return {"error": "not_configured"}

    url = f"{_TG_API.format(token=cfg.TELEGRAM_TOKEN)}/{method}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=kwargs)
        resp.raise_for_status()
        return resp.json()


async def _send_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> dict:
    """Send a text message."""
    return await _tg_api(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
    )


async def _send_voice(chat_id: int, audio_path: str, caption: str = "") -> dict:
    """Send a voice/audio message."""
    url = f"{_TG_API.format(token=cfg.TELEGRAM_TOKEN)}/sendVoice"

    async with httpx.AsyncClient(timeout=60) as client:
        with open(audio_path, "rb") as f:
            resp = await client.post(
                url,
                data={
                    "chat_id": chat_id,
                    "caption": caption,
                },
                files={"voice": ("voice.wav", f, "audio/wav")},
            )
            resp.raise_for_status()
            return resp.json()


async def _get_file(file_id: str) -> bytes:
    """Download a file from Telegram."""
    # Get file path
    result = await _tg_api("getFile", file_id=file_id)
    file_path = result.get("result", {}).get("file_path", "")

    if not file_path:
        raise RuntimeError("Could not get file path")

    url = f"https://api.telegram.org/file/bot{cfg.TELEGRAM_TOKEN}/{file_path}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def _detect_intent(text: str) -> str:
    """Detect intent from message text."""
    text_lower = text.lower().strip()

    if text_lower in ("/start", "/menu", "menu", "start"):
        return "greeting"

    keywords = {
        "cv": ["cv", "resume", "cover letter", "barua ya kazi"],
        "gov": ["kra", "ecitizen", "nhif", "nssf", "ntsa", "helb", "serikali"],
        "translate": ["translate", "tarajimu", "tfsiri"],
        "print": ["print", "copy", "scan", "chapisha"],
    }

    for service, kws in keywords.items():
        for kw in kws:
            if kw in text_lower:
                return service

    return "unknown"


def _get_welcome(language: str = "en") -> str:
    """Get welcome message."""
    if language == "sw":
        return (
            "👋 *Karibu Aego Cyber Cafe — Nyatike!*\n\n"
            "Tunatoa huduma zifuatazo:\n\n"
            "📄 CV / Barua ya Kazi — KES 300-450\n"
            "🏛️ Huduma za Serikali — KES 150-300\n"
            "🖨️ Printing / Scan — KES 5-20\n"
            "🌐 Translation — Bure\n\n"
            "Chagua huduma kwa kuandika jina lake au:\n"
            "/cv — CV Services\n"
            "/gov — Government Services\n"
            "/translate — Translation\n"
            "/help — Msaada"
        )
    return (
        "👋 *Welcome to Aego Cyber Cafe — Nyatike!*\n\n"
        "We offer:\n\n"
        "📄 CV / Cover Letter — KES 300-450\n"
        "🏛️ Government Services — KES 150-300\n"
        "🖨️ Printing / Scan — KES 5-20\n"
        "🌐 Translation — Free\n\n"
        "Choose a service by typing its name or:\n"
        "/cv — CV Services\n"
        "/gov — Government Services\n"
        "/translate — Translation\n"
        "/help — Help"
    )


async def _handle_text(chat_id: int, text: str, username: str = "") -> str:
    """Handle incoming text message."""
    conv = _conversations.get(chat_id, {"state": "new", "language": "en"})
    _conversations[chat_id] = conv

    intent = _detect_intent(text)

    if intent == "greeting":
        return _get_welcome(conv.get("language", "en"))

    if intent == "cv":
        return (
            "📄 *CV Writing Service*\n\n"
            "CV tu: KES 300\n"
            "CV + Cover Letter: KES 450\n\n"
            "Tafadhali tuma jina lako kamili kuanza:\n"
            "(Full name as on your ID)"
        )

    if intent == "gov":
        return (
            "🏛️ *Government Services*\n\n"
            "KRA PIN — KES 150\n"
            "eCitizen — KES 150-200\n"
            "NHIF — KES 150-200\n"
            "NSSF — KES 150-200\n"
            "NTSA — KES 300\n"
            "HELB — KES 150-200\n\n"
            "Which service? Type the name (e.g., 'KRA PIN')"
        )

    if intent == "translate":
        return (
            "🌐 *Translation Service*\n\n"
            "Send text and specify target language:\n"
            "🇬🇧 English | 🇰🇪 Swahili | 🇰🇪 Dholuo | 🇰🇪 Kikuyu\n\n"
            "Example: 'Translate to Swahili: I need a job'"
        )

    if intent == "print":
        return (
            "🖨️ *Printing Services*\n\n"
            "Printing: KES 5/page (bw) | KES 10 (color)\n"
            "Copy: KES 5/page\n"
            "Scan: KES 20/page\n\n"
            "Kuja dukani na document yako!"
        )

    # Default
    return (
        "😊 Samahani, sijaelewa.\n\n"
        "Andika 'menu' kuona huduma zote.\n"
        "Or type: cv, gov, translate, print"
    )


async def _handle_voice(chat_id: int, file_id: str) -> tuple[str, str]:
    """Handle voice message. Returns (transcription, response)."""
    try:
        # Download audio
        audio_bytes = await _get_file(file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            # Transcribe
            import subprocess
            proc = subprocess.run(
                ["/usr/local/bin/whisper-cli",
                 "-m", "/home/work/models/ggml-tiny.bin",
                 "-f", tmp_path, "-t", "2", "--no-timestamps"],
                capture_output=True, text=True, timeout=30,
            )
            transcription = proc.stdout.strip() if proc.returncode == 0 else ""
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if not transcription:
            return "", "😊 Sikuelewa voice yako. Tafadhali jaribu tena au andika."

        # Process the transcribed text
        response = await _handle_text(chat_id, transcription)
        return transcription, response

    except Exception as e:
        logger.error(f"Voice handling failed: {e}", exc_info=True)
        return "", "😊 Kuna tatizo la voice. Tafadhali jaribu tena."


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict:
    """Receive incoming Telegram updates."""
    try:
        body = await request.json()
        logger.debug(f"Telegram update: {json.dumps(body, indent=2)}")

        message = body.get("message")
        if not message:
            return {"status": "ok"}

        chat_id = message.get("chat", {}).get("id")
        if not chat_id:
            return {"status": "ok"}

        from_user = message.get("from", {})
        username = from_user.get("username", "")
        text = message.get("text", "")

        # Handle different message types
        if text:
            response = await _handle_text(chat_id, text, username)
            await _send_message(chat_id, response)

        elif "voice" in message:
            file_id = message["voice"]["file_id"]
            transcription, response = await _handle_voice(chat_id, file_id)
            if transcription:
                await _send_message(chat_id, f"🎙️ *Umesema:* {transcription}", "Markdown")
            await _send_message(chat_id, response)

        elif "photo" in message:
            # Photos — get the largest version
            photo = message["photo"][-1]
            await _send_message(
                chat_id,
                "📷 Nimepokea picha yako.\n"
                "Kuja dukani kwa huduma za picha, au nitakusaidia na nini?"
            )

        elif "document" in message:
            await _send_message(
                chat_id,
                "📄 Nimepokea document yako.\n"
                "Kuja dukani kwa printing/scanning!"
            )

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Telegram webhook error: {e}", exc_info=True)
        return {"status": "error"}
