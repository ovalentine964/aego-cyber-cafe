# Aego Cyber Cafe — Deployment Guide
## From Code to Running System

---

## What You Need to Buy

| Item | Price (KES) | Price (USD) | Where |
|------|-------------|-------------|-------|
| Raspberry Pi 5 (8GB) | ~10,000 | ~80 | Jumia, AliExpress |
| 64GB microSD (Class 10) | ~1,200 | ~10 | Jumia |
| USB Microphone | ~1,200 | ~10 | Jumia |
| USB Speaker | ~1,800 | ~15 | Jumia |
| Webcam (for form scanning) | ~2,400 | ~20 | Jumia |
| UPS Battery Pack (10,000mAh+) | ~3,000 | ~25 | Jumia |
| Pi case + power supply | ~1,800 | ~15 | Jumia |
| **Total** | **~21,400** | **~175** | |

You already have: printer, existing PC/laptop, WiFi router, M-Pesa paybill.

---

## Step-by-Step Setup (Day 1)

### 1. Assemble Hardware (30 minutes)
1. Put Pi 5 in case, insert microSD
2. Plug in USB microphone
3. Plug in USB speaker
4. Plug in webcam
5. Connect Pi to WiFi router via Ethernet (more reliable than WiFi)
6. Connect UPS battery to Pi power supply
7. Power on

### 2. Flash Raspberry Pi OS (30 minutes)
1. On your existing PC, download Raspberry Pi Imager
2. Flash Raspberry Pi OS Lite (64-bit) to microSD
3. Enable SSH (create empty file named `ssh` on boot partition)
4. Insert microSD into Pi, power on

### 3. Connect to Pi (5 minutes)
```bash
# Find Pi's IP (check your router admin page, or use:)
ping raspberrypi.local

# SSH in
ssh pi@<PI_IP_ADDRESS>
# Default password: raspberry (change it!)
passwd
```

### 4. Run Setup Script (30-60 minutes)
```bash
# Clone the repo
git clone https://github.com/ovalentine964/aego-cyber-cafe.git
cd aego-cyber-cafe/engineering/foundation

# Run setup
chmod +x setup-pi.sh
./setup-pi.sh

# This installs:
# - Ollama + pulls gemma4:4b and qwen3.5:3b models
# - Piper TTS + Swahili voice model
# - Whisper.cpp + tiny model
# - FastAPI server dependencies
# - n8n
# - systemd services (auto-start on boot)
# - Firewall rules
```

### 5. Configure Environment (10 minutes)
```bash
# Copy env template
cp /opt/aego/.env.example /opt/aego/.env

# Edit with your actual values
nano /opt/aego/.env

# Fill in:
# - WHATSAPP_TOKEN (from Meta Business)
# - WHATSAPP_PHONE_ID
# - TELEGRAM_TOKEN (from @BotFather)
# - MPESA_CONSUMER_KEY (from Safaricom Daraja)
# - MPESA_CONSUMER_SECRET
# - MPESA_SHORTCODE (your paybill: 0115 965 493)
# - MPESA_PASSKEY
# - ADMIN_USERNAME (pick something)
# - ADMIN_PASSWORD (pick something strong)
```

### 6. Start the Server (1 minute)
```bash
sudo systemctl start aego-server
sudo systemctl status aego-server

# Should show: active (running)
```

### 7. Test It Works (10 minutes)
```bash
# Health check
curl http://localhost:8000/api/health

# Test CV endpoint
curl -X POST http://localhost:8000/api/cv/start

# Test translation
curl -X POST http://localhost:8000/api/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello", "source_lang": "en", "target_lang": "sw"}'

# Open kiosk UI on a phone/tablet connected to same WiFi
# http://<PI_IP_ADDRESS>:8000/kiosk/
```

### 8. Connect WhatsApp (Day 2-3)
1. Go to business.facebook.com
2. Create WhatsApp Business account
3. Get API token
4. Set webhook URL: `https://your-domain.com/api/whatsapp/webhook`
5. You'll need a domain + ngrok or Cloudflare Tunnel for the webhook

### 9. Connect Telegram (5 minutes)
1. Message @BotFather on Telegram
2. Create new bot: /newbot
3. Copy token to .env
4. Set webhook: `curl https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-domain.com/api/telegram/webhook`

---

## Daily Operations (Staff)

### Morning Routine
1. Check Pi is on (green light)
2. Check health: `curl http://localhost:8000/api/health`
3. Open kiosk on tablet: `http://<PI_IP>:8000/kiosk/`
4. Check today's stats: `http://<PI_IP>:8000/api/admin/stats`

### When Customer Arrives
1. **CV Writing:** Open kiosk → CV Writing → customer speaks → review → print
2. **Government Service:** Open kiosk → Government → select service → fill fields → print
3. **Translation:** Open kiosk → Translation → speak/type → get translation
4. **WhatsApp customer:** AI handles automatically, staff approves generated documents

### End of Day
1. Check daily report (n8n workflow sends to your WhatsApp at 8 PM)
2. Backup runs automatically (backup.sh at midnight)
3. Don't turn off Pi — it runs 24/7 (UPS handles power outages)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Pi won't boot | Check SD card, reflash if needed |
| Can't SSH | Check Ethernet cable, check `ping raspberrypi.local` |
| Ollama not responding | `sudo systemctl restart ollama` |
| Server not responding | `sudo systemctl restart aego-server` |
| Out of memory | Check `free -h`, restart Ollama to clear model from RAM |
| WhatsApp not working | Check .env token, check webhook URL |
| Voice not working | Check USB mic/speaker: `arecord -l` and `aplay -l` |
| Slow responses | Normal on Pi 5 — Gemma 4 E4B takes 5-15s per response |

---

## What's Built vs What's Left

### ✅ Built (Code Complete)
- FastAPI server with all routes
- Voice pipeline (Whisper + Piper TTS)
- CV writer + templates
- Government services + form filler
- M-Pesa integration + database
- Translation service
- WhatsApp/Telegram bots
- Kiosk UI (touch-friendly, trilingual)
- n8n workflows (5 automation flows)
- WiFi captive portal
- Setup script + systemd services
- Backup + health monitoring

### 🔲 Needs Your Input
- M-Pesa API credentials (from Safaricom)
- WhatsApp Business API token (from Meta)
- Telegram bot token (from @BotFather)
- Test with actual hardware (Pi 5 + mic + speaker)
- Staff training (1-2 hours)

### 🔲 Future Enhancements (Month 2+)
- Add n8n for staff workflow automation
- Solar backup for daytime power outages
- Fine-tune Gemma 4 on Aego-specific data
- Add Kikuyu language support
- WiFi hotspot + AI bundle billing
