# Aego Cyber Cafe — Setup Guide

**Location:** Nyatike, Migori County, Kenya
**Hardware:** Raspberry Pi 5 (8GB RAM)

This guide walks you through setting up AI services at Aego Cyber Cafe from scratch. Follow each step in order. If something goes wrong, check the [Troubleshooting](#troubleshooting) section at the end.

---

## What You're Building

After setup, Aego Cyber Cafe will have:

| Service | What It Does | How to Access |
|---------|-------------|---------------|
| **Ollama** | Runs AI models locally (no internet needed) | `http://localhost:11434` |
| **OpenClaw** | AI assistant platform (WhatsApp, Telegram, voice) | `http://localhost:3000` |
| **n8n** | Workflow automation (appointments, SMS, etc.) | `http://localhost:5678` |
| **Piper TTS** | Speaks responses in Swahili | Built into OpenClaw |
| **Whisper** | Listens to voice messages | Built into OpenClaw |

---

## Step 1: Hardware Assembly

Before running any software, connect all hardware to the Raspberry Pi 5.

### What You Need

- [x] Raspberry Pi 5 (8GB RAM) with heatsink/fan
- [x] MicroSD card (64GB+ recommended, with Raspberry Pi OS pre-installed)
- [x] USB microphone (any basic USB mic works)
- [x] Speaker or headphones (3.5mm jack or USB)
- [x] Webcam (USB, for vision features — optional)
- [x] UPS or battery backup (Kenya Power can be unreliable)
- [x] Ethernet cable or WiFi connection
- [x] Monitor + keyboard (for initial setup only)
- [x] USB drive (for backups — optional but recommended)

### Assembly Steps

1. **Insert the MicroSD card** into the Pi 5's card slot
2. **Connect the USB microphone** to any USB port
3. **Connect the speaker** to the 3.5mm audio jack (or USB port)
4. **Connect the webcam** to a USB port (if you have one)
5. **Connect Ethernet** cable from your router to the Pi (WiFi works too, but Ethernet is more reliable)
6. **Connect the UPS** and plug the Pi's power supply into the UPS
7. **Connect monitor + keyboard** (you'll only need these for initial setup)
8. **Power on** the Pi — wait for the desktop to appear

### First Boot Configuration

When Raspberry Pi OS first boots:

1. Set your timezone: **Africa/Nairobi**
2. Set a strong password (write it down somewhere safe)
3. Connect to WiFi if not using Ethernet
4. Open a terminal (black icon on the taskbar)
5. Run: `sudo raspi-config`
   - Go to **Interface Options** → Enable **SSH**
   - Go to **Interface Options** → Enable **Audio** (select your speaker)
   - Go to **Localisation Options** → Set timezone to **Africa/Nairobi**
6. Reboot when done

---

## Step 2: Run the Setup Script

The setup script installs everything automatically. It takes **1-2 hours** depending on your internet speed (model downloads are large).

### Transfer Setup Files

Copy the `foundation/` folder to your Pi. You can:

**Option A — USB drive:**
```bash
# On your computer, copy the foundation folder to a USB drive
# On the Pi, open terminal and run:
cp -r /media/usb/foundation /home/pi/aego-setup
```

**Option B — Over SSH:**
```bash
# From your computer:
scp -r foundation/ pi@<PI_IP_ADDRESS>:/home/pi/aego-setup/
```

**Option C — Download from GitHub** (if files are uploaded):
```bash
cd /home/pi
git clone <repository-url> aego-setup
```

### Run the Script

```bash
cd /home/pi/aego-setup
chmod +x setup-pi.sh
sudo bash setup-pi.sh
```

**What happens:**
1. Updates the system (5-10 min)
2. Creates directories at `/opt/aego/`
3. Installs Ollama and downloads AI models (30-60 min — this is the big download)
4. Installs OpenClaw Gateway
5. Installs Piper TTS with Swahili voice (5 min)
6. Builds Whisper from source (10-20 min)
7. Installs n8n
8. Configures firewall and auto-start services

**Do NOT turn off the Pi during setup.** The script logs everything to `/opt/aego/logs/setup-*.log` so you can check progress.

When it finishes, you'll see a summary with service URLs.

---

## Step 3: Copy the OpenClaw Configuration

```bash
cp openclaw-config.yaml ~/.openclaw/config.yaml
```

Edit the file if you need to change anything:

```bash
nano ~/.openclaw/config.yaml
```

**Important settings to check:**

- **WhatsApp** — enabled by default (you'll pair in the next step)
- **Telegram** — add your bot token if you have one
- **Google API key** — only needed for cloud fallback (optional)

---

## Step 4: Configure WhatsApp Bridge

WhatsApp lets customers message the AI assistant directly from their phones.

### Setup Steps

1. **Start OpenClaw:**
   ```bash
   openclaw gateway start
   ```

2. **Set up WhatsApp:**
   ```bash
   openclaw channel whatsapp setup
   ```

3. **Scan the QR code** that appears:
   - Open WhatsApp on a dedicated phone (a phone number just for the cafe)
   - Go to **Settings → Linked Devices → Link a Device**
   - Scan the QR code shown in the terminal

4. **Test it:**
   - Send a message to the cafe's WhatsApp number from your personal phone
   - The AI should respond within a few seconds

### Tips

- Use a **dedicated phone number** for the cafe (not your personal number)
- Keep the phone plugged in and connected to WiFi
- The WhatsApp session persists across reboots
- If the session expires, re-run `openclaw channel whatsapp setup`

---

## Step 5: Test the Voice Pipeline

Test that the microphone, AI, and speaker all work together.

### Test Microphone

```bash
# Record 5 seconds of audio
arecord -d 5 -f cd /tmp/test-mic.wav

# Play it back
aplay /tmp/test-mic.wav
```

If you hear your voice, the microphone and speaker work.

### Test Whisper (Speech-to-Text)

```bash
# Record and transcribe
arecord -d 5 -f cd /tmp/test-stt.wav

/opt/aego/whisper.cpp/build/bin/whisper-cli \
    -m /opt/aego/whisper.cpp/models/ggml-tiny.bin \
    -f /tmp/test-stt.wav \
    --language sw
```

You should see your words transcribed in the terminal.

### Test Piper (Text-to-Speech)

```bash
echo "Habari! Karibu Aego Cyber Cafe" | piper \
    --model /opt/aego/models/piper/sw_ke-siwi-medium.onnx \
    --output_file /tmp/test-tts.wav

aplay /tmp/test-tts.wav
```

You should hear the greeting spoken in Swahili.

### Test Ollama (AI Model)

```bash
curl http://localhost:11434/api/generate -d '{
    "model": "gemma4:4b",
    "prompt": "Habari yako? Unaitwa nani?",
    "stream": false
}' | jq -r '.response'
```

The AI should respond in Swahili.

### Test Full Pipeline via OpenClaw

Open a browser and go to `http://localhost:3000`. Type a message and see if the AI responds.

---

## Step 6: Set Up n8n Workflows (Optional)

n8n lets you create automated workflows — like appointment booking, payment confirmations, or SMS notifications.

1. Open a browser and go to `http://<PI_IP>:5678`
2. Login with:
   - Username: `admin`
   - Password: `changeme-aego-2024` (change this immediately!)
3. Create your first workflow or import from the `skills/` directory

---

## Step 7: Verify Everything is Running

```bash
# Check all services
curl http://localhost:11434/api/tags    # Ollama
curl http://localhost:3000/health       # OpenClaw
curl http://localhost:5678/healthz      # n8n

# Check the health dashboard
cat /opt/aego/logs/health/health-state.json | jq .

# Check system resources
htop
```

---

## Daily Operations

### Starting Services After a Power Outage

All services auto-start on boot. If something doesn't come back:

```bash
sudo systemctl start ollama
openclaw gateway start
sudo systemctl start aego-n8n
```

### Checking System Health

```bash
# Run a manual health check
bash /opt/aego/health-check.sh

# View recent health logs
tail -50 /opt/aego/logs/health/health.log
```

### Viewing Logs

```bash
# OpenClaw logs
openclaw gateway logs

# n8n logs
journalctl -u aego-n8n -f

# System health
tail -f /opt/aego/logs/health/health.log
```

### Manual Backup

```bash
bash /opt/aego/backup.sh
```

Backups run automatically at 2:00 AM daily. Insert a USB drive and backups will copy there too.

---

## Troubleshooting

### "Ollama is not responding"

```bash
# Check if Ollama is running
systemctl status ollama

# Restart it
sudo systemctl restart ollama

# Check for errors
journalctl -u ollama --no-pager -n 50
```

### "No audio output / microphone not working"

```bash
# List audio devices
aplay -l          # Speakers
arecord -l        # Microphones

# Check volume
alsamixer

# Set default audio output (3.5mm jack)
sudo raspi-config  → System Options → Audio → Headphones

# Test
speaker-test -t wav -c 2
```

### "WhatsApp disconnected"

```bash
# Check WhatsApp session status
openclaw channel whatsapp status

# Re-pair
openclaw channel whatsapp setup
```

### "AI responses are very slow"

The Pi 5 with 8GB RAM can run Gemma 4 4B, but responses take 10-30 seconds. This is normal for local AI. If it's slower than that:

```bash
# Check CPU temperature (throttling slows everything down)
vcgencmd measure_temp

# If temp > 75°C, improve cooling:
# - Add a heatsink + fan
# - Move the Pi to a ventilated area
# - Reduce model size (switch to qwen3.5:3b)
```

To switch to the smaller, faster model:
```bash
nano ~/.openclaw/config.yaml
# Change "primary" model from gemma4:4b to qwen3.5:3b
openclaw gateway restart
```

### "Disk space full"

```bash
# Check what's using space
du -sh /opt/aego/* | sort -rh
du -sh ~/.ollama/models/* | sort -rh

# Clean up old logs
find /opt/aego/logs -name "*.log" -mtime +14 -delete

# Clean up old backups
find /opt/aego/data/backups -name "*.tar.gz" -mtime +7 -delete
```

### "Power went out and Pi won't boot"

1. Unplug the Pi
2. Remove the MicroSD card
3. Insert it into a computer
4. Check if the filesystem is corrupted — if yes, re-flash Raspberry Pi OS
5. Re-run `setup-pi.sh` (it's safe to run again)
6. Restore from backup: `tar -xzf /path/to/backup.tar.gz -C /`

### "n8n shows 'Unauthorized'"

The default password is `changeme-aego-2024`. To change it:

```bash
sudo nano /etc/systemd/system/aego-n8n.service
# Change N8N_BASIC_AUTH_PASSWORD
sudo systemctl daemon-reload
sudo systemctl restart aego-n8n
```

---

## Network Diagram

```
                    ┌─────────────────────┐
                    │   Internet (Safaricom│
                    │   / Airtel / Telkom) │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │     WiFi Router      │
                    │   (192.168.1.1)      │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │  Raspberry Pi 5      │
                    │  (192.168.1.x)       │
                    │                      │
                    │  :11434 → Ollama     │
                    │  :3000  → OpenClaw   │
                    │  :5678  → n8n        │
                    └──────┬──┬──┬────────┘
                           │  │  │
              ┌────────────┘  │  └────────────┐
              │               │               │
        ┌─────┴─────┐  ┌─────┴─────┐  ┌─────┴─────┐
        │  USB Mic   │  │  Speaker   │  │  Webcam    │
        └───────────┘  └───────────┘  └───────────┘

  Customer phones ←→ WhatsApp/Telegram ←→ OpenClaw → Ollama (AI)
```

---

## File Locations Reference

| Path | What's There |
|------|-------------|
| `/opt/aego/` | Main installation directory |
| `/opt/aego/models/` | AI models (Piper voice, Whisper) |
| `/opt/aego/data/` | Databases, n8n data, backups |
| `/opt/aego/logs/` | All log files |
| `/opt/aego/skills/` | OpenClaw skills |
| `~/.openclaw/config.yaml` | OpenClaw configuration |
| `~/.ollama/models/` | Ollama model storage |

---

## Security Notes

- **Firewall** is configured to only allow local network access
- **n8n** has default credentials — change the password immediately
- **WhatsApp** session is stored locally — don't share the SD card
- **Backups** don't include passwords — store credentials separately
- The AI models run **entirely offline** — no data leaves the Pi (except when using cloud fallback)

---

## Getting Help

If you're stuck:

1. Check the logs: `tail -100 /opt/aego/logs/health/health.log`
2. Run a health check: `bash /opt/aego/health-check.sh`
3. Restart everything: `sudo systemctl restart ollama && openclaw gateway restart`
4. Re-run setup: `sudo bash setup-pi.sh` (safe to run multiple times)
5. Restore from backup if needed

---

*Last updated: 2026-07-19*
*Aego Cyber Cafe — Nyatike, Migori County, Kenya*
