# Aego Cyber Cafe — API Server

Lightweight FastAPI server for Aego Cyber Cafe, Nyatike, Migori County, Kenya.

Replaces the OpenClaw foundation layer with a purpose-built, low-overhead API server designed for a Raspberry Pi 5 with 8GB RAM.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Server (main.py)                   │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ ┌──────────────────┐ │
│  │ CV Route │ │Gov Route│ │Voice Route│ │ Admin Route      │ │
│  └────┬────┘ └────┬────┘ └─────┬─────┘ └────────┬─────────┘ │
│       │           │            │                  │           │
│  ┌────┴───────────┴────────────┴──────────────────┴────────┐ │
│  │              Session Manager + Request Queue            │ │
│  └───────────────────────┬──────────────────────────────────┘ │
│                          │                                    │
│  ┌───────────┐ ┌─────────┴──────┐ ┌────────────┐            │
│  │ Ollama LLM│ │ Whisper.cpp STT│ │ Piper TTS  │            │
│  └───────────┘ └────────────────┘ └────────────┘            │
│                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ WhatsApp Bot │ │ Telegram Bot │ │ M-Pesa (Daraja API)  │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start (Development)

```bash
cd engineering/server

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or create .env file)
export OLLAMA_HOST=http://localhost:11434
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=your-secure-password

# Run the server
python main.py
# Or:
uvicorn main:app --reload --port 8000
```

Server starts at http://localhost:8000
- API docs: http://localhost:8000/docs
- Kiosk UI: http://localhost:8000/kiosk/
- Health check: http://localhost:8000/api/health

## Production (systemd)

```bash
# Create system user
sudo useradd -r -s /bin/false aego

# Create directories
sudo mkdir -p /opt/aego/{data,output,logs,server,skills,kiosk,voice}
sudo chown -R aego:aego /opt/aego

# Copy files
sudo cp -r engineering/server/* /opt/aego/server/
sudo cp -r engineering/skills/* /opt/aego/skills/
sudo cp -r engineering/kiosk/kiosk/public/* /opt/aego/kiosk/
sudo cp -r engineering/voice/* /opt/aego/voice/

# Set up Python environment
python3 -m venv /opt/aego/venv
/opt/aego/venv/bin/pip install -r /opt/aego/server/requirements.txt

# Create .env file
sudo cp .env.example /opt/aego/.env
sudo nano /opt/aego/.env  # Edit with real values

# Install systemd service
sudo cp systemd/aego-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aego-server
sudo systemctl start aego-server

# Check status
sudo systemctl status aego-server
sudo journalctl -u aego-server -f
```

## Docker

```bash
# Build
docker build -t aego-server -f engineering/server/Dockerfile .

# Run
docker run -d \
  --name aego-server \
  -p 8000:8000 \
  -v aego-data:/opt/aego/data \
  -v aego-output:/opt/aego/output \
  --env-file .env \
  aego-server
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `gemma4:4b` | Primary LLM model |
| `OLLAMA_FALLBACK_MODEL` | `qwen3.5:3b` | Fallback model (translation) |
| `OLLAMA_TIMEOUT` | `60` | Ollama request timeout (seconds) |
| `WHATSAPP_TOKEN` | — | WhatsApp Business Cloud API token |
| `WHATSAPP_PHONE_ID` | — | WhatsApp phone number ID |
| `WHATSAPP_VERIFY_TOKEN` | `aego_verify_token` | Webhook verification token |
| `TELEGRAM_TOKEN` | — | Telegram bot token |
| `MPESA_CONSUMER_KEY` | — | M-Pesa Daraja consumer key |
| `MPESA_CONSUMER_SECRET` | — | M-Pesa Daraja consumer secret |
| `MPESA_SHORTCODE` | `174379` | M-Pesa shortcode |
| `MPESA_PASSKEY` | — | M-Pesa passkey |
| `MPESA_CALLBACK_URL` | — | Callback URL for M-Pesa |
| `MPESA_ENV` | `sandbox` | `sandbox` or `production` |
| `ADMIN_USERNAME` | `admin` | Admin dashboard username |
| `ADMIN_PASSWORD` | `aego2026` | Admin dashboard password |
| `DATA_DIR` | `/opt/aego/data` | Data directory (SQLite DB) |
| `OUTPUT_DIR` | `/opt/aego/output` | Generated files output |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `WORKERS` | `1` | Uvicorn workers (keep 1 for Pi) |
| `LOG_LEVEL` | `info` | Logging level |
| `SESSION_TTL_MINUTES` | `30` | Session auto-purge time |

## API Endpoints

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/` | Service info |
| GET | `/docs` | Swagger UI |

### CV Writing (`/api/cv`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/cv/start` | Begin CV session |
| POST | `/api/cv/{id}/personal` | Add personal info |
| POST | `/api/cv/{id}/education` | Add education |
| POST | `/api/cv/{id}/experience` | Add work experience |
| POST | `/api/cv/{id}/skills` | Add skills |
| POST | `/api/cv/{id}/generate` | Generate CV PDF |
| GET | `/api/cv/{id}/download` | Download CV file |

### Government Services (`/api/gov`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/gov/services` | List all services |
| POST | `/api/gov/{type}/start` | Begin service session |
| POST | `/api/gov/{id}/fields` | Submit required fields |
| POST | `/api/gov/{id}/validate` | Validate fields |
| POST | `/api/gov/{id}/generate` | Generate filled form |

### Translation (`/api/translate`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/translate` | Translate text |
| POST | `/api/translate/voice` | Translate audio |

### Voice Pipeline (`/api/voice`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/voice/transcribe` | Audio → text |
| POST | `/api/voice/synthesize` | Text → audio |
| POST | `/api/voice/synthesize/audio` | Text → WAV bytes |
| POST | `/api/voice/chat` | Full voice pipeline |
| WS | `/api/voice/stream` | Real-time voice streaming |

### M-Pesa Payments (`/api/mpesa`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/mpesa/stk-push` | Initiate STK push |
| POST | `/api/mpesa/callback` | Safaricom callback |
| GET | `/api/mpesa/status/{id}` | Check payment status |

### Admin Dashboard (`/api/admin`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/stats` | Today's stats |
| GET | `/api/admin/requests` | Recent requests |
| GET | `/api/admin/payments` | Recent payments |
| GET | `/api/admin/health` | System health |
| POST | `/api/admin/approve/{id}` | Approve document |

### Webhooks
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/whatsapp/webhook` | WhatsApp verification |
| POST | `/api/whatsapp/webhook` | WhatsApp messages |
| POST | `/api/telegram/webhook` | Telegram messages |

## Skills Integration

Routes import from existing skills:

| Route | Skill Module | Location |
|-------|-------------|----------|
| `routes/cv.py` | `cv-generator.py` | `skills/cv-writer/` |
| `routes/gov.py` | `form-filler.py`, `service-catalog.json` | `skills/gov-services/` |
| `routes/mpesa.py` | `mpesa-client.py` | `skills/mpesa/` |
| `routes/voice.py` | `stt-module.py`, `tts-module.py` | `voice/` |
| `routes/translate.py` | Ollama API | via `config.OLLAMA_HOST` |
| `routes/whatsapp.py` | WhatsApp Business API | via `config.WHATSAPP_*` |
| `routes/telegram.py` | Telegram Bot API | via `config.TELEGRAM_TOKEN` |

## Session Management

- UUID-based sessions stored in memory (no database for sessions)
- Auto-purge after 30 minutes of inactivity
- Thread-safe via asyncio locks
- No persistent customer data — ephemeral by design

## Request Queue

LLM requests are queued because Ollama handles one request at a time:
- FIFO with priority (voice > text)
- 60-second timeout
- 1 retry on failure
- Progress notifications

## Memory Optimization (Raspberry Pi 5)

- Single uvicorn worker
- In-memory sessions (no ORM overhead)
- SQLite for transactions (lightweight)
- Lazy imports for heavy modules (voice pipeline)
- Queue prevents LLM overload
- Conservative model defaults (4B parameter)

## License

Internal use — Aego Cyber Cafe, Nyatike, Migori County, Kenya.
