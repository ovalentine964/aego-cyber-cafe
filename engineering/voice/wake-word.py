"""
wake-word.py — Wake word detection for Aego Cyber Cafe voice pipeline.

Two strategies (ordered by resource cost):
  1. Porcupine (pvporcupine) — dedicated DSP chip-level wake word engine.
     Accurate, low CPU, but requires API key and pre-built keyword.
  2. Energy + keyword fallback — lightweight energy detection followed by
     a quick Whisper pass. Works without Porcupine but uses more CPU.

For the Raspberry Pi 5, Porcupine is strongly recommended.
The fallback exists so the pipeline works out-of-the-box without it.

Wake words supported:
  - "Aego" / "Hey Aego" / "Habari Aego" (customizable)
"""

import logging
import struct
import time
from collections import deque
from pathlib import Path
from typing import Optional, Callable

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

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
compute_rms = _audio_utils.compute_rms
record_until_silence = _audio_utils.record_until_silence
DTYPE = _audio_utils.DTYPE

logger = logging.getLogger("aego.wakeword")


class WakeWordDetector:
    """
    Wake word detection with two backends:
      - Porcupine (preferred): dedicated wake word DSP
      - Energy fallback: energy spike → quick STT check

    Usage:
        detector = WakeWordDetector(config)
        detector.start(callback=my_function)
        # ... runs in background thread ...
        detector.stop()
    """

    def __init__(self, config: dict):
        ww_cfg = config.get("wake_word", {})
        self.keywords = ww_cfg.get("keywords", ["aego", "hey aego"])
        self.sensitivity = ww_cfg.get("sensitivity", 0.5)
        self.cooldown_sec = ww_cfg.get("cooldown_sec", 3)
        self.sample_rate = 16000  # Porcupine requires 16kHz

        # State
        self._running = False
        self._last_trigger_time = 0.0
        self._porcupine = None

        # Try Porcupine first
        self._backend = self._init_porcupine(ww_cfg)
        if self._backend == "porcupine":
            logger.info("Wake word: using Porcupine backend")
        else:
            logger.info("Wake word: using energy fallback backend")

    def _init_porcupine(self, ww_cfg: dict) -> str:
        """Try to initialize Porcupine wake word engine."""
        try:
            import pvporcupine

            # Check for Porcupine access key
            access_key = ww_cfg.get("porcupine_access_key")
            if not access_key:
                logger.info("No Porcupine access key — using energy fallback")
                return "energy"

            # Try built-in keywords first, then custom
            # Porcupine has built-in keywords like "porcupine", "bumblebee", etc.
            # For custom "Aego" keyword, you'd need to train one at
            # https://console.picovoice.ai/ppn
            custom_keyword_path = ww_cfg.get("porcupine_keyword_path")

            if custom_keyword_path and Path(custom_keyword_path).exists():
                self._porcupine = pvporcupine.create(
                    access_key=access_key,
                    keyword_paths=[custom_keyword_path],
                    sensitivities=[self.sensitivity],
                )
            else:
                # Use built-in keyword as placeholder
                # In production, replace with custom "Aego" keyword
                logger.warning(
                    "No custom wake word trained. Using built-in 'porcupine' keyword. "
                    "Train a custom 'Aego' keyword at https://console.picovoice.ai/ppn"
                )
                self._porcupine = pvporcupine.create(
                    access_key=access_key,
                    keywords=["porcupine"],  # placeholder
                    sensitivities=[self.sensitivity],
                )

            logger.info(f"Porcupine initialized (sample_rate={self._porcupine.sample_rate})")
            return "porcupine"

        except ImportError:
            logger.debug("pvporcupine not installed")
            return "energy"
        except Exception as e:
            logger.warning(f"Porcupine init failed: {e}")
            return "energy"

    def start(
        self,
        callback: Callable[[], None],
        device_index: Optional[int] = None,
    ) -> None:
        """
        Start listening for wake word in a blocking loop.
        Calls callback() when wake word detected.

        For non-blocking use, run in a thread:
            import threading
            t = threading.Thread(target=detector.start, args=(callback,))
            t.daemon = True
            t.start()
        """
        if sd is None:
            raise RuntimeError("sounddevice not installed for wake word detection")

        self._running = True
        logger.info("Wake word detection started")

        if self._backend == "porcupine":
            self._listen_porcupine(callback, device_index)
        else:
            self._listen_energy(callback, device_index)

    def stop(self) -> None:
        """Stop the wake word detection loop."""
        self._running = False
        if self._porcupine:
            self._porcupine.delete()
            self._porcupine = None
        logger.info("Wake word detection stopped")

    # ── Porcupine Backend ─────────────────────────────────────

    def _listen_porcupine(
        self,
        callback: Callable[[], None],
        device_index: Optional[int],
    ) -> None:
        """
        Listen for wake word using Porcupine DSP engine.
        Very low CPU usage — Porcupine processes audio on a dedicated pipeline.
        """
        porcupine = self._porcupine
        frame_length = porcupine.frame_length  # samples per Porcupine frame

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio status: {status}")
            # Porcupine expects int16 samples
            pcm = struct.unpack_from("h" * frame_length, indata)
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                # Check cooldown
                now = time.time()
                if now - self._last_trigger_time >= self.cooldown_sec:
                    self._last_trigger_time = now
                    logger.info(f"Wake word detected (Porcupine keyword_index={keyword_index})")
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Wake word callback error: {e}")

        try:
            with sd.InputStream(
                samplerate=porcupine.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=frame_length,
                device=device_index,
                callback=audio_callback,
            ):
                while self._running:
                    time.sleep(0.1)  # sleep to reduce CPU in main thread
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    # ── Energy Fallback Backend ───────────────────────────────

    def _listen_energy(
        self,
        callback: Callable[[], None],
        device_index: Optional[int],
    ) -> None:
        """
        Lightweight energy-based wake word detection.

        Algorithm:
        1. Continuously monitor audio energy (very low CPU).
        2. When energy spikes above threshold, record a short segment.
        3. Run quick STT on the segment.
        4. Check if any keyword is in the transcription.
        5. If match → trigger callback.

        CPU usage: ~5% for energy monitoring, spikes during STT checks.
        """
        from stt_module import SpeechToText
        import yaml

        # Load STT for keyword checking
        try:
            with open("config.yaml") as f:
                full_config = yaml.safe_load(f)
            stt = SpeechToText(full_config)
        except Exception as e:
            logger.error(f"Cannot initialize STT for wake word: {e}")
            return

        energy_threshold = 0.03  # slightly higher than VAD to avoid false triggers
        block_size = int(self.sample_rate * 0.1)  # 100ms blocks
        energy_history = deque(maxlen=10)  # rolling window

        logger.info(f"Energy wake word listening (threshold={energy_threshold})")

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=DTYPE,
                blocksize=block_size,
                device=device_index,
            ) as stream:
                while self._running:
                    block, _ = stream.read(block_size)
                    audio = block.flatten()
                    energy = compute_rms(audio)
                    energy_history.append(energy)

                    # Detect energy spike (speech onset)
                    if energy > energy_threshold:
                        # Quick check: was silence before? (avoids re-triggering mid-speech)
                        avg_prev = np.mean(list(energy_history)[:-1]) if len(energy_history) > 1 else 0
                        if avg_prev < energy_threshold * 0.5:
                            # Possible wake word — record a short segment and check
                            now = time.time()
                            if now - self._last_trigger_time < self.cooldown_sec:
                                continue

                            logger.debug("Energy spike detected — checking for wake word")
                            self._last_trigger_time = now

                            # Record 2 seconds of audio for STT check
                            check_audio = self._record_check_audio(stream, block, duration_sec=2.0)
                            if check_audio is None or len(check_audio) == 0:
                                continue

                            # Quick STT
                            result = stt.transcribe(check_audio, sample_rate=self.sample_rate)
                            text_lower = result.text.lower().strip()

                            if not text_lower:
                                continue

                            # Check for keyword match
                            matched = False
                            for keyword in self.keywords:
                                if keyword.lower() in text_lower:
                                    matched = True
                                    break

                            if matched:
                                logger.info(f"Wake word matched: \"{result.text}\"")
                                try:
                                    callback()
                                except Exception as e:
                                    logger.error(f"Wake word callback error: {e}")
                            else:
                                logger.debug(f"No wake word in: \"{result.text}\"")

        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Energy wake word error: {e}")
        finally:
            self.stop()

    def _record_check_audio(
        self,
        stream,
        initial_block: np.ndarray,
        duration_sec: float = 2.0,
    ) -> Optional[np.ndarray]:
        """Record a short audio segment for wake word verification."""
        blocks = [initial_block]
        block_size = initial_block.shape[0]
        num_blocks = int(duration_sec * self.sample_rate / block_size)

        try:
            for _ in range(num_blocks):
                block, _ = stream.read(block_size)
                blocks.append(block.flatten())
            return np.concatenate(blocks)
        except Exception:
            return None


# ── Standalone Test ───────────────────────────────────────────

def main():
    """CLI test for wake word detection."""
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description="Aego Wake Word Detection Test")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    logging.basicConfig(
        level="DEBUG",
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    def on_wake():
        print("\n🎯 WAKE WORD DETECTED! Triggering voice pipeline...\n")

    detector = WakeWordDetector(config)
    print(f"Wake word detection active. Say one of: {detector.keywords}")
    print(f"Backend: {detector._backend}")
    print("Press Ctrl+C to stop.\n")

    try:
        detector.start(callback=on_wake)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
