"""
voice-pipeline.py — Main voice processing pipeline for Aego Cyber Cafe.

Orchestrates the full voice interaction loop:
  1. Listen (microphone → VAD or push-to-talk)
  2. Transcribe (Whisper.cpp primary, Gemma audio fallback)
  3. Think (Ollama / Gemma 4 LLM reasoning)
  4. Speak (Piper TTS → speaker)

Three operating modes:
  - push_to_talk: press Enter to start recording (most reliable)
  - always_listening: always-on with VAD (convenient but uses more CPU)
  - wake_word: listen for "Aego" then process (hands-free)

Designed for Raspberry Pi 5 — careful with memory and CPU.
"""

import json
import logging
import logging.handlers
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
import requests
import yaml

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
record_until_silence = _audio_utils.record_until_silence
play_audio = _audio_utils.play_audio
save_wav = _audio_utils.save_wav
compute_rms = _audio_utils.compute_rms
list_devices = _audio_utils.list_devices
AudioMeter = _audio_utils.AudioMeter
DTYPE = _audio_utils.DTYPE

_stt_module = _import_hyphenated("stt-module")
SpeechToText = _stt_module.SpeechToText
TranscriptionResult = _stt_module.TranscriptionResult

_tts_module = _import_hyphenated("tts-module")
TextToSpeech = _tts_module.TextToSpeech

_wake_word = _import_hyphenated("wake-word")
WakeWordDetector = _wake_word.WakeWordDetector

logger = logging.getLogger("aego.pipeline")


# ── Ollama LLM Client ────────────────────────────────────────

class OllamaClient:
    """
    Client for Ollama API (Gemma 4 E4B).
    Handles both regular text chat and streaming responses.
    """

    def __init__(self, config: dict):
        ollama_cfg = config.get("ollama", {})
        self.endpoint = ollama_cfg.get("endpoint", "http://localhost:11434")
        self.model = ollama_cfg.get("model", "gemma4-e4b")
        self.timeout = ollama_cfg.get("timeout_sec", 30)
        self.system_prompt = ollama_cfg.get("system_prompt", "You are Aego, a helpful assistant.")
        self.temperature = ollama_cfg.get("temperature", 0.7)
        self.max_tokens = ollama_cfg.get("max_tokens", 200)

        # Conversation history (kept short for memory efficiency)
        self._history: list = []
        self._max_history = 10  # keep last N exchanges

    def chat(self, user_message: str, stream: bool = False) -> str:
        """
        Send a message to the LLM and get a response.

        Args:
            user_message: the transcribed customer speech
            stream: if True, returns a generator yielding text chunks

        Returns:
            Response text (or generator if stream=True)
        """
        # Build messages with history
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        try:
            if stream:
                return self._chat_stream(payload, user_message)
            else:
                return self._chat_sync(payload, user_message)
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama — is it running?")
            return "Pole, kuna tatizo la kiunganishi. Tafadhali jaribu tena."
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out")
            return "Pole, muda umekwisha. Tafadhali jaribu tena."
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return "Pole, kuna hitilafu. Tafadhali jaribu tena."

    def _chat_sync(self, payload: dict, user_message: str) -> str:
        """Synchronous chat — wait for full response."""
        resp = requests.post(
            f"{self.endpoint}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()

        result = resp.json()
        response = result.get("message", {}).get("content", "").strip()

        # Update history
        self._add_to_history(user_message, response)

        logger.info(f"LLM response ({len(response)} chars): {response[:100]}...")
        return response

    def _chat_stream(self, payload: dict, user_message: str):
        """
        Streaming chat — yields text chunks as they arrive.
        Used for streaming TTS to reduce perceived latency.
        """
        resp = requests.post(
            f"{self.endpoint}/api/chat",
            json=payload,
            stream=True,
            timeout=self.timeout,
        )
        resp.raise_for_status()

        full_response = []
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    full_response.append(content)
                    yield content
            except json.JSONDecodeError:
                continue

        # Update history with complete response
        complete = "".join(full_response)
        self._add_to_history(user_message, complete)

    def _add_to_history(self, user_msg: str, assistant_msg: str) -> None:
        """Add exchange to conversation history, trim if too long."""
        self._history.append({"role": "user", "content": user_msg})
        self._history.append({"role": "assistant", "content": assistant_msg})

        # Trim old history (keep last N exchanges = 2*N messages)
        while len(self._history) > self._max_history * 2:
            self._history.pop(0)
            self._history.pop(0)

    def clear_history(self) -> None:
        """Clear conversation history (new customer)."""
        self._history.clear()
        logger.info("Conversation history cleared")


# ── Voice Pipeline ────────────────────────────────────────────

class VoicePipeline:
    """
    Main voice processing pipeline for Aego Cyber Cafe.

    Orchestrates: Listen → Transcribe → Think → Speak

    Usage:
        pipeline = VoicePipeline("config.yaml")
        pipeline.run()  # blocking main loop
    """

    def __init__(self, config_path: str = "config.yaml"):
        # Load configuration
        self.config_path = Path(config_path)
        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)

        # Set up logging
        self._setup_logging()

        # Operation mode
        self.mode = self.config.get("mode", "push_to_talk")

        # Audio device settings
        self.mic_device = self.config.get("microphone", {}).get("device_index")
        self.speaker_device = self.config.get("speaker", {}).get("device_index")
        self.sample_rate = self.config.get("microphone", {}).get("sample_rate", 16000)

        # Initialize components
        logger.info("Initializing voice pipeline components...")
        self.stt = SpeechToText(self.config)
        self.tts = TextToSpeech(self.config)
        self.llm = OllamaClient(self.config)

        # Wake word detector (only initialized if mode is wake_word)
        self.wake_detector: Optional[WakeWordDetector] = None
        if self.mode == "wake_word":
            self.wake_detector = WakeWordDetector(self.config)

        # State
        self._running = False
        self._processing = False  # True when handling a customer interaction
        self._interaction_count = 0

        # Metrics
        self._total_latency = {"stt": 0, "llm": 0, "tts": 0, "total": 0}
        self._total_interactions = 0

        logger.info(f"Pipeline ready — mode={self.mode}")

    def _setup_logging(self) -> None:
        """Configure logging from config."""
        log_cfg = self.config.get("logging", {})
        level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)

        # Root logger
        root = logging.getLogger("aego")
        root.setLevel(level)

        # Console handler
        if log_cfg.get("console", True):
            console = logging.StreamHandler(sys.stdout)
            console.setLevel(level)
            fmt = logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                datefmt="%H:%M:%S",
            )
            console.setFormatter(fmt)
            root.addHandler(console)

        # File handler (rotating)
        log_file = log_cfg.get("file")
        if log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=log_cfg.get("max_size_mb", 10) * 1024 * 1024,
                backupCount=3,
            )
            file_handler.setLevel(level)
            fmt = logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
            )
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)

    # ── Main Loop ─────────────────────────────────────────────

    def run(self) -> None:
        """
        Start the voice pipeline main loop.
        Blocks until interrupted (Ctrl+C or SIGTERM).
        """
        self._running = True

        # Handle graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        # Print startup banner
        self._print_banner()

        try:
            if self.mode == "push_to_talk":
                self._loop_push_to_talk()
            elif self.mode == "always_listening":
                self._loop_always_listening()
            elif self.mode == "wake_word":
                self._loop_wake_word()
            else:
                logger.error(f"Unknown mode: {self.mode}")
                sys.exit(1)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _print_banner(self) -> None:
        """Print startup information."""
        print("=" * 60)
        print("  🎙️  Aego Cyber Cafe — Voice Assistant")
        print("  📍 Nyatike, Migori County, Kenya")
        print(f"  🔧 Mode: {self.mode}")
        print(f"  🤖 LLM: {self.config.get('ollama', {}).get('model', 'unknown')}")
        print(f"  🗣️  STT: Whisper.cpp ({self.stt.use_model})")
        print(f"  🔊 TTS: Piper ({self.tts.default_voice_key})")
        print("=" * 60)
        if self.mode == "push_to_talk":
            print("\n  Press ENTER to start speaking, Ctrl+C to exit.\n")
        elif self.mode == "always_listening":
            print("\n  Always listening... speak naturally. Ctrl+C to exit.\n")
        elif self.mode == "wake_word":
            print(f"\n  Say '{self.wake_detector.keywords[0]}' to activate. Ctrl+C to exit.\n")

    # ── Push-to-Talk Mode ────────────────────────────────────

    def _loop_push_to_talk(self) -> None:
        """
        Push-to-talk mode: press Enter to start recording.

        Most reliable mode — no false triggers, works in noisy environments.
        Best for the cyber cafe counter where staff can press a button.
        """
        while self._running:
            try:
                # Wait for Enter key
                input("\n🔘 Press ENTER to speak...")
            except EOFError:
                break

            if not self._running:
                break

            # Process the interaction
            self._process_interaction()

    # ── Always-Listening Mode ─────────────────────────────────

    def _loop_always_listening(self) -> None:
        """
        Always-listening mode: VAD detects when customer speaks.

        More natural but uses more CPU. The VAD in record_until_silence
        handles start/stop detection.
        """
        vad_cfg = self.config.get("vad", {})

        while self._running:
            logger.debug("Listening for speech...")

            # Record until silence (VAD-based)
            audio = record_until_silence(
                sample_rate=self.sample_rate,
                device_index=self.mic_device,
                energy_threshold=vad_cfg.get("energy_threshold", 0.015),
                silence_timeout_sec=vad_cfg.get("silence_timeout_sec", 1.5),
                max_duration_sec=self.config.get("microphone", {}).get("max_record_seconds", 30),
                pre_buffer_sec=vad_cfg.get("pre_speech_buffer_sec", 0.3),
                block_duration_ms=vad_cfg.get("block_duration_ms", 30),
            )

            if len(audio) == 0:
                # No speech detected — just silence
                continue

            # Check minimum speech duration
            min_duration = vad_cfg.get("min_speech_duration_sec", 0.3)
            if len(audio) / self.sample_rate < min_duration:
                logger.debug("Speech too short — ignoring")
                continue

            # Process the interaction
            self._process_interaction(audio=audio)

    # ── Wake Word Mode ────────────────────────────────────────

    def _loop_wake_word(self) -> None:
        """
        Wake word mode: listen for "Aego" then process.

        Best for hands-free operation. Uses the wake word detector
        to minimize CPU usage during idle periods.
        """
        if self.wake_detector is None:
            logger.error("Wake word detector not initialized")
            return

        def on_wake():
            """Called when wake word is detected."""
            # Play a confirmation sound
            self._play_ding()
            # Process interaction
            self._process_interaction()

        # Start wake word detection (blocking)
        self.wake_detector.start(callback=on_wake, device_index=self.mic_device)

    # ── Core Processing ───────────────────────────────────────

    def _process_interaction(self, audio: Optional[np.ndarray] = None) -> None:
        """
        Process a single voice interaction:
          1. Record audio (if not provided)
          2. Transcribe speech → text
          3. Send text to LLM → get response
          4. Speak response via TTS

        Handles the full error chain gracefully.
        """
        self._processing = True
        self._interaction_count += 1
        interaction_id = self._interaction_count
        timings = {}

        logger.info(f"=== Interaction #{interaction_id} started ===")

        try:
            # ── Step 1: Record audio ──
            if audio is None:
                t0 = time.time()
                vad_cfg = self.config.get("vad", {})
                audio = record_until_silence(
                    sample_rate=self.sample_rate,
                    device_index=self.mic_device,
                    energy_threshold=vad_cfg.get("energy_threshold", 0.015),
                    silence_timeout_sec=vad_cfg.get("silence_timeout_sec", 1.5),
                    max_duration_sec=self.config.get("microphone", {}).get("max_record_seconds", 30),
                    pre_buffer_sec=vad_cfg.get("pre_speech_buffer_sec", 0.3),
                )
                timings["record"] = time.time() - t0

                if len(audio) == 0:
                    logger.info("No speech detected — skipping")
                    self._speak_error("Sikutambua sauti. Tafadhali jaribu tena.")
                    return

            duration = len(audio) / self.sample_rate
            logger.info(f"Audio recorded: {duration:.1f}s")

            # Save audio for debugging
            debug_dir = Path(self.config.get("logging", {}).get("file", "")).parent
            if debug_dir.exists():
                save_wav(str(debug_dir / f"interaction_{interaction_id}.wav"), audio, self.sample_rate)

            # ── Step 2: Transcribe ──
            t0 = time.time()
            transcription = self.stt.transcribe(audio, sample_rate=self.sample_rate)
            timings["stt"] = time.time() - t0

            logger.info(f"Transcription: {transcription}")

            if not transcription.text.strip():
                logger.info("Empty transcription — skipping")
                self._speak_error("Sikuelewa. Tafadhali jaribu tena.")
                return

            # ── Step 3: LLM reasoning ──
            t0 = time.time()
            use_streaming = self.config.get("performance", {}).get("streaming_tts", True)

            if use_streaming:
                # Streaming: TTS speaks as LLM generates
                response_text = self._process_streaming(transcription)
            else:
                # Non-streaming: wait for full response, then speak
                response_text = self.llm.chat(transcription.text)
            timings["llm"] = time.time() - t0

            if not response_text:
                logger.warning("LLM returned empty response")
                self._speak_error("Pole, sijaweza kujibu. Tafadhali jaribu tena.")
                return

            # ── Step 4: Speak response ──
            if not use_streaming:
                t0 = time.time()
                self.tts.speak(
                    response_text,
                    language=transcription.language,
                    blocking=True,
                )
                timings["tts"] = time.time() - t0

            # ── Metrics ──
            total = sum(timings.values())
            logger.info(
                f"Interaction #{interaction_id} complete — "
                f"record={timings.get('record', 0):.1f}s, "
                f"stt={timings.get('stt', 0):.1f}s, "
                f"llm={timings.get('llm', 0):.1f}s, "
                f"tts={timings.get('tts', 0):.1f}s, "
                f"total={total:.1f}s"
            )

            # Update running averages
            self._total_interactions += 1
            for key, val in timings.items():
                self._total_latency[key] = self._total_latency.get(key, 0) + val

        except Exception as e:
            logger.error(f"Interaction #{interaction_id} failed: {e}", exc_info=True)
            self._speak_error("Kuna hitilafu. Tafadhali jaribu tena.")
        finally:
            self._processing = False

    def _process_streaming(self, transcription: TranscriptionResult) -> str:
        """
        Process with streaming TTS — speaks while LLM generates.
        Returns the complete response text.
        """
        # Get streaming response from LLM
        response_gen = self.llm.chat(transcription.text, stream=True)

        # Collect full response while TTS speaks chunks
        full_response = []

        def on_chunk(chunk: str):
            full_response.append(chunk)

        self.tts.speak_streaming(
            response_gen,
            language=transcription.language,
            on_chunk=on_chunk,
        )

        return "".join(full_response)

    def _speak_error(self, message: str) -> None:
        """Speak an error message to the customer."""
        try:
            self.tts.speak(message, blocking=True)
        except Exception as e:
            logger.error(f"Failed to speak error message: {e}")

    def _play_ding(self) -> None:
        """Play a short confirmation tone (wake word detected)."""
        try:
            sr = 22050
            duration = 0.15
            t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
            # Pleasant two-tone ding
            tone = 0.3 * np.sin(2 * np.pi * 880 * t) + 0.2 * np.sin(2 * np.pi * 1320 * t)
            fade = min(500, len(tone) // 4)
            tone[:fade] *= np.linspace(0, 1, fade)
            tone[-fade:] *= np.linspace(1, 0, fade)
            play_audio(tone, sample_rate=sr, device_index=self.speaker_device, blocking=False)
        except Exception:
            pass  # non-critical

    # ── Shutdown ──────────────────────────────────────────────

    def _handle_shutdown(self, signum, frame) -> None:
        """Handle SIGINT/SIGTERM gracefully."""
        logger.info("Shutdown signal received")
        self._running = False

    def _shutdown(self) -> None:
        """Clean up resources."""
        logger.info("Shutting down voice pipeline...")

        if self.wake_detector:
            self.wake_detector.stop()

        # Print session summary
        if self._total_interactions > 0:
            n = self._total_interactions
            avg = {k: v / n for k, v in self._total_latency.items()}
            print(f"\n📊 Session Summary:")
            print(f"   Interactions: {n}")
            print(f"   Avg latency — STT: {avg.get('stt', 0):.1f}s, "
                  f"LLM: {avg.get('llm', 0):.1f}s, "
                  f"TTS: {avg.get('tts', 0):.1f}s, "
                  f"Total: {avg.get('total', 0):.1f}s")

        logger.info("Pipeline stopped")


# ── CLI Entry Point ──────────────────────────────────────────

def main():
    """CLI entry point for the voice pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Aego Cyber Cafe Voice Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python voice-pipeline.py                          # push-to-talk mode
  python voice-pipeline.py --mode always_listening  # always-on VAD
  python voice-pipeline.py --mode wake_word         # wake word activation
  python voice-pipeline.py --devices                # list audio devices
  python voice-pipeline.py --meter                  # audio level meter
        """,
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument(
        "--mode",
        choices=["push_to_talk", "always_listening", "wake_word"],
        help="Override operation mode from config",
    )
    parser.add_argument("--devices", action="store_true", help="List audio devices and exit")
    parser.add_argument("--meter", action="store_true", help="Run audio level meter")
    parser.add_argument("--meter-duration", type=float, default=10.0)

    args = parser.parse_args()

    # Quick commands
    if args.devices:
        print("Audio Devices:")
        for d in list_devices():
            ch = []
            if d["max_input_channels"] > 0:
                ch.append(f"IN:{d['max_input_channels']}")
            if d["max_output_channels"] > 0:
                ch.append(f"OUT:{d['max_output_channels']}")
            print(f"  [{d['index']:2d}] {d['name']} ({', '.join(ch)})")
        return

    if args.meter:
        meter = AudioMeter()
        meter.run(args.meter_duration)
        return

    # Load config
    config_file = Path(args.config)
    if not config_file.exists():
        print(f"Error: Config file not found: {config_file}")
        sys.exit(1)

    # Build and run pipeline
    pipeline = VoicePipeline(str(config_file))

    # Override mode if specified
    if args.mode:
        pipeline.mode = args.mode

    pipeline.run()


if __name__ == "__main__":
    main()
