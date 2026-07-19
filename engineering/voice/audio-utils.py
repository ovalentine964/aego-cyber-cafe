"""
audio-utils.py — Audio utilities for Aego Cyber Cafe voice pipeline.

Provides:
  - Microphone recording to numpy arrays / WAV files
  - Speaker playback from numpy arrays / WAV files
  - Real-time audio level metering (RMS, peak)
  - Noise gate (silence below energy threshold)
  - Sample rate conversion
  - Device enumeration helpers

Designed for Raspberry Pi 5 with limited resources — minimal buffering,
no unnecessary copies, direct numpy operations.
"""

import io
import wave
import struct
import logging
from pathlib import Path
from typing import Optional, Tuple, Generator

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None  # Allow import for testing without audio hardware

logger = logging.getLogger("aego.audio")

# ── Constants ─────────────────────────────────────────────────
DTYPE = "float32"            # sounddevice works in float32 [-1.0, 1.0]
INT16_MAX = 32767.0          # for WAV conversion


# ── Device Helpers ────────────────────────────────────────────

def list_devices() -> list:
    """Return list of available audio devices with index, name, channels."""
    if sd is None:
        logger.warning("sounddevice not installed")
        return []
    devices = sd.query_devices()
    result = []
    for i, d in enumerate(devices):
        result.append({
            "index": i,
            "name": d["name"],
            "max_input_channels": d["max_input_channels"],
            "max_output_channels": d["max_output_channels"],
            "default_samplerate": d["default_samplerate"],
        })
    return result


def find_usb_device(kind: str = "input") -> Optional[int]:
    """
    Find the first USB audio device index.
    kind: "input" for microphone, "output" for speaker.
    Returns device index or None if not found.
    """
    devices = list_devices()
    keyword = "USB"
    for d in devices:
        if keyword.lower() in d["name"].lower():
            if kind == "input" and d["max_input_channels"] > 0:
                return d["index"]
            if kind == "output" and d["max_output_channels"] > 0:
                return d["index"]
    return None


# ── Recording ─────────────────────────────────────────────────

def record_audio(
    duration_sec: float,
    sample_rate: int = 16000,
    channels: int = 1,
    device_index: Optional[int] = None,
) -> np.ndarray:
    """
    Record audio from microphone for a fixed duration.
    Returns numpy array of shape (num_samples,) for mono.
    """
    if sd is None:
        raise RuntimeError("sounddevice not installed")
    logger.info(f"Recording {duration_sec:.1f}s @ {sample_rate} Hz")
    audio = sd.rec(
        int(duration_sec * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        dtype=DTYPE,
        device=device_index,
    )
    sd.wait()  # block until recording complete
    if channels == 1:
        audio = audio.flatten()
    return audio


def record_until_silence(
    sample_rate: int = 16000,
    channels: int = 1,
    device_index: Optional[int] = None,
    energy_threshold: float = 0.015,
    silence_timeout_sec: float = 1.5,
    max_duration_sec: float = 30.0,
    pre_buffer_sec: float = 0.3,
    block_duration_ms: int = 30,
) -> np.ndarray:
    """
    Record audio until silence is detected (VAD-based recording).

    Algorithm:
    1. Start recording in small blocks.
    2. When RMS energy exceeds threshold → mark as "speech started".
    3. Keep recording. If energy drops below threshold for silence_timeout → stop.
    4. Pre-buffer captures the first moments before speech was detected.

    Returns the recorded audio as a numpy array.
    """
    if sd is None:
        raise RuntimeError("sounddevice not installed")

    block_size = int(sample_rate * block_duration_ms / 1000)
    pre_buffer_blocks = int(pre_buffer_sec * sample_rate / block_size)
    silence_blocks_needed = int(silence_timeout_sec * sample_rate / block_size)
    max_blocks = int(max_duration_sec * sample_rate / block_size)

    # Rolling pre-buffer (circular list of recent blocks)
    pre_buffer: list = []
    recorded_blocks: list = []
    speech_started = False
    silence_count = 0
    total_blocks = 0

    logger.debug(f"VAD: threshold={energy_threshold}, silence_timeout={silence_timeout_sec}s")

    # Use InputStream for real-time block processing
    with sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype=DTYPE,
        device=device_index,
        blocksize=block_size,
    ) as stream:
        while total_blocks < max_blocks:
            block, overflowed = stream.read(block_size)
            if overflowed:
                logger.warning("Audio input overflow — data may be lost")

            mono_block = block.flatten() if channels == 1 else block[:, 0]
            energy = compute_rms(mono_block)

            if not speech_started:
                # Maintain pre-buffer
                pre_buffer.append(mono_block.copy())
                if len(pre_buffer) > pre_buffer_blocks:
                    pre_buffer.pop(0)

                if energy >= energy_threshold:
                    speech_started = True
                    # Include pre-buffer so we don't clip the start
                    recorded_blocks.extend(pre_buffer)
                    recorded_blocks.append(mono_block.copy())
                    silence_count = 0
                    logger.debug("Speech detected — recording started")
            else:
                recorded_blocks.append(mono_block.copy())
                if energy < energy_threshold:
                    silence_count += 1
                    if silence_count >= silence_blocks_needed:
                        logger.debug("Silence timeout — recording stopped")
                        break
                else:
                    silence_count = 0

            total_blocks += 1

    if not speech_started:
        logger.info("No speech detected in recording window")
        return np.array([], dtype=DTYPE)

    audio = np.concatenate(recorded_blocks)
    duration = len(audio) / sample_rate
    logger.info(f"Recorded {duration:.1f}s of speech ({len(audio)} samples)")
    return audio


# ── Playback ──────────────────────────────────────────────────

def play_audio(
    audio: np.ndarray,
    sample_rate: int = 22050,
    device_index: Optional[int] = None,
    blocking: bool = True,
) -> None:
    """Play a numpy array through the speaker."""
    if sd is None:
        raise RuntimeError("sounddevice not installed")
    logger.debug(f"Playing {len(audio)/sample_rate:.1f}s of audio")
    if blocking:
        sd.play(audio, samplerate=sample_rate, device=device_index, blocking=True)
    else:
        sd.play(audio, samplerate=sample_rate, device=device_index)


def play_wav_file(filepath: str, device_index: Optional[int] = None) -> None:
    """Play a WAV file through the speaker."""
    audio, sr = load_wav(filepath)
    play_audio(audio, sample_rate=sr, device_index=device_index)


def stop_playback() -> None:
    """Stop any currently playing audio."""
    if sd:
        sd.stop()


# ── WAV File I/O ──────────────────────────────────────────────

def save_wav(filepath: str, audio: np.ndarray, sample_rate: int = 16000) -> None:
    """Save numpy audio array to a WAV file (16-bit PCM)."""
    # Convert float32 [-1, 1] to int16
    audio_int16 = np.clip(audio * INT16_MAX, -INT16_MAX, INT16_MAX).astype(np.int16)
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

    logger.info(f"Saved WAV: {filepath} ({len(audio)/sample_rate:.1f}s)")


def load_wav(filepath: str) -> Tuple[np.ndarray, int]:
    """
    Load a WAV file, return (audio_float32, sample_rate).
    Converts to mono float32 regardless of source format.
    """
    with wave.open(str(filepath), "rb") as wf:
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        raw = wf.readframes(n_frames)

    # Decode raw bytes based on sample width
    if sampwidth == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / INT16_MAX
    elif sampwidth == 4:
        audio = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483647.0
    elif sampwidth == 1:
        audio = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    # Convert to mono if stereo
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    return audio, sr


# ── Audio Analysis ────────────────────────────────────────────

def compute_rms(audio: np.ndarray) -> float:
    """Compute Root Mean Square energy of audio signal."""
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio ** 2)))


def compute_peak(audio: np.ndarray) -> float:
    """Compute peak amplitude of audio signal."""
    if len(audio) == 0:
        return 0.0
    return float(np.max(np.abs(audio)))


def compute_db(audio: np.ndarray) -> float:
    """Compute signal level in decibels (dBFS)."""
    rms = compute_rms(audio)
    if rms < 1e-10:
        return -100.0
    return float(20 * np.log10(rms))


class AudioMeter:
    """
    Real-time audio level meter.
    Continuously reads from microphone and reports RMS / peak levels.
    Useful for tuning energy_threshold in config.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        block_duration_ms: int = 30,
        device_index: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.block_size = int(sample_rate * block_duration_ms / 1000)
        self.device_index = device_index
        self._running = False

    def run(self, duration_sec: float = 10.0) -> None:
        """Print audio levels for the specified duration."""
        if sd is None:
            raise RuntimeError("sounddevice not installed")

        print(f"Audio meter — listening for {duration_sec:.0f}s (Ctrl+C to stop)")
        print(f"{'RMS':>10} {'Peak':>10} {'dB':>8}  Level")
        print("-" * 50)

        blocks = int(duration_sec * self.sample_rate / self.block_size)

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=DTYPE,
            device=self.device_index,
            blocksize=self.block_size,
        ) as stream:
            for _ in range(blocks):
                block, _ = stream.read(self.block_size)
                audio = block.flatten()
                rms = compute_rms(audio)
                peak = compute_peak(audio)
                db = compute_db(audio)

                # Visual bar
                bar_len = int(rms * 200)
                bar = "█" * min(bar_len, 40)
                clip = " ⚠ CLIP" if peak > 0.95 else ""

                print(f"\r{rms:10.5f} {peak:10.5f} {db:7.1f}dB  {bar}{clip}", end="", flush=True)

        print()


# ── Signal Processing ─────────────────────────────────────────

def noise_gate(
    audio: np.ndarray,
    threshold: float = 0.01,
    release_samples: int = 1600,
) -> np.ndarray:
    """
    Simple noise gate — zero out samples below threshold.
    Applies a short release window to avoid harsh cutoffs.
    """
    if len(audio) == 0:
        return audio

    # Compute per-sample amplitude
    amplitude = np.abs(audio)
    gate_open = amplitude > threshold

    # Smooth the gate signal (release window)
    # After gate closes, keep it open for release_samples to avoid clipping
    smoothed = gate_open.copy()
    for i in range(1, len(smoothed)):
        if gate_open[i]:
            # Open gate and mark release window
            end = min(i + release_samples, len(smoothed))
            smoothed[i:end] = True

    # Apply gate
    result = audio.copy()
    result[~smoothed] = 0.0
    return result


def resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Resample audio to a different sample rate using linear interpolation.
    Lightweight — works without scipy (though scipy.signal.resample is better).
    """
    if orig_sr == target_sr:
        return audio

    try:
        from scipy.signal import resample as sci_resample
        num_samples = int(len(audio) * target_sr / orig_sr)
        return sci_resample(audio, num_samples).astype(np.float32)
    except ImportError:
        # Fallback: linear interpolation (less accurate but works)
        duration = len(audio) / orig_sr
        num_samples = int(duration * target_sr)
        indices = np.linspace(0, len(audio) - 1, num_samples)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


def normalize(audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
    """Normalize audio so peak amplitude equals target_peak."""
    peak = compute_peak(audio)
    if peak < 1e-10:
        return audio
    return (audio * (target_peak / peak)).astype(np.float32)


# ── CLI: Audio Utilities ─────────────────────────────────────

def main():
    """CLI interface for quick audio tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Aego Audio Utilities")
    sub = parser.add_subparsers(dest="command")

    # List devices
    sub.add_parser("devices", help="List audio devices")

    # Record test
    rec = sub.add_parser("record", help="Record and save to WAV")
    rec.add_argument("output", help="Output WAV file path")
    rec.add_argument("--duration", type=float, default=5.0, help="Duration in seconds")
    rec.add_argument("--device", type=int, default=None, help="Device index")

    # Play test
    play = sub.add_parser("play", help="Play a WAV file")
    play.add_argument("input", help="Input WAV file path")
    play.add_argument("--device", type=int, default=None, help="Device index")

    # Meter
    meter = sub.add_parser("meter", help="Audio level meter")
    meter.add_argument("--duration", type=float, default=10.0)
    meter.add_argument("--device", type=int, default=None)

    args = parser.parse_args()

    if args.command == "devices":
        for d in list_devices():
            ch_in = d["max_input_channels"]
            ch_out = d["max_output_channels"]
            kind = []
            if ch_in > 0:
                kind.append(f"in:{ch_in}")
            if ch_out > 0:
                kind.append(f"out:{ch_out}")
            print(f"  [{d['index']:2d}] {d['name']} ({', '.join(kind)})")

    elif args.command == "record":
        print(f"Recording {args.duration}s to {args.output}...")
        audio = record_audio(args.duration, device_index=args.device)
        save_wav(args.output, audio)
        print(f"Saved: {args.output}")

    elif args.command == "play":
        print(f"Playing {args.input}...")
        play_wav_file(args.input, device_index=args.device)

    elif args.command == "meter":
        meter = AudioMeter(device_index=args.device)
        meter.run(args.duration)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
