#!/usr/bin/env bash
# test-voice.sh — Test script for Aego Cyber Cafe voice pipeline.
#
# Tests each component independently, then runs end-to-end.
# Reports latency metrics for each stage.
#
# Usage:
#   chmod +x test-voice.sh
#   ./test-voice.sh              # run all tests
#   ./test-voice.sh --quick      # skip interactive tests
#   ./test-voice.sh --component mic      # test only microphone
#   ./test-voice.sh --component speaker  # test only speaker
#   ./test-voice.sh --component stt      # test only STT
#   ./test-voice.sh --component tts      # test only TTS
#   ./test-voice.sh --component e2e      # test full pipeline

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
SKIP=0
TEST_DIR=".openclaw/tmp/voice-tests"

# ── Helpers ───────────────────────────────────────────────────

log()  { echo -e "${BLUE}[TEST]${NC} $*"; }
pass() { echo -e "${GREEN}  ✅ PASS${NC}: $*"; ((PASS++)); }
fail() { echo -e "${RED}  ❌ FAIL${NC}: $*"; ((FAIL++)); }
skip() { echo -e "${YELLOW}  ⏭️  SKIP${NC}: $*"; ((SKIP++)); }
info() { echo -e "${CYAN}  ℹ️  INFO${NC}: $*"; }
section() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

time_start() { date +%s%N; }
time_ms() {
    local start=$1
    local end=$(date +%s%N)
    echo $(( (end - start) / 1000000 ))
}

# ── Parse args ────────────────────────────────────────────────

QUICK=false
COMPONENT="all"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick) QUICK=true; shift ;;
        --component) COMPONENT="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ── Setup ─────────────────────────────────────────────────────

mkdir -p "$TEST_DIR"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║  🎙️  Aego Cyber Cafe — Voice Pipeline Test Suite    ║"
echo "║  📍 Nyatike, Migori County, Kenya                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Test: Python Dependencies ────────────────────────────────

section "Python Dependencies"

test_import() {
    local module=$1
    local label=$2
    if python3 -c "import $module" 2>/dev/null; then
        pass "$label installed"
    else
        fail "$label not installed (pip install $module)"
    fi
}

test_import "sounddevice" "sounddevice"
test_import "numpy" "numpy"
test_import "scipy" "scipy"
test_import "yaml" "PyYAML"
test_import "requests" "requests"

# ── Test: Config File ────────────────────────────────────────

section "Configuration"

if [[ -f "config.yaml" ]]; then
    pass "config.yaml exists"
    # Validate YAML syntax
    if python3 -c "import yaml; yaml.safe_load(open('config.yaml'))" 2>/dev/null; then
        pass "config.yaml is valid YAML"
    else
        fail "config.yaml has syntax errors"
    fi
else
    fail "config.yaml not found"
fi

# ── Test: Microphone ─────────────────────────────────────────

if [[ "$COMPONENT" == "all" || "$COMPONENT" == "mic" ]]; then
    section "Microphone Input"

    # Check for audio devices
    MIC_DEVICES=$(python3 -c "
import sounddevice as sd
devices = sd.query_devices()
mics = [d for d in devices if d['max_input_channels'] > 0]
print(len(mics))
" 2>/dev/null || echo "0")

    if [[ "$MIC_DEVICES" -gt 0 ]]; then
        pass "Microphone device found ($MIC_DEVICES input device(s))"

        # List devices
        info "Input devices:"
        python3 -c "
import sounddevice as sd
for i, d in enumerate(sd.query_devices()):
    if d['max_input_channels'] > 0:
        print(f'  [{i}] {d[\"name\"]} (ch={d[\"max_input_channels\"]})')
" 2>/dev/null

        # Record test
        if [[ "$QUICK" == "false" ]]; then
            log "Recording 3 seconds of audio..."
            t=$(time_start)
            python3 -c "
import sounddevice as sd
import numpy as np
audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype='float32')
sd.wait()
rms = np.sqrt(np.mean(audio**2))
peak = np.max(np.abs(audio))
print(f'RMS={rms:.5f} Peak={peak:.5f}')
import wave
with wave.open('$TEST_DIR/mic-test.wav', 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes((audio.flatten() * 32767).astype(np.int16).tobytes())
" 2>/dev/null
            ms=$(time_ms $t)
            if [[ -f "$TEST_DIR/mic-test.wav" ]]; then
                pass "Microphone recording OK (${ms}ms)"
            else
                fail "Microphone recording failed"
            fi
        fi
    else
        fail "No microphone devices found"
    fi
fi

# ── Test: Speaker ────────────────────────────────────────────

if [[ "$COMPONENT" == "all" || "$COMPONENT" == "speaker" ]]; then
    section "Speaker Output"

    SPEAKER_DEVICES=$(python3 -c "
import sounddevice as sd
devices = sd.query_devices()
spkrs = [d for d in devices if d['max_output_channels'] > 0]
print(len(spkrs))
" 2>/dev/null || echo "0")

    if [[ "$SPEAKER_DEVICES" -gt 0 ]]; then
        pass "Speaker device found ($SPEAKER_DEVICES output device(s))"

        if [[ "$QUICK" == "false" ]]; then
            log "Playing test tone (440 Hz, 1 second)..."
            python3 -c "
import sounddevice as sd
import numpy as np
sr = 22050
t = np.linspace(0, 1.0, sr, dtype=np.float32)
tone = 0.3 * np.sin(2 * np.pi * 440 * t)
# Fade in/out
fade = 1000
tone[:fade] *= np.linspace(0, 1, fade)
tone[-fade:] *= np.linspace(1, 0, fade)
sd.play(tone, samplerate=sr, blocking=True)
print('Tone played successfully')
" 2>/dev/null && pass "Speaker playback OK" || fail "Speaker playback failed"
        fi
    else
        fail "No speaker devices found"
    fi
fi

# ── Test: Whisper.cpp ────────────────────────────────────────

if [[ "$COMPONENT" == "all" || "$COMPONENT" == "stt" ]]; then
    section "Whisper.cpp (Speech-to-Text)"

    WHISPER_BIN=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('config.yaml'))
print(cfg.get('stt', {}).get('whisper_bin', '/usr/local/bin/whisper-cli'))
" 2>/dev/null)

    WHISPER_MODEL=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('config.yaml'))
use = cfg.get('stt', {}).get('use_model', 'tiny')
if use == 'base':
    print(cfg.get('stt', {}).get('model_path_base', ''))
else:
    print(cfg.get('stt', {}).get('model_path', ''))
" 2>/dev/null)

    if [[ -x "$WHISPER_BIN" ]]; then
        pass "Whisper binary found: $WHISPER_BIN"
    else
        skip "Whisper binary not found: $WHISPER_BIN"
    fi

    if [[ -f "$WHISPER_MODEL" ]]; then
        pass "Whisper model found: $WHISPER_MODEL"
    else
        skip "Whisper model not found: $WHISPER_MODEL"
    fi

    # Test transcription if we have a test recording
    if [[ -x "$WHISPER_BIN" && -f "$WHISPER_MODEL" && -f "$TEST_DIR/mic-test.wav" ]]; then
        log "Testing transcription..."
        t=$(time_start)
        OUTPUT=$("$WHISPER_BIN" -m "$WHISPER_MODEL" -f "$TEST_DIR/mic-test.wav" --no-timestamps -t 2 2>/dev/null || echo "")
        ms=$(time_ms $t)
        if [[ -n "$OUTPUT" ]]; then
            pass "Whisper transcription OK (${ms}ms)"
            info "Output: $OUTPUT"
        else
            fail "Whisper transcription returned empty"
        fi
    elif [[ -x "$WHISPER_BIN" && -f "$WHISPER_MODEL" ]]; then
        skip "No test recording to transcribe"
    fi
fi

# ── Test: Piper TTS ──────────────────────────────────────────

if [[ "$COMPONENT" == "all" || "$COMPONENT" == "tts" ]]; then
    section "Piper TTS (Text-to-Speech)"

    PIPER_BIN=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('config.yaml'))
print(cfg.get('tts', {}).get('piper_bin', '/usr/local/bin/piper'))
" 2>/dev/null)

    PIPER_VOICE=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('config.yaml'))
voices = cfg.get('tts', {}).get('voices', {})
default = cfg.get('tts', {}).get('default_voice', 'sw')
print(voices.get(default, ''))
" 2>/dev/null)

    if [[ -x "$PIPER_BIN" ]]; then
        pass "Piper binary found: $PIPER_BIN"
    else
        skip "Piper binary not found: $PIPER_BIN"
    fi

    if [[ -f "$PIPER_VOICE" ]]; then
        pass "Piper voice model found: $PIPER_VOICE"
    else
        skip "Piper voice model not found: $PIPER_VOICE"
    fi

    # Test TTS synthesis
    if [[ -x "$PIPER_BIN" && -f "$PIPER_VOICE" ]]; then
        log "Testing TTS synthesis..."
        t=$(time_start)
        echo "Habari! Karibu Aego Cyber Cafe." | "$PIPER_BIN" --model "$PIPER_VOICE" \
            --output_file "$TEST_DIR/tts-test.wav" 2>/dev/null
        ms=$(time_ms $t)
        if [[ -f "$TEST_DIR/tts-test.wav" ]]; then
            SIZE=$(stat -c%s "$TEST_DIR/tts-test.wav" 2>/dev/null || stat -f%z "$TEST_DIR/tts-test.wav" 2>/dev/null)
            pass "Piper TTS synthesis OK (${ms}ms, ${SIZE} bytes)"

            # Play the synthesized audio
            if [[ "$QUICK" == "false" && "$SPEAKER_DEVICES" -gt 0 ]]; then
                log "Playing synthesized speech..."
                python3 -c "
import sounddevice as sd
import wave
import numpy as np
with wave.open('$TEST_DIR/tts-test.wav') as wf:
    sr = wf.getframerate()
    audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32767.0
sd.play(audio, samplerate=sr, blocking=True)
" 2>/dev/null && pass "TTS playback OK" || fail "TTS playback failed"
            fi
        else
            fail "Piper TTS synthesis failed"
        fi
    fi
fi

# ── Test: Ollama / Gemma 4 ──────────────────────────────────

section "Ollama / Gemma 4 LLM"

OLLAMA_EP=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('config.yaml'))
print(cfg.get('ollama', {}).get('endpoint', 'http://localhost:11434'))
" 2>/dev/null)

OLLAMA_MODEL=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('config.yaml'))
print(cfg.get('ollama', {}).get('model', 'gemma4-e4b'))
" 2>/dev/null)

# Check if Ollama is running
if curl -s --connect-timeout 3 "$OLLAMA_EP/api/tags" >/dev/null 2>&1; then
    pass "Ollama is running at $OLLAMA_EP"

    # Check if model is available
    MODELS=$(curl -s "$OLLAMA_EP/api/tags" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = [m['name'] for m in data.get('models', [])]
print(' '.join(models))
" 2>/dev/null || echo "")

    if echo "$MODELS" | grep -qi "gemma"; then
        pass "Gemma model available: $MODELS"

        # Quick LLM test
        log "Testing LLM response..."
        t=$(time_start)
        RESPONSE=$(curl -s --max-time 15 "$OLLAMA_EP/api/chat" \
            -d "{\"model\":\"$OLLAMA_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in Swahili in one sentence.\"}],\"stream\":false}" 2>/dev/null \
            | python3 -c "import sys,json; print(json.load(sys.stdin).get('message',{}).get('content',''))" 2>/dev/null || echo "")
        ms=$(time_ms $t)

        if [[ -n "$RESPONSE" ]]; then
            pass "LLM response OK (${ms}ms)"
            info "Response: $RESPONSE"
        else
            fail "LLM returned empty response"
        fi
    else
        skip "No Gemma model found. Run: ollama pull $OLLAMA_MODEL"
    fi
else
    skip "Ollama not running at $OLLAMA_EP"
fi

# ── Test: End-to-End Pipeline ────────────────────────────────

if [[ "$COMPONENT" == "all" || "$COMPONENT" == "e2e" ]]; then
    section "End-to-End Pipeline"

    # Test that all Python modules can be imported
    log "Testing module imports..."
    if python3 -c "
import sys
sys.path.insert(0, '.')
from audio_utils import list_devices, compute_rms
from stt_module import SpeechToText, TranscriptionResult
from tts_module import TextToSpeech, TTSResult
print('All modules imported successfully')
" 2>/dev/null; then
        pass "All Python modules importable"
    else
        fail "Module import failed"
    fi

    # Test config loading
    if python3 -c "
import yaml
with open('config.yaml') as f:
    cfg = yaml.safe_load(f)
assert 'stt' in cfg, 'Missing stt config'
assert 'tts' in cfg, 'Missing tts config'
assert 'ollama' in cfg, 'Missing ollama config'
assert 'vad' in cfg, 'Missing vad config'
print('Config validation passed')
" 2>/dev/null; then
        pass "Config validation OK"
    else
        fail "Config validation failed"
    fi

    # Test pipeline initialization (without running)
    if python3 -c "
import sys, logging
logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, '.')
from voice_pipeline import VoicePipeline
pipeline = VoicePipeline('config.yaml')
print(f'Pipeline initialized: mode={pipeline.mode}')
" 2>/dev/null; then
        pass "Pipeline initialization OK"
    else
        fail "Pipeline initialization failed"
    fi

    # Full E2E test (interactive)
    if [[ "$QUICK" == "false" ]]; then
        echo ""
        log "Full end-to-end test (speak → transcribe → respond → speak)"
        read -p "  Press Enter to start (or 's' to skip): " REPLY
        if [[ "$REPLY" != "s" && "$REPLY" != "S" ]]; then
            info "Starting pipeline in push-to-talk mode for 1 interaction..."
            timeout 30 python3 -c "
import sys, logging
logging.basicConfig(level=logging.INFO)
sys.path.insert(0, '.')
from voice_pipeline import VoicePipeline
pipeline = VoicePipeline('config.yaml')
pipeline.mode = 'push_to_talk'
print('Press Enter to speak...')
input()
pipeline._process_interaction()
print('E2E test complete')
" 2>/dev/null && pass "End-to-end pipeline OK" || fail "End-to-end pipeline failed"
        else
            skip "Full E2E test (skipped by user)"
        fi
    fi
fi

# ── Summary ──────────────────────────────────────────────────

section "Test Summary"
echo ""
echo -e "  ${GREEN}✅ Passed: $PASS${NC}"
echo -e "  ${RED}❌ Failed: $FAIL${NC}"
echo -e "  ${YELLOW}⏭️  Skipped: $SKIP${NC}"
echo ""

if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Some tests failed. Check output above.${NC}"
    exit 1
fi
