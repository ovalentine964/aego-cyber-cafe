"""
routes/translate.py — Translation endpoints for Aego Cyber Cafe.

Supports: English, Swahili, Dholuo, Kikuyu
Uses Ollama (Qwen 3.5-3B) for translation via the async queue.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File

from config import cfg
from models import APIResponse, TranslateRequest, TranslateResponse
from queue import Priority, RequestQueue

logger = logging.getLogger("aego.routes.translate")
router = APIRouter(prefix="/api/translate", tags=["translation"])

# Will be set by main.py
request_queue: RequestQueue = None  # type: ignore

LANG_NAMES = {
    "en": "English",
    "sw": "Swahili (Kiswahili)",
    "luo": "Dholuo",
    "ki": "Kikuyu (Gikuyu)",
}


def init(queue: RequestQueue) -> None:
    """Initialize route dependencies."""
    global request_queue
    request_queue = queue


async def _ollama_translate(text: str, source_lang: str | None, target_lang: str) -> dict:
    """Call Ollama to translate text. Returns dict with translated text and detected source lang."""
    source_desc = LANG_NAMES.get(source_lang, "the source language") if source_lang else "auto-detected language"
    target_desc = LANG_NAMES.get(target_lang, target_lang)

    prompt = (
        f"Translate the following text from {source_desc} to {target_desc}.\n"
        f"Output ONLY the translation, nothing else. No explanations.\n\n"
        f"Text to translate:\n{text}"
    )

    async with httpx.AsyncClient(timeout=cfg.OLLAMA_TIMEOUT) as client:
        resp = await client.post(
            f"{cfg.OLLAMA_HOST}/api/generate",
            json={
                "model": cfg.OLLAMA_FALLBACK_MODEL,  # Use smaller model for translation
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2048},
            },
        )
        resp.raise_for_status()
        result = resp.json()
        translated = result.get("response", "").strip()

    # Detect source language if not provided
    detected = source_lang
    if not detected:
        detected = await _detect_language(text)

    return {
        "translated": translated,
        "source_lang": detected,
    }


async def _detect_language(text: str) -> str:
    """Detect the language of the input text using Ollama."""
    prompt = (
        "Detect the language of the following text. "
        "Reply with ONLY the language code: en, sw, luo, or ki. Nothing else.\n\n"
        f"Text: {text[:500]}"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{cfg.OLLAMA_HOST}/api/generate",
                json={
                    "model": cfg.OLLAMA_FALLBACK_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 10},
                },
            )
            resp.raise_for_status()
            result = resp.json()
            lang = result.get("response", "").strip().lower()
            # Normalize
            for code in ("en", "sw", "luo", "ki"):
                if code in lang:
                    return code
    except Exception:
        pass

    return "en"  # default


@router.post("", response_model=APIResponse)
async def translate_text(req: TranslateRequest) -> APIResponse:
    """Translate text between supported languages."""
    if req.target_lang not in LANG_NAMES:
        raise HTTPException(400, f"Unsupported target language. Use: {list(LANG_NAMES.keys())}")

    request_id = f"translate-{hash(req.text[:50])}"

    async def do_translate():
        return await _ollama_translate(req.text, req.source_lang, req.target_lang)

    result = await request_queue.enqueue(
        request_id=request_id,
        priority=Priority.TEXT,
        handler=do_translate,
    )

    if not result.success:
        raise HTTPException(500, f"Translation failed: {result.error}")

    data = result.result
    return APIResponse(
        success=True,
        message="Translation complete",
        data={
            "original": req.text,
            "translated": data["translated"],
            "source_lang": data["source_lang"],
            "target_lang": req.target_lang,
        },
    )


@router.post("/voice", response_model=APIResponse)
async def translate_voice(
    audio: UploadFile = File(...),
    target_lang: str = "sw",
) -> APIResponse:
    """
    Accept audio file, transcribe, translate, return translated text.
    Full pipeline: audio → Whisper → translate → text
    """
    if target_lang not in LANG_NAMES:
        raise HTTPException(400, f"Unsupported target language. Use: {list(LANG_NAMES.keys())}")

    # Save uploaded audio to temp file
    suffix = Path(audio.filename or "audio.ogg").suffix or ".ogg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Step 1: Transcribe using Whisper via subprocess
        import subprocess
        whisper_bin = "/usr/local/bin/whisper-cli"
        whisper_model = "/home/work/models/ggml-tiny.bin"

        proc = subprocess.run(
            [whisper_bin, "-m", whisper_model, "-f", tmp_path, "-t", "2", "--no-timestamps"],
            capture_output=True, text=True, timeout=30,
        )

        if proc.returncode != 0:
            raise HTTPException(500, "Transcription failed")

        transcription = proc.stdout.strip()
        if not transcription:
            raise HTTPException(400, "No speech detected in audio")

        # Step 2: Translate
        request_id = f"translate-voice-{hash(transcription[:50])}"

        async def do_translate():
            return await _ollama_translate(transcription, None, target_lang)

        result = await request_queue.enqueue(
            request_id=request_id,
            priority=Priority.VOICE,
            handler=do_translate,
        )

        if not result.success:
            raise HTTPException(500, f"Translation failed: {result.error}")

        data = result.result
        return APIResponse(
            success=True,
            message="Voice translation complete",
            data={
                "transcription": transcription,
                "translated": data["translated"],
                "source_lang": data["source_lang"],
                "target_lang": target_lang,
            },
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Transcription timed out")
    except Exception as e:
        logger.error(f"Voice translation error: {e}", exc_info=True)
        raise HTTPException(500, f"Voice translation failed: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
