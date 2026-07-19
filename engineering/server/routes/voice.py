"""
routes/voice.py — Voice Pipeline endpoints for Aego Cyber Cafe.

Endpoints:
  POST /api/voice/transcribe  — audio → text (Whisper.cpp)
  POST /api/voice/synthesize  — text → audio (Piper TTS)
  POST /api/voice/chat        — audio → text → LLM → audio (full pipeline)
  WS   /api/voice/stream      — real-time voice streaming

Uses existing voice pipeline modules from engineering/voice/.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import tempfile
import time
import wave
from pathlib import Path

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from config import cfg
from models import APIResponse, VoiceResponse
from queue import Priority, RequestQueue

logger = logging.getLogger("aego.routes.voice")
router = APIRouter(prefix="/api/voice", tags=["voice"])

# Will be set by main.py
request_queue: RequestQueue = None  # type: ignore
_voice_config: dict = {}


def init(queue: RequestQueue, voice_config_path: str) -> None:
    """Initialize route dependencies."""
    global request_queue, _voice_config
    request_queue = queue

    # Load voice config
    try:
        import yaml
        with open(voice_config_path, "r") as f:
            _voice_config = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Could not load voice config: {e}")


def _get_stt():
    """Lazy-load SpeechToText module."""
    import importlib.util
    voice_dir = Path(cfg.VOICE_CONFIG).parent
    stt_path = voice_dir / "stt-module.py"
    spec = importlib.util.spec_from_file_location("stt_module", str(stt_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SpeechToText(_voice_config)


def _get_tts():
    """Lazy-load TextToSpeech module."""
    import importlib.util
    voice_dir = Path(cfg.VOICE_CONFIG).parent
    tts_path = voice_dir / "tts-module.py"
    spec = importlib.util.spec_from_file_location("tts_module", str(tts_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TextToSpeech(_voice_config)


async def _transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    """Transcribe audio bytes to text using Whisper.cpp."""
    suffix = Path(filename).suffix or ".ogg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        import subprocess
        whisper_bin = _voice_config.get("stt", {}).get("whisper_bin", "/usr/local/bin/whisper-cli")
        model_path = _voice_config.get("stt", {}).get("model_path", "/home/work/models/ggml-tiny.bin")
        threads = _voice_config.get("performance", {}).get("whisper_threads", 2)

        proc = subprocess.run(
            [whisper_bin, "-m", model_path, "-f", tmp_path, "-t", str(threads), "--no-timestamps"],
            capture_output=True, text=True, timeout=30,
        )

        if proc.returncode != 0:
            logger.error(f"Whisper failed: {proc.stderr}")
            raise RuntimeError("Transcription failed")

        return proc.stdout.strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def _synthesize_speech(text: str, language: str = "sw") -> bytes:
    """Synthesize text to WAV audio using Piper TTS."""
    import subprocess

    piper_bin = _voice_config.get("tts", {}).get("piper_bin", "/usr/local/bin/piper")
    voices = _voice_config.get("tts", {}).get("voices", {})
    voice_path = voices.get(language, voices.get("sw", ""))
    speed = _voice_config.get("tts", {}).get("speed", 1.0)

    if not voice_path:
        raise RuntimeError(f"No voice model for language: {language}")

    cmd = [piper_bin, "--model", str(voice_path), "--output-raw"]
    if speed != 1.0:
        cmd.extend(["--length-scale", f"{1.0 / speed:.2f}"])

    proc = subprocess.run(
        cmd, input=text.encode("utf-8"), capture_output=True, timeout=30,
    )

    if proc.returncode != 0:
        raise RuntimeError(f"Piper TTS failed: {proc.stderr.decode()}")

    # Convert raw PCM to WAV
    raw_pcm = proc.stdout
    sample_rate = _voice_config.get("tts", {}).get("sample_rate", 22050)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_pcm)

    return buf.getvalue()


async def _ollama_chat(text: str, language: str = "en") -> str:
    """Send text to Ollama LLM and get response."""
    system_prompt = _voice_config.get("ollama", {}).get(
        "system_prompt",
        "You are Aego, a helpful assistant at a cyber cafe in Kenya. "
        "Respond in the same language the customer uses. Be concise."
    )

    async with httpx.AsyncClient(timeout=cfg.OLLAMA_TIMEOUT) as client:
        resp = await client.post(
            f"{cfg.OLLAMA_HOST}/api/chat",
            json={
                "model": cfg.OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 200,
                },
            },
        )
        resp.raise_for_status()
        result = resp.json()
        return result.get("message", {}).get("content", "").strip()


@router.post("/transcribe", response_model=APIResponse)
async def transcribe(audio: UploadFile = File(...)) -> APIResponse:
    """Transcribe audio file to text using Whisper.cpp."""
    content = await audio.read()
    if not content:
        raise HTTPException(400, "Empty audio file")

    request_id = f"transcribe-{int(time.time())}"

    async def do_transcribe():
        return await _transcribe_audio(content, audio.filename or "audio.ogg")

    result = await request_queue.enqueue(
        request_id=request_id,
        priority=Priority.VOICE,
        handler=do_transcribe,
        timeout=30,
    )

    if not result.success:
        raise HTTPException(500, f"Transcription failed: {result.error}")

    return APIResponse(
        success=True,
        message="Transcription complete",
        data={"text": result.result},
    )


@router.post("/synthesize", response_model=APIResponse)
async def synthesize(
    text: str = "",
    language: str = "sw",
) -> APIResponse:
    """Synthesize text to speech audio. Returns base64-encoded WAV."""
    if not text:
        raise HTTPException(400, "Text is required")

    request_id = f"synthesize-{int(time.time())}"

    async def do_synthesize():
        return await _synthesize_speech(text, language)

    result = await request_queue.enqueue(
        request_id=request_id,
        priority=Priority.VOICE,
        handler=do_synthesize,
        timeout=30,
    )

    if not result.success:
        raise HTTPException(500, f"Synthesis failed: {result.error}")

    audio_b64 = base64.b64encode(result.result).decode("utf-8")

    return APIResponse(
        success=True,
        message="Speech synthesized",
        data={
            "audio_base64": audio_b64,
            "format": "wav",
            "language": language,
        },
    )


@router.post("/synthesize/audio")
async def synthesize_audio(
    text: str = "",
    language: str = "sw",
) -> Response:
    """Synthesize text to speech and return raw WAV audio bytes."""
    if not text:
        raise HTTPException(400, "Text is required")

    try:
        audio_bytes = await _synthesize_speech(text, language)
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=speech.wav"},
        )
    except Exception as e:
        raise HTTPException(500, f"Synthesis failed: {e}")


@router.post("/chat")
async def voice_chat(audio: UploadFile = File(...)) -> APIResponse:
    """
    Full voice pipeline: audio → transcribe → LLM → synthesize response.
    Returns transcription, text response, and base64-encoded audio response.
    """
    content = await audio.read()
    if not content:
        raise HTTPException(400, "Empty audio file")

    request_id = f"voice-chat-{int(time.time())}"

    async def do_voice_chat():
        # Step 1: Transcribe
        transcription = await _transcribe_audio(content, audio.filename or "audio.ogg")
        if not transcription:
            return {"error": "No speech detected"}

        # Step 2: LLM response
        response_text = await _ollama_chat(transcription)

        # Step 3: Synthesize response
        audio_bytes = await _synthesize_speech(response_text)

        return {
            "transcription": transcription,
            "response_text": response_text,
            "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
        }

    result = await request_queue.enqueue(
        request_id=request_id,
        priority=Priority.VOICE,
        handler=do_voice_chat,
        timeout=90,  # Full pipeline needs more time
    )

    if not result.success:
        raise HTTPException(500, f"Voice chat failed: {result.error}")

    data = result.result
    if "error" in data:
        raise HTTPException(400, data["error"])

    return APIResponse(
        success=True,
        message="Voice chat complete",
        data=data,
    )


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time voice streaming.

    Protocol:
      Client sends: binary audio chunks (PCM 16-bit, 16kHz, mono)
      Client sends: JSON {"type": "end"} when done recording
      Server sends: JSON {"type": "transcription", "text": "..."}
      Server sends: JSON {"type": "response", "text": "..."}
      Server sends: binary audio chunk (PCM 16-bit, 22050Hz)
      Server sends: JSON {"type": "done"}
    """
    await websocket.accept()
    logger.info("Voice stream WebSocket connected")

    audio_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message:
                audio_buffer.extend(message["bytes"])

            elif "text" in message:
                data = json.loads(message["text"])

                if data.get("type") == "end":
                    # Process the buffered audio
                    if not audio_buffer:
                        await websocket.send_json({"type": "error", "message": "No audio received"})
                        continue

                    # Transcribe
                    await websocket.send_json({"type": "status", "message": "Transcribing..."})
                    try:
                        transcription = await _transcribe_audio(bytes(audio_buffer))
                        await websocket.send_json({"type": "transcription", "text": transcription})
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": f"Transcription failed: {e}"})
                        audio_buffer.clear()
                        continue

                    # LLM response
                    await websocket.send_json({"type": "status", "message": "Thinking..."})
                    try:
                        response_text = await _ollama_chat(transcription)
                        await websocket.send_json({"type": "response", "text": response_text})
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": f"LLM failed: {e}"})
                        audio_buffer.clear()
                        continue

                    # Synthesize and stream audio back
                    await websocket.send_json({"type": "status", "message": "Speaking..."})
                    try:
                        audio_bytes = await _synthesize_speech(response_text)
                        # Send audio in chunks
                        chunk_size = 4096
                        for i in range(0, len(audio_bytes), chunk_size):
                            await websocket.send_bytes(audio_bytes[i:i + chunk_size])
                        await websocket.send_json({"type": "done"})
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": f"TTS failed: {e}"})

                    audio_buffer.clear()

                elif data.get("type") == "reset":
                    audio_buffer.clear()
                    await websocket.send_json({"type": "status", "message": "Buffer cleared"})

    except WebSocketDisconnect:
        logger.info("Voice stream WebSocket disconnected")
    except Exception as e:
        logger.error(f"Voice stream error: {e}", exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass
