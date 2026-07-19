"""
routes/whatsapp.py — WhatsApp Business Cloud API webhook for Aego Cyber Cafe.

Endpoints:
  POST /api/whatsapp/webhook — receive incoming WhatsApp messages
  GET  /api/whatsapp/webhook — webhook verification (Meta challenge)

Handles text, voice notes, and images. Routes to appropriate service.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from config import cfg
from models import APIResponse

logger = logging.getLogger("aego.routes.whatsapp")
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

# Conversation state per phone number (in-memory, ephemeral)
_conversations: dict[str, dict[str, Any]] = {}

# Service keywords for routing
SERVICE_KEYWORDS = {
    "cv": ["cv", "resume", "cover letter", "barua ya kazi", "wasifu"],
    "gov": ["kra", "ecitizen", "nhif", "nssf", "ntsa", "helb", "serikali", "government"],
    "translate": ["translate", "tarajimu", "targuma", "tfsiri"],
    "print": ["print", "copy", "scan", "chapisha", "nakala"],
    "photo": ["photo", "picha", "passport"],
    "menu": ["menu", "menyu", "huduma", "services", "help", "msaada"],
}


def init() -> None:
    """Initialize route dependencies."""
    pass


async def _send_whatsapp_message(to: str, text: str) -> dict:
    """Send a text message via WhatsApp Business Cloud API."""
    if not cfg.WHATSAPP_TOKEN or not cfg.WHATSAPP_PHONE_ID:
        logger.warning("WhatsApp not configured — message not sent")
        return {"error": "not_configured"}

    url = f"https://graph.facebook.com/v18.0/{cfg.WHATSAPP_PHONE_ID}/messages"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
            headers={
                "Authorization": f"Bearer {cfg.WHATSAPP_TOKEN}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _send_whatsapp_audio(to: str, audio_path: str) -> dict:
    """Send an audio file via WhatsApp Business Cloud API."""
    if not cfg.WHATSAPP_TOKEN or not cfg.WHATSAPP_PHONE_ID:
        return {"error": "not_configured"}

    # First upload the media
    url = f"https://graph.facebook.com/v18.0/{cfg.WHATSAPP_PHONE_ID}/media"

    async with httpx.AsyncClient(timeout=60) as client:
        # Upload media
        with open(audio_path, "rb") as f:
            resp = await client.post(
                url,
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"messaging_product": "whatsapp", "type": "audio/wav"},
                headers={"Authorization": f"Bearer {cfg.WHATSAPP_TOKEN}"},
            )
            resp.raise_for_status()
            media_id = resp.json().get("id", "")

        if not media_id:
            return {"error": "upload_failed"}

        # Send audio message
        msg_url = f"https://graph.facebook.com/v18.0/{cfg.WHATSAPP_PHONE_ID}/messages"
        resp = await client.post(
            msg_url,
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "audio",
                "audio": {"id": media_id},
            },
            headers={
                "Authorization": f"Bearer {cfg.WHATSAPP_TOKEN}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _download_whatsapp_media(media_id: str) -> bytes:
    """Download media from WhatsApp Business API."""
    if not cfg.WHATSAPP_TOKEN:
        raise RuntimeError("WhatsApp not configured")

    async with httpx.AsyncClient(timeout=30) as client:
        # Get media URL
        resp = await client.get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers={"Authorization": f"Bearer {cfg.WHATSAPP_TOKEN}"},
        )
        resp.raise_for_status()
        media_url = resp.json().get("url", "")

        # Download media
        resp = await client.get(
            media_url,
            headers={"Authorization": f"Bearer {cfg.WHATSAPP_TOKEN}"},
        )
        resp.raise_for_status()
        return resp.content


def _detect_intent(text: str) -> str:
    """Detect customer intent from message text."""
    text_lower = text.lower().strip()

    # Check for numeric menu selection
    if text_lower in ("1", "2", "3", "4", "5", "6", "7"):
        return f"menu_{text_lower}"

    # Check keywords
    for service, keywords in SERVICE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return service

    # Greeting detection
    greetings = ["hi", "hello", "hey", "habari", "niaje", "mambo", "sawa", "maraba"]
    if any(g in text_lower for g in greetings):
        return "greeting"

    return "unknown"


def _detect_language(text: str) -> str:
    """Detect language from text. Returns language code."""
    text_lower = text.lower()
    sw_markers = ["habari", "nzuri", "sana", "naomba", "tafadhali", "asante",
                  "karibu", "sawa", "hapana", "ndiyo", "ninataka", "nataka"]
    luo_markers = ["nyathi", "maber", "amos", "ochieng", "maraba", "nhero", "en ang'o"]
    ki_markers = ["muthuri", "mwarimu", "njira", "niaritha"]

    sw_hits = sum(1 for m in sw_markers if m in text_lower)
    luo_hits = sum(1 for m in luo_markers if m in text_lower)
    ki_hits = sum(1 for m in ki_markers if m in text_lower)

    if sw_hits >= 1:
        return "sw"
    if luo_hits >= 1:
        return "luo"
    if ki_hits >= 1:
        return "ki"
    return "en"


def _get_greeting(language: str) -> str:
    """Get greeting message in detected language."""
    greetings = {
        "en": (
            "👋 Welcome to Aego Cyber Cafe — Nyatike!\n\n"
            "We offer: CV writing, government services (KRA, eCitizen, NHIF), "
            "printing, scanning, and more.\n\n"
            "How can we help you today?\n"
            "1️⃣ CV / Cover Letter\n"
            "2️⃣ Government Services\n"
            "3️⃣ Printing / Scan\n"
            "4️⃣ Translation\n"
            "5️⃣ Other"
        ),
        "sw": (
            "👋 Karibu Aego Cyber Cafe — Nyatike!\n\n"
            "Tunatoa: CV, huduma za serikali (KRA, eCitizen, NHIF), "
            "printing, scanning, na zaidi.\n\n"
            "Tunaweza kukusaidia nini leo?\n"
            "1️⃣ CV / Barua ya Kazi\n"
            "2️⃣ Huduma za Serikali\n"
            "3️⃣ Printing / Scan\n"
            "4️⃣ Translation\n"
            "5️⃣ Nyingineyo"
        ),
        "luo": (
            "👋 Maraba e Aego Cyber Cafe — Nyatike!\n\n"
            "Nyalo gi: CV, tiende mag guok (KRA, eCitizen, NHIF), "
            "printing, scanning, ne moko.\n\n"
            "Ihero tiende ang'o?\n"
            "1️⃣ CV / Barua mag kaze\n"
            "2️⃣ Tiende mag Guok\n"
            "3️⃣ Printing / Scan\n"
            "4️⃣ Translation\n"
            "5️⃣ Moko"
        ),
    }
    return greetings.get(language, greetings["sw"])


async def _process_voice_note(from_number: str, media_id: str) -> str:
    """Process incoming voice note: download → transcribe → handle."""
    try:
        # Download audio
        audio_bytes = await _download_whatsapp_media(media_id)

        # Transcribe via Whisper
        import subprocess
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            whisper_bin = "/usr/local/bin/whisper-cli"
            whisper_model = "/home/work/models/ggml-tiny.bin"
            proc = subprocess.run(
                [whisper_bin, "-m", whisper_model, "-f", tmp_path, "-t", "2", "--no-timestamps"],
                capture_output=True, text=True, timeout=30,
            )
            transcription = proc.stdout.strip() if proc.returncode == 0 else ""
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if not transcription:
            return "😊 Samahani, sijaelewa voice yako. Tafadhali jaribu tena au andika ujumbe."

        # Process the transcribed text as a regular message
        return await _handle_text_message(from_number, transcription)

    except Exception as e:
        logger.error(f"Voice note processing failed: {e}", exc_info=True)
        return "😊 Samahani, kuna tatizo la kusikia voice yako. Tafadhali jaribu tena."


async def _handle_text_message(from_number: str, text: str) -> str:
    """Handle an incoming text message and return response."""
    conv = _conversations.get(from_number, {
        "language": _detect_language(text),
        "state": "new",
        "service": None,
        "step": 0,
        "data": {},
    })
    _conversations[from_number] = conv

    intent = _detect_intent(text)

    # Greeting or first message
    if intent == "greeting" or conv["state"] == "new":
        conv["state"] = "menu"
        lang = _detect_language(text)
        conv["language"] = lang
        return _get_greeting(lang)

    # Menu selections
    if intent.startswith("menu_"):
        choice = intent.split("_")[1]
        if choice == "1":
            conv["state"] = "cv"
            conv["service"] = "cv"
            if conv["language"] == "sw":
                return "📄 *CV & Barua ya Kazi*\n\n1️⃣ CV tu — KES 300\n2️⃣ CV + Barua ya Kazi — KES 450\n\nChagua nambari."
            return "📄 *CV & Cover Letter*\n\n1️⃣ CV only — KES 300\n2️⃣ CV + Cover Letter — KES 450\n\nChoose a number."
        elif choice == "2":
            conv["state"] = "gov"
            conv["service"] = "gov"
            if conv["language"] == "sw":
                return "🏛️ *Huduma za Serikali*\n\n1️⃣ KRA PIN — KES 150\n2️⃣ eCitizen — KES 150-200\n3️⃣ NHIF — KES 150-200\n4️⃣ NSSF — KES 150-200\n5️⃣ NTSA — KES 300\n6️⃣ HELB — KES 150-200\n\nChagua nambari."
            return "🏛️ *Government Services*\n\n1️⃣ KRA PIN — KES 150\n2️⃣ eCitizen — KES 150-200\n3️⃣ NHIF — KES 150-200\n4️⃣ NSSF — KES 150-200\n5️⃣ NTSA — KES 300\n6️⃣ HELB — KES 150-200\n\nChoose a number."
        elif choice == "3":
            return "🖨️ Printing ni KES 5/page (bw) | KES 10 (rangi)\nCopy: KES 5/page | Scan: KES 20/page\n\nKuja dukani au tuma document yako hapa."
        elif choice == "4":
            return "🌐 Translation ni bure na huduma yoyote.\n\nTuma text ukitaka kutafsiri kwa:\n🇬🇧 English\n🇰🇪 Kiswahili\n🇰🇪 Dholuo\n🇰🇪 Kikuyu"
        else:
            return "📞 Piga: 07XX XXX XXX\n🏪 Kuja: Aego Cyber Cafe, Nyatike\n\nAu andika 'menu' kuona huduma zote."

    # Service-specific routing
    if intent == "cv":
        return "📄 Karibu! Nitakusaidia kutengeneza CV.\n\nAnza na jina lako kamili (kama kwenye kitambulisho):"
    if intent == "gov":
        return "🏛️ Huduma gani ya serikali unahitaji?\n• KRA PIN\n• eCitizen\n• NHIF\n• NSSF\n• NTSA\n• HELB"
    if intent == "translate":
        return "🌐 Tuma text unayotaka kutafsiri, au sema lugha unayotaka."
    if intent == "print":
        return "🖨️ Printing: KES 5/page (bw) | KES 10 (rangi)\nTuma document yako au kuja dukani."
    if intent == "photo":
        return "📷 Passport Photo: KES 100\nKuja dukani kwa picha."

    # Default response
    if conv["language"] == "sw":
        return (
            "😊 Samahani, sijaelewa vizuri.\n\n"
            "Andika 'menu' kuona huduma zote, au sema unachohitaji.\n"
            "Mfano: 'Nataka CV', 'KRA PIN', 'Printing'"
        )
    return (
        "😊 Sorry, I didn't understand.\n\n"
        "Type 'menu' to see all services, or tell me what you need.\n"
        "Example: 'I need a CV', 'KRA PIN', 'Printing'"
    )


@router.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    """
    Webhook verification endpoint.
    Meta sends a GET request with hub.mode, hub.verify_token, hub.challenge.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == cfg.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(403, "Verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict:
    """
    Receive incoming WhatsApp messages.
    Processes messages and sends responses back via WhatsApp API.
    """
    try:
        body = await request.json()
        logger.debug(f"WhatsApp webhook: {json.dumps(body, indent=2)}")

        # Parse the webhook payload
        entries = body.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])

                for msg in messages:
                    from_number = msg.get("from", "")
                    msg_type = msg.get("type", "")
                    msg_id = msg.get("id", "")

                    if not from_number:
                        continue

                    logger.info(f"WhatsApp message from {from_number}: type={msg_type}")

                    response_text = ""

                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "")
                        response_text = await _handle_text_message(from_number, text)

                    elif msg_type == "audio":
                        media_id = msg.get("audio", {}).get("id", "")
                        response_text = await _process_voice_note(from_number, media_id)

                    elif msg_type == "image":
                        response_text = (
                            "📷 Nimepokea picha yako.\n"
                            "Kuja dukani kwa huduma za picha, au nitakusaidia na nini?"
                        )

                    elif msg_type == "sticker":
                        response_text = "😊 Karibu! Unahitaji huduma gani leo? Andika 'menu'."

                    else:
                        response_text = (
                            "😊 Tafadhali tuma text, voice note, au picha.\n"
                            "Andika 'menu' kuona huduma zetu."
                        )

                    # Send response
                    if response_text:
                        try:
                            await _send_whatsapp_message(from_number, response_text)
                        except Exception as e:
                            logger.error(f"Failed to send WhatsApp reply: {e}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
