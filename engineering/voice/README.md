# Aego Cyber Cafe — Voice Pipeline

Voice AI system for rural Kenyan customers at Aego Cyber Cafe, Nyatike, Migori County.

## Languages Supported

| Language | Code | Status |
|----------|------|--------|
| Swahili  | sw   | Primary (TTS + STT) |
| English  | en   | Full support |
| Dholuo   | lu   | STT only (no TTS voice yet) |
| Kikuyu   | ki   | STT only (no TTS voice yet) |

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  USB Mic    │────▶│   VAD    │────▶│   STT    │────▶│   LLM    │
│ (PyAudio)   │     │ (energy) │     │(Whisper/ │     │ (Gemma 4 │
└─────────────┘     └──────────┘     │ Gemma)   │     │ via Ollama)│
                                      └──────────┘     └────┬─────┘
                                                            │
                                                     ┌──────▼──────┐
                                                     │    TTS      │
                                                     │  (Piper)    │
                                                     └──────┬──────┘
                                                            │
                                                     ┌──────▼──────┐
                                                     │  USB Speaker│
                                                     └─────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install external tools
#    Whisper.cpp: https://github.com/ggerganov/whisper.cpp
#    Piper TTS:   https://github.com/rhasspy/piper
#    Ollama:      https://ollama.ai

# 3. Download models
# Whisper tiny model (~75 MB)
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin \
  -O ~/models/ggml-tiny.bin

# Piper Swahili voice
# See: https://github.com/rhasspy/piper/blob/master/VOICES.md

# Gemma 4 via Ollama
ollama pull gemma4-e4b

# 4. Configure
nano config.yaml   # set device indices, model paths

# 5. Run tests
./test-voice.sh

# 6. Start the pipeline
python3 voice-pipeline.py
```

## Files

| File | Description |
|------|-------------|
| `voice-pipeline.py` | Main orchestrator — ties all components together |
| `stt-module.py` | Speech-to-text (Whisper.cpp + Gemma audio fallback) |
| `tts-module.py` | Text-to-speech (Piper TTS) |
| `wake-word.py` | Wake word detection ("Hey Aego") |
| `audio-utils.py` | Microphone, speaker, VAD, noise gate, WAV I/O |
| `config.yaml` | All configuration (devices, models, thresholds) |
| `test-voice.sh` | Component and end-to-end tests |
| `requirements.txt` | Python dependencies |

## Operating Modes

### Push-to-Talk (default, most reliable)
```bash
python3 voice-pipeline.py --mode push_to_talk
```
Press Enter to start recording. Best for the cyber cafe counter.

### Always Listening (convenient, more CPU)
```bash
python3 voice-pipeline.py --mode always_listening
```
VAD detects when someone starts speaking. Uses more CPU.

### Wake Word (hands-free)
```bash
python3 voice-pipeline.py --mode wake_word
```
Say "Aego" to activate. Requires Porcupine or uses energy fallback.

## Configuration

Edit `config.yaml` to tune:

- **Microphone/Speaker device index** — run `python3 audio-utils.py devices`
- **VAD energy threshold** — run `python3 audio-utils.py meter` to see ambient levels
- **Whisper model** — `tiny` (fast) or `base` (better accuracy)
- **LLM temperature** — lower = more consistent, higher = more creative
- **TTS speed** — `0.8` for slower/clearer speech

## Performance Notes (Raspberry Pi 5)

- Whisper tiny: ~1-2s latency for 5s audio
- Whisper base: ~3-5s latency for 5s audio
- Gemma 4 E4B: ~2-5s for typical response
- Piper TTS: <0.5s for short sentences
- Total round-trip: 5-15s (use streaming TTS to reduce perceived latency)

## Troubleshooting

```bash
# No microphone detected
python3 audio-utils.py devices

# Audio too quiet/loud
python3 audio-utils.py meter --duration 15

# Whisper not finding model
ls ~/models/ggml-*.bin

# Ollama not responding
curl http://localhost:11434/api/tags

# Full test suite
./test-voice.sh
```
