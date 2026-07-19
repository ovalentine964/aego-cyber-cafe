"""
stt-module.py — Speech-to-Text module for Aego Cyber Cafe voice pipeline.

Two backends:
  1. Whisper.cpp (primary) — local, fast, supports Swahili/English/Dholuo
  2. Gemma 4 native audio (fallback) — sends raw audio to Ollama for transcription

Handles:
  - Auto language detection
  - Confidence scoring
  - Automatic fallback when Whisper confidence is low
  - WAV file and numpy array input
"""

import json
import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import requests

# Import sibling modules (hyphenated filenames)
import importlib as _il
import sys as _sys
from pathlib import Path as _Path

def _import_hyphenated(name: str):
    """Import a sibling module with hyphenated filename."""
    if name in _sys.modules:
        return _sys.modules[name]
    _file = _Path(__file__).parent / f"{name}.py"
    _spec = _il.util.spec_from_file_location(name, str(_file))
    _mod = _il.util.module_from_spec(_spec)
    _sys.modules[name] = _mod
    _spec.loader.exec_module(_mod)
    return _mod

_audio_utils = _import_hyphenated("audio-utils")
save_wav = _audio_utils.save_wav
load_wav = _audio_utils.load_wav
compute_rms = _audio_utils.compute_rms
normalize = _audio_utils.normalize
DTYPE = _audio_utils.DTYPE

logger = logging.getLogger("aego.stt")


@dataclass
class TranscriptionResult:
    """Result of a speech-to-text operation."""
    text: str
    language: str          # detected language code: "sw", "en", "lu", etc.
    confidence: float      # 0.0 to 1.0
    duration_sec: float    # audio duration processed
    latency_sec: float     # time taken to transcribe
    backend: str           # "whisper" or "gemma_audio"
    raw_output: str = ""   # full whisper.cpp output for debugging

    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.7

    def __str__(self) -> str:
        return (
            f"[{self.backend}] \"{self.text}\" "
            f"(lang={self.language}, conf={self.confidence:.2f}, "
            f"audio={self.duration_sec:.1f}s, latency={self.latency_sec:.2f}s)"
        )


class SpeechToText:
    """
    Speech-to-text engine with Whisper.cpp primary and Gemma audio fallback.
    """

    # Language code mapping for Whisper.cpp output
    LANG_MAP = {
        "swahili": "sw", "sw": "sw",
        "english": "en", "en": "en",
        "luo": "lu", "dholuo": "lu", "luo (dholuo)": "lu",
        "kikuyu": "ki", "gikuyu": "ki",
        "unknown": "auto",
    }

    def __init__(self, config: dict):
        """
        Initialize STT from config dict (parsed from config.yaml).

        Expected keys under config['stt']:
          whisper_bin, model_path, use_model, language, confidence_threshold,
          beam_size, no_timestamps, gemma_audio_fallback
        """
        stt_cfg = config.get("stt", {})
        ollama_cfg = config.get("ollama", {})

        # Whisper.cpp settings
        self.whisper_bin = Path(stt_cfg.get("whisper_bin", "/usr/local/bin/whisper-cli"))
        self.use_model = stt_cfg.get("use_model", "tiny")
        if self.use_model == "base":
            self.model_path = Path(stt_cfg.get("model_path_base", stt_cfg.get("model_path", "")))
        else:
            self.model_path = Path(stt_cfg.get("model_path", ""))
        self.language = stt_cfg.get("language", "auto")
        self.confidence_threshold = stt_cfg.get("confidence_threshold", 0.7)
        self.beam_size = stt_cfg.get("beam_size", 3)
        self.no_timestamps = stt_cfg.get("no_timestamps", True)
        self.threads = config.get("performance", {}).get("whisper_threads", 2)

        # Gemma audio fallback
        self.gemma_audio_fallback = stt_cfg.get("gemma_audio_fallback", True)
        self.ollama_endpoint = ollama_cfg.get("endpoint", "http://localhost:11434")
        self.ollama_model = ollama_cfg.get("model", "gemma4-e4b")

        # Pre-flight checks
        self._whisper_available = self._check_whisper()
        self._validate_model_path()

    def _check_whisper(self) -> bool:
        """Check if whisper.cpp binary exists and is executable."""
        if not self.whisper_bin.exists():
            logger.warning(f"Whisper binary not found: {self.whisper_bin}")
            return False
        if not self.whisper_bin.is_file():
            logger.warning(f"Whisper binary is not a file: {self.whisper_bin}")
            return False
        return True

    def _validate_model_path(self) -> None:
        """Log warning if model file doesn't exist."""
        if not self.model_path.exists():
            logger.warning(
                f"Whisper model not found: {self.model_path} "
                f"(will fall back to Gemma audio if enabled)"
            )

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        """
        Transcribe audio numpy array → text.

        Pipeline:
        1. Try Whisper.cpp (if available).
        2. If confidence < threshold, try Gemma 4 native audio (if enabled).
        3. Return best result.

        Args:
            audio: float32 numpy array of audio samples
            sample_rate: sample rate of the audio (default 16000)

        Returns:
            TranscriptionResult with text, language, confidence, etc.
        """
        if len(audio) == 0:
            return TranscriptionResult(
                text="", language="unknown", confidence=0.0,
                duration_sec=0.0, latency_sec=0.0, backend="none",
            )

        # Normalize audio level
        audio = normalize(audio, target_peak=0.9)
        duration = len(audio) / sample_rate

        # --- Try Whisper.cpp first ---
        result = None
        if self._whisper_available and self.model_path.exists():
            result = self._transcribe_whisper(audio, sample_rate)
            if result and result.is_confident:
                logger.info(f"Whisper OK: {result}")
                return result
            elif result:
                logger.info(f"Whisper low confidence ({result.confidence:.2f}), trying fallback")
        else:
            if not self._whisper_available:
                logger.debug("Whisper not available")
            if not self.model_path.exists():
                logger.debug("Whisper model not found")

        # --- Fallback: Gemma 4 native audio ---
        if self.gemma_audio_fallback:
            gemma_result = self._transcribe_gemma_audio(audio, sample_rate)
            if gemma_result:
                # If Whisper also returned something, pick the one with more content
                if result and len(result.text) > len(gemma_result.text):
                    return result
                return gemma_result

        # Return Whisper result even if low confidence (best we have)
        if result:
            return result

        # Nothing worked
        return TranscriptionResult(
            text="", language="unknown", confidence=0.0,
            duration_sec=duration, latency_sec=0.0, backend="none",
        )

    def transcribe_file(self, wav_path: str) -> TranscriptionResult:
        """Transcribe a WAV file."""
        audio, sr = load_wav(wav_path)
        return self.transcribe(audio, sample_rate=sr)

    # ── Whisper.cpp Backend ────────────────────────────────────

    def _transcribe_whisper(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> Optional[TranscriptionResult]:
        """
        Run Whisper.cpp on audio via subprocess.
        Saves audio to temp WAV, runs whisper-cli, parses output.
        """
        start_time = time.time()
        duration = len(audio) / sample_rate

        # Save audio to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            save_wav(tmp_path, audio, sample_rate)

        try:
            # Build whisper.cpp command
            cmd = [
                str(self.whisper_bin),
                "-m", str(self.model_path),
                "-f", tmp_path,
                "-t", str(self.threads),
                "-b", str(self.beam_size),
                "--no-timestamps" if self.no_timestamps else "",
            ]

            # Set language (or auto-detect)
            if self.language != "auto":
                cmd.extend(["-l", self.language])

            # Remove empty strings from command
            cmd = [c for c in cmd if c]

            logger.debug(f"Running: {' '.join(cmd)}")

            # Run whisper.cpp
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # safety timeout
            )

            latency = time.time() - start_time

            if proc.returncode != 0:
                logger.error(f"Whisper.cpp failed (rc={proc.returncode}): {proc.stderr}")
                return None

            raw_output = proc.stdout.strip()
            if not raw_output:
                logger.warning("Whisper.cpp returned empty output")
                return None

            # Parse output
            text, language, confidence = self._parse_whisper_output(raw_output)

            return TranscriptionResult(
                text=text,
                language=language,
                confidence=confidence,
                duration_sec=duration,
                latency_sec=latency,
                backend="whisper",
                raw_output=raw_output,
            )

        except subprocess.TimeoutExpired:
            logger.error("Whisper.cpp timed out after 60s")
            return None
        except Exception as e:
            logger.error(f"Whisper.cpp error: {e}")
            return None
        finally:
            # Clean up temp file
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    def _parse_whisper_output(self, raw: str) -> tuple:
        """
        Parse whisper.cpp output to extract text, language, confidence.

        whisper.cpp output format:
          Line 1: detected language (optional, with -l auto)
          Remaining lines: transcription text

        Confidence is estimated from output characteristics since whisper.cpp
        doesn't directly expose logprobs in CLI mode.
        """
        lines = raw.strip().split("\n")

        language = "unknown"
        text_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Language detection line (whisper.cpp format)
            if line.startswith("detected language:") or line.startswith("["):
                lang_lower = line.lower()
                for key, code in self.LANG_MAP.items():
                    if key in lang_lower:
                        language = code
                        break
                continue

            # Skip whisper.cpp status/debug lines
            if any(skip in line.lower() for skip in [
                "whisper", "loading", "processing", "system info",
                "model size", "sampling", "threads",
            ]):
                continue

            # Clean timestamp markers like [00:00:00.000 --> ...]
            if line.startswith("[") and "-->" in line:
                # Extract text after timestamp
                parts = line.split("]", 1)
                if len(parts) > 1:
                    line = parts[1].strip()

            if line:
                text_lines.append(line)

        text = " ".join(text_lines).strip()

        # Estimate confidence based on text characteristics
        # (whisper.cpp CLI doesn't expose token-level probabilities)
        confidence = self._estimate_confidence(text, language)

        return text, language, confidence

    def _estimate_confidence(self, text: str, language: str) -> float:
        """
        Estimate transcription confidence from text characteristics.
        This is a heuristic — real confidence would come from whisper.cpp logprobs.
        """
        if not text:
            return 0.0

        confidence = 0.7  # base confidence for non-empty output

        # Longer text generally means more confident recognition
        word_count = len(text.split())
        if word_count >= 3:
            confidence += 0.1
        if word_count >= 10:
            confidence += 0.05

        # Known language detected
        if language != "unknown":
            confidence += 0.1

        # Penalize if text looks like garbage (repeated chars, no spaces)
        if len(text) > 5 and " " not in text:
            confidence -= 0.3

        # Penalize very short text (might be noise)
        if len(text) < 3:
            confidence -= 0.3

        return max(0.0, min(1.0, confidence))

    # ── Gemma 4 Native Audio Backend ──────────────────────────

    def _transcribe_gemma_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> Optional[TranscriptionResult]:
        """
        Use Gemma 4's native audio input via Ollama API.
        Sends raw audio as base64-encoded WAV and asks for transcription.
        """
        import base64

        start_time = time.time()
        duration = len(audio) / sample_rate

        try:
            # Save audio to WAV bytes in memory
            import io
            import wave

            buf = io.BytesIO()
            audio_int16 = np.clip(audio * 32767, -32767, 32767).astype(np.int16)
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())
            audio_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            # Send to Ollama with audio modality
            payload = {
                "model": self.ollama_model,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Transcribe this audio exactly. "
                            "Output ONLY the transcription text, nothing else. "
                            "If you detect the language, prepend it like: [sw] Habari yako"
                        ),
                        "audio": {"data": audio_b64},
                    }
                ],
                "stream": False,
                "options": {"temperature": 0.1},  # low temp for accurate transcription
            }

            resp = requests.post(
                f"{self.ollama_endpoint}/api/chat",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()

            result_data = resp.json()
            raw_text = result_data.get("message", {}).get("content", "").strip()
            latency = time.time() - start_time

            if not raw_text:
                logger.warning("Gemma audio returned empty transcription")
                return None

            # Parse language tag if present
            language = "unknown"
            text = raw_text
            if raw_text.startswith("[") and "]" in raw_text[:10]:
                tag_end = raw_text.index("]")
                lang_tag = raw_text[1:tag_end].strip().lower()
                language = self.LANG_MAP.get(lang_tag, lang_tag)
                text = raw_text[tag_end + 1:].strip()

            return TranscriptionResult(
                text=text,
                language=language,
                confidence=0.75,  # moderate confidence for Gemma audio
                duration_sec=duration,
                latency_sec=latency,
                backend="gemma_audio",
                raw_output=raw_text,
            )

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama — is it running?")
            return None
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out")
            return None
        except Exception as e:
            logger.error(f"Gemma audio transcription error: {e}")
            return None


# ── CLI: Test STT ─────────────────────────────────────────────

def main():
    """CLI for testing speech-to-text."""
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description="Aego STM Module Test")
    parser.add_argument("audio", help="WAV file to transcribe")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--backend", choices=["whisper", "gemma", "auto"], default="auto")
    args = parser.parse_args()

    # Load config
    with open(args.config) as f:
        config = yaml.safe_load(f)

    # Set up logging
    logging.basicConfig(
        level=config.get("logging", {}).get("level", "INFO"),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    stt = SpeechToText(config)

    # Override backend if specified
    if args.backend == "whisper":
        stt.gemma_audio_fallback = False
    elif args.backend == "gemma":
        stt._whisper_available = False

    print(f"Transcribing: {args.audio}")
    print(f"Backend: whisper={'available' if stt._whisper_available else 'N/A'}, "
          f"gemma_audio={'enabled' if stt.gemma_audio_fallback else 'disabled'}")
    print()

    result = stt.transcribe_file(args.audio)

    print(f"Text:       {result.text}")
    print(f"Language:   {result.language}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Duration:   {result.duration_sec:.1f}s")
    print(f"Latency:    {result.latency_sec:.2f}s")
    print(f"Backend:    {result.backend}")


if __name__ == "__main__":
    main()
