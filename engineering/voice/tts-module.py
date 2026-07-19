"""
tts-module.py — Text-to-Speech module for Aego Cyber Cafe voice pipeline.

Uses Piper TTS (local neural TTS) for fast, offline speech synthesis.
Supports:
  - Swahili voice (sw_CD) and English voice (en_US)
  - Auto language detection to select the right voice
  - Streaming output (start speaking before full LLM response is ready)
  - Speed and pitch control
  - Direct speaker playback or WAV file output

Piper runs as a subprocess — pipe text in, get WAV audio out.
"""

import io
import logging
import subprocess
import struct
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Generator, Callable

import numpy as np

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
play_audio = _audio_utils.play_audio
save_wav = _audio_utils.save_wav
load_wav = _audio_utils.load_wav
resample = _audio_utils.resample
DTYPE = _audio_utils.DTYPE

logger = logging.getLogger("aego.tts")


@dataclass
class TTSResult:
    """Result of a text-to-speech operation."""
    audio: np.ndarray          # float32 audio samples
    sample_rate: int           # sample rate in Hz
    duration_sec: float        # audio duration
    latency_sec: float         # time to generate audio
    voice: str                 # voice model used
    text: str                  # input text

    def __str__(self) -> str:
        return (
            f"TTS: \"{self.text[:50]}...\" "
            f"(voice={self.voice}, {self.duration_sec:.1f}s audio, "
            f"latency={self.latency_sec:.2f}s)"
        )


class TextToSpeech:
    """
    Text-to-speech engine using Piper TTS.

    Handles voice selection based on language, speed control,
    and streaming playback for long responses.
    """

    # Language detection heuristics
    SWAHILI_MARKERS = {
        "habari", "nzuri", "sana", "naomba", "tafadhali", "asante",
        "karibu", "sawa", "hapana", "ndiyo", "ninataka", "je",
        "mimi", "wewe", "yeye", "sisi", "wao", "hii", "hiyo",
        "pia", "lakini", "kwa", "ya", "na", "wa", "ni",
        "nataka", "unaweza", "nisaidie", "ninaomba",
    }
    DHOLO_MARKERS = {
        "nyathi", "amos", "maber", "ochieng", "ong\'eng\'o",
        "koro", "in", "to", "gi", "ka", "mana", "en",
    }
    KIKUYU_MARKERS = {
        "muthuri", "mwarimu", "njira", "guthii", "kiumeni",
        "niaritha", "wendo", "ngai", "mucii",
    }

    def __init__(self, config: dict):
        """
        Initialize TTS from config dict (parsed from config.yaml).

        Expected keys under config['tts']:
          piper_bin, voices (dict of lang→path), default_voice,
          speed, volume, sample_rate
        """
        tts_cfg = config.get("tts", {})

        self.piper_bin = Path(tts_cfg.get("piper_bin", "/usr/local/bin/piper"))
        self.default_voice_key = tts_cfg.get("default_voice", "sw")
        self.speed = tts_cfg.get("speed", 1.0)
        self.volume = tts_cfg.get("volume", 0.9)
        self.sample_rate = tts_cfg.get("sample_rate", 22050)
        self.speaker_device = config.get("speaker", {}).get("device_index", None)

        # Load voice paths
        self.voices: dict[str, Path] = {}
        for key, path in tts_cfg.get("voices", {}).items():
            self.voices[key] = Path(path)

        # Pre-flight check
        self._piper_available = self._check_piper()

    def _check_piper(self) -> bool:
        """Check if Piper binary exists."""
        if not self.piper_bin.exists():
            logger.warning(f"Piper binary not found: {self.piper_bin}")
            return False
        return True

    def detect_language(self, text: str) -> str:
        """
        Detect the language of the input text using keyword heuristics.
        Returns voice key: "sw", "en", "lu", "ki", or default.
        """
        text_lower = text.lower()
        words = set(text_lower.split())

        # Count matches per language
        swahili_hits = len(words & self.SWAHILI_MARKERS)
        dholuo_hits = len(words & self.DHOLO_MARKERS)
        kikuyu_hits = len(words & self.KIKUYU_MARKERS)

        # If predominantly Swahili markers found
        if swahili_hits >= 2 or (swahili_hits > dholuo_hits and swahili_hits > kikuyu_hits):
            return "sw"

        # If Dholuo markers found
        if dholuo_hits >= 1:
            return "lu"

        # If Kikuyu markers found
        if kikuyu_hits >= 1:
            return "ki"

        # Default: if text contains mostly ASCII/English words, use English
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
        if ascii_ratio > 0.9:
            return "en"

        # Fallback to configured default (usually Swahili for this cafe)
        return self.default_voice_key

    def _select_voice(self, language: Optional[str] = None, text: str = "") -> tuple:
        """
        Select the best voice model for the given language.
        Returns (voice_key, voice_path).
        """
        # Explicit language takes priority
        if language and language in self.voices:
            return language, self.voices[language]

        # Auto-detect from text
        detected = self.detect_language(text)
        if detected in self.voices:
            return detected, self.voices[detected]

        # Fallback to default
        if self.default_voice_key in self.voices:
            return self.default_voice_key, self.voices[self.default_voice_key]

        # Last resort: first available voice
        if self.voices:
            key = next(iter(self.voices))
            return key, self.voices[key]

        raise RuntimeError("No TTS voice models configured!")

    def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> TTSResult:
        """
        Synthesize text to audio.

        Args:
            text: text to speak
            language: force language ("sw", "en", "lu", "ki"), or None for auto
            speed: playback speed override, or None for config default

        Returns:
            TTSResult with audio numpy array and metadata.
        """
        if not text.strip():
            return TTSResult(
                audio=np.array([], dtype=DTYPE),
                sample_rate=self.sample_rate,
                duration_sec=0.0,
                latency_sec=0.0,
                voice="none",
                text=text,
            )

        voice_key, voice_path = self._select_voice(language, text)
        speed = speed or self.speed

        start_time = time.time()

        # Try Piper first
        if self._piper_available and voice_path.exists():
            audio = self._run_piper(text, voice_path, speed)
        else:
            logger.warning("Piper not available — using beep fallback")
            audio = self._beep_fallback(text)

        latency = time.time() - start_time
        duration = len(audio) / self.sample_rate

        result = TTSResult(
            audio=audio,
            sample_rate=self.sample_rate,
            duration_sec=duration,
            latency_sec=latency,
            voice=voice_key,
            text=text,
        )
        logger.info(str(result))
        return result

    def speak(
        self,
        text: str,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        blocking: bool = True,
    ) -> TTSResult:
        """Synthesize and play through speaker."""
        result = self.synthesize(text, language, speed)
        if len(result.audio) > 0:
            play_audio(
                result.audio,
                sample_rate=result.sample_rate,
                device_index=self.speaker_device,
                blocking=blocking,
            )
        return result

    def speak_streaming(
        self,
        text_generator: Generator[str, None, None],
        language: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Streaming TTS — speaks chunks as they arrive from the LLM.

        This is key for perceived latency: the customer hears the response
        starting while the LLM is still generating the rest.

        Args:
            text_generator: yields text chunks from LLM streaming
            language: force language for voice selection
            on_chunk: optional callback for each text chunk (for display)
        """
        import sounddevice as sd

        voice_key, voice_path = self._select_voice(language)
        buffer = ""
        # Minimum characters before we speak a chunk (avoid tiny fragments)
        min_chunk_chars = 20
        # Sentence-ending punctuation triggers immediate speech
        sentence_enders = {".", "!", "?", "。", "！", "？", "\n"}

        # Open audio output stream for continuous playback
        stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=DTYPE,
            device=self.speaker_device,
        )
        stream.start()

        try:
            for chunk in text_generator:
                if on_chunk:
                    on_chunk(chunk)

                buffer += chunk

                # Check if we have enough to speak
                should_speak = False
                if any(buffer.rstrip().endswith(e) for e in sentence_enders):
                    should_speak = True
                elif len(buffer) >= min_chunk_chars * 3:
                    # Long buffer without sentence end — speak at word boundary
                    should_speak = True

                if should_speak and buffer.strip():
                    audio = self._run_piper(buffer.strip(), voice_path, self.speed)
                    if len(audio) > 0:
                        # Apply volume
                        audio = audio * self.volume
                        stream.write(audio.reshape(-1, 1))
                    buffer = ""

            # Speak remaining buffer
            if buffer.strip():
                audio = self._run_piper(buffer.strip(), voice_path, self.speed)
                if len(audio) > 0:
                    audio = audio * self.volume
                    stream.write(audio.reshape(-1, 1))

        finally:
            stream.stop()
            stream.close()

    def synthesize_to_file(
        self,
        text: str,
        filepath: str,
        language: Optional[str] = None,
    ) -> None:
        """Synthesize text and save to WAV file."""
        result = self.synthesize(text, language)
        save_wav(filepath, result.audio, result.sample_rate)

    # ── Piper Backend ─────────────────────────────────────────

    def _run_piper(
        self,
        text: str,
        voice_path: Path,
        speed: float,
    ) -> np.ndarray:
        """
        Run Piper TTS subprocess.

        Piper reads text from stdin and writes WAV audio to stdout.
        We capture stdout and parse the WAV data.
        """
        cmd = [
            str(self.piper_bin),
            "--model", str(voice_path),
            "--output-raw",  # output raw PCM instead of WAV (faster)
        ]

        # Speed control via length scale (inverse: lower = faster)
        if speed != 1.0:
            length_scale = 1.0 / speed
            cmd.extend(["--length-scale", f"{length_scale:.2f}"])

        try:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )

            if proc.returncode != 0:
                logger.error(f"Piper failed (rc={proc.returncode}): {proc.stderr.decode()}")
                return self._beep_fallback(text)

            # Parse raw PCM output (16-bit signed, mono)
            raw_audio = proc.stdout
            if not raw_audio:
                logger.warning("Piper returned empty audio")
                return self._beep_fallback(text)

            # Convert int16 PCM to float32
            num_samples = len(raw_audio) // 2
            audio = np.frombuffer(raw_audio[:num_samples * 2], dtype=np.int16)
            audio = audio.astype(np.float32) / 32767.0

            # Apply volume
            audio = audio * self.volume

            return audio

        except subprocess.TimeoutExpired:
            logger.error("Piper TTS timed out")
            return self._beep_fallback(text)
        except Exception as e:
            logger.error(f"Piper error: {e}")
            return self._beep_fallback(text)

    def _beep_fallback(self, text: str) -> np.ndarray:
        """
        Generate a simple beep as fallback when Piper is unavailable.
        At least provides audio feedback that something was said.
        """
        duration = max(0.5, len(text) * 0.05)  # rough duration estimate
        t = np.linspace(0, duration, int(self.sample_rate * duration), dtype=np.float32)
        # Simple 440 Hz tone with fade in/out
        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        # Fade in/out to avoid clicks
        fade_len = min(1000, len(audio) // 4)
        audio[:fade_len] *= np.linspace(0, 1, fade_len)
        audio[-fade_len:] *= np.linspace(1, 0, fade_len)
        return audio


# ── CLI: Test TTS ─────────────────────────────────────────────

def main():
    """CLI for testing text-to-speech."""
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description="Aego TTS Module Test")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--language", choices=["sw", "en", "lu", "ki", "auto"], default="auto")
    parser.add_argument("--speed", type=float, default=None, help="Speed multiplier")
    parser.add_argument("--output", help="Save to WAV file instead of playing")
    parser.add_argument("--list-voices", action="store_true", help="List available voices")
    args = parser.parse_args()

    # Load config
    with open(args.config) as f:
        config = yaml.safe_load(f)

    logging.basicConfig(
        level=config.get("logging", {}).get("level", "INFO"),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    tts = TextToSpeech(config)

    if args.list_voices:
        print("Available voices:")
        for key, path in tts.voices.items():
            exists = "✓" if path.exists() else "✗ (not found)"
            print(f"  {key}: {path} {exists}")
        return

    lang = None if args.language == "auto" else args.language

    if args.output:
        print(f"Synthesizing to {args.output}...")
        tts.synthesize_to_file(args.text, args.output, language=lang)
        print(f"Saved: {args.output}")
    else:
        print(f"Speaking: \"{args.text}\"")
        result = tts.speak(args.text, language=lang, speed=args.speed)
        print(f"Voice: {result.voice}, Duration: {result.duration_sec:.1f}s, Latency: {result.latency_sec:.2f}s")


if __name__ == "__main__":
    main()
