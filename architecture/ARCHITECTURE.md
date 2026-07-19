# Aego Cyber Cafe — Validated Architecture & Tech Stack
## v1.0 — July 19, 2026

---

## Gap Analysis: What the Brief Got Wrong

| # | Claim in Brief | Reality | Fix |
|---|---------------|---------|-----|
| 1 | **Coqui TTS** for text-to-speech | Coqui shut down in 2023. Unmaintained, broken dependencies. | Replace with **Piper TTS** — actively maintained, supports Swahili (sw_CD), 30+ languages, runs on Pi 5, C++ core |
| 2 | **Whisper Large V3 Turbo** for speech-to-text | Needs 6GB VRAM. Pi 5 has 8GB RAM shared — won't fit with other models. | Use **Whisper tiny/base** on Pi 5 (fast, ~1GB). Use Gemma 4 native audio input to eliminate STT entirely for voice interactions |
| 3 | Gemma 4 handles voice output | Gemma 4 has native audio **INPUT** (speak to it) but NOT audio output. Still needs separate TTS. | Combine Gemma 4 (audio in) + Piper TTS (audio out) for full voice loop |
| 4 | Ollama not mentioned | OpenClaw connects to models via API. Need a local model server. | Add **Ollama** as the model serving layer between OpenClaw and Gemma 4/Qwen |
| 5 | M-Pesa MCP "just works" | The existing `mboya/daraja-mcp` was built for Claude, not OpenClaw. May need adaptation. | Either adapt existing MCP server or build custom M-Pesa skill for OpenClaw using Daraja API directly |
| 6 | No power/reliability consideration | Rural Kenya has frequent power outages. Pi dies = no AI services. | Add **UPS battery backup** ($20-30) for Pi 5 |
| 7 | No offline queue design | Intermittent connectivity means requests fail. | Design **offline queue** — requests queue locally, process when connectivity returns |
| 8 | "Kimi K3 matches GPT-5.5" | Unverified claim. Kimi K3 is competitive but benchmarks vary. | Don't depend on Kimi K3. Build on Gemma 4 (confirmed, Google-backed, Apache 2.0) |
| 9 | Missing: How OpenClaw serves web UI | Brief mentions "walk-in kiosk (web UI)" but doesn't specify how. | OpenClaw has no built-in customer-facing web UI. Need to build a simple kiosk interface or use WhatsApp/Telegram as primary channels |
| 10 | Missing: Data privacy for gov forms | Customers filling KRA/eCitizen forms = sensitive personal data (ID numbers, PINs). | Design data handling: process in-memory, don't persist sensitive fields, auto-purge after session |

---

## Validated Tech Stack

### Layer 1: Hardware (Cafe Floor)

```
┌─────────────────────────────────────────────────────────┐
│                    HARDWARE LAYER                         │
│                                                           │
│  Raspberry Pi 5 (8GB)          ← Main AI server ($80)    │
│  ├── 64GB microSD              ← OS + models ($10)       │
│  ├── USB Microphone            ← Customer voice input ($10) │
│  ├── USB Speaker               ← AI voice output ($15)   │
│  ├── Webcam                    ← Document scanning ($20)  │
│  └── UPS Battery Pack          ← Power backup ($25)      │
│                                                           │
│  Existing PC/Laptop            ← Staff workstation       │
│  └── Printer                   ← Already in cafe         │
│                                                           │
│  Total new hardware cost: ~$160                           │
└─────────────────────────────────────────────────────────┘
```

### Layer 2: Software Stack

```
┌─────────────────────────────────────────────────────────┐
│                    SOFTWARE STACK                          │
│                                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  OpenClaw Gateway (orchestration brain)            │  │
│  │  - WhatsApp/Telegram bridges                       │  │
│  │  - Skill management                                │  │
│  │  - MCP client                                      │  │
│  │  - Cron/scheduler                                  │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────▼────────────────────────────┐  │
│  │  Ollama (local model server)                       │  │
│  │  - Gemma 4 E4B (voice input + reasoning)           │  │
│  │  - Qwen 3.5-3B (multilingual fallback)            │  │
│  │  - Exposes localhost:11434 API                     │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────▼────────────────────────────┐  │
│  │  Voice Pipeline                                    │  │
│  │  - Whisper.cpp tiny/base (STT, for non-Gemma cases)│  │
│  │  - Piper TTS (Swahili/English voice output)        │  │
│  │  - Gemma 4 native audio input (primary voice-in)   │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────▼────────────────────────────┐  │
│  │  Service Layer (OpenClaw Skills)                   │  │
│  │  - CV Writing Skill (voice → structured CV → print)│  │
│  │  - Form Filling Skill (photo → parse → fill)       │  │
│  │  - Translation Skill (En ↔ Sw ↔ Luo)              │  │
│  │  - Gov Services Skill (KRA/eCitizen guided flow)   │  │
│  │  - M-Pesa Skill (Daraja API integration)           │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────▼────────────────────────────┐  │
│  │  Infrastructure                                    │  │
│  │  - n8n (workflow automation, staff-facing)         │  │
│  │  - SQLite (local data, sessions, queue)            │  │
│  │  - Offline queue (process when connectivity returns)│  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  Cloud Fallback (when internet available):                │
│  - OpenAI API (complex tasks, GPT-Realtime-2)             │
│  - Google Gemini API (translation, fallback reasoning)    │
│  - Total: $0-30/month depending on usage                  │
└─────────────────────────────────────────────────────────┘
```

### Layer 3: Customer-Facing Interfaces

```
┌─────────────────────────────────────────────────────────┐
│               CUSTOMER INTERFACES                         │
│                                                           │
│  1. WhatsApp (PRIMARY — most customers already use it)   │
│     └── OpenClaw WhatsApp bridge                         │
│     └── Message AI → get service → pay via M-Pesa        │
│                                                           │
│  2. Walk-in Kiosk (SECONDARY — at the cafe)              │
│     └── Simple web UI on existing PC                     │
│     └── Voice input via USB microphone                   │
│     └── Touch-friendly, large buttons                    │
│                                                           │
│  3. Telegram (OPTIONAL — tech-savvy users)               │
│     └── OpenClaw Telegram bridge                         │
│                                                           │
│  4. Staff Dashboard (INTERNAL)                           │
│     └── n8n workflows for staff to manage services       │
│     └── Monitor AI usage, payments, errors               │
└─────────────────────────────────────────────────────────┘
```

---

## What Actually Needs to Be Built

### Phase 1: Foundation (Week 1-2)

| # | Task | What | Status |
|---|------|------|--------|
| 1 | Install OpenClaw on Pi 5 | `curl -fsSL https://openclaw.ai/install \| bash` | 🔲 |
| 2 | Install Ollama on Pi 5 | `curl -fsSL https://ollama.ai/install.sh \| sh` | 🔲 |
| 3 | Pull Gemma 4 E4B | `ollama pull gemma4:4b` | 🔲 |
| 4 | Pull Qwen 3.5-3B | `ollama pull qwen3.5:3b` | 🔲 |
| 5 | Install Piper TTS | Binary install, download Swahili voice model | 🔲 |
| 6 | Install Whisper.cpp | Build from source, download tiny/base model | 🔲 |
| 7 | Configure OpenClaw | Set Ollama as model provider, enable voice | 🔲 |
| 8 | Connect WhatsApp | OpenClaw WhatsApp bridge setup | 🔲 |
| 9 | Test voice pipeline | Mic → Whisper/Gemma → LLM → Piper → Speaker | 🔲 |
| 10 | UPS battery backup | Connect Pi to battery pack | 🔲 |

### Phase 2: Core Services (Week 3-4)

| # | Task | What | Status |
|---|------|------|--------|
| 11 | Build CV Writing Skill | OpenClaw skill: voice input → structured CV → PDF → print | 🔲 |
| 12 | Build Translation Skill | OpenClaw skill: En ↔ Sw ↔ Luo using Qwen 3.5 | 🔲 |
| 13 | Build M-Pesa Skill | OpenClaw skill wrapping Daraja API for payments | 🔲 |
| 14 | Build Form Filling Skill | Photo gov form → Gemma vision → extract fields → fill | 🔲 |
| 15 | Build WhatsApp auto-reply | Greet customers, list services, accept requests | 🔲 |
| 16 | Offline queue system | SQLite-backed request queue, process when online | 🔲 |
| 17 | Staff dashboard (basic) | n8n workflow: view requests, approve, print | 🔲 |

### Phase 3: Government Services (Week 5-8)

| # | Task | What | Status |
|---|------|------|--------|
| 18 | KRA iTax guided flow | Voice-guided step-by-step KRA filing | 🔲 |
| 19 | eCitizen guided flow | Voice-guided good conduct, birth cert, etc. | 🔲 |
| 20 | NHIF/NSSF guided flow | Registration and status check | 🔲 |
| 21 | Document scanning pipeline | Webcam → Gemma vision → extract text → process | 🔲 |
| 22 | Payment confirmation | M-Pesa callback → auto-confirm → deliver service | 🔲 |

### Phase 4: Revenue & Scale (Week 9-12)

| # | Task | What | Status |
|---|------|------|--------|
| 23 | Pay-per-query billing | KES 10-50 per AI query via M-Pesa | 🔲 |
| 24 | WiFi + AI bundles | Monthly subscription via M-Pesa | 🔲 |
| 25 | Self-service kiosk UI | Touch-friendly web interface for walk-ins | 🔲 |
| 26 | Usage analytics | Track queries, revenue, popular services | 🔲 |
| 27 | Multi-language expansion | Add Kikuyu, more Luo coverage | 🔲 |

---

## Key Architecture Decisions

### Decision 1: Ollama as Model Server (not raw llama.cpp)

**Why:** OpenClaw expects an OpenAI-compatible API endpoint. Ollama provides this natively at `localhost:11434`. Raw llama.cpp would require building an API wrapper. Ollama handles model loading, quantization, and serving.

**Trade-off:** Ollama adds ~200MB overhead. Worth it for the API compatibility.

### Decision 2: Piper TTS over Coqui/Kokoro/XTTS

**Why:**
- **Piper** — actively maintained, C++ core, 30+ languages including Swahili, runs on Pi 5, <100ms latency
- **Coqui** — dead (2023), Python-heavy, broken deps
- **Kokoro** — newer, 82M params, good quality but less proven on edge
- **XTTS v2** — heavy, needs GPU, not Pi-friendly

**Trade-off:** Piper voices are less natural than XTTS. But it works offline on Pi 5. That's the constraint.

### Decision 3: Gemma 4 E4B as Primary Model (not Qwen 3.5)

**Why:**
- Gemma 4 E4B has **native audio input** — speak directly, no separate STT step needed
- Gemma 4 E4B has **native vision** — photograph forms, extract text
- Gemma 4 E4B has **function calling** — structured JSON output for form filling
- Qwen 3.5-3B as fallback for multilingual edge cases (201 languages)
- Both Apache 2.0

**Trade-off:** Qwen 3.5 has more languages (201 vs ~140). Use it as fallback when Gemma struggles with a specific language.

### Decision 4: WhatsApp as Primary Channel (not web UI)

**Why:** 90%+ of Kenyan internet users have WhatsApp. Building a web kiosk is secondary. WhatsApp works on the cheapest phones, supports voice messages, images, and text.

**Trade-off:** WhatsApp Business API has costs at scale. But OpenClaw's WhatsApp bridge uses the personal account for free initially.

### Decision 5: M-Pesa via Daraja API Direct (not MCP)

**Why:** The existing `mboya/daraja-mcp` is designed for Claude. OpenClaw skills can call the Daraja API directly via HTTP. Simpler, more reliable, no MCP translation layer needed.

**Trade-off:** Lose MCP ecosystem compatibility. But gain reliability and simplicity.

### Decision 6: SQLite for Local Storage (not PostgreSQL)

**Why:** SQLite runs on Pi 5 with zero config, handles 1000s of concurrent reads, single-file database, easy backup. PostgreSQL would be overkill and heavier.

**Trade-off:** No concurrent writes at high scale. Fine for a single cafe. If you scale to multiple locations, migrate to PostgreSQL.

---

## Power & Reliability Design

```
┌──────────────────────────────────────────┐
│         RELIABILITY STACK                 │
│                                           │
│  Power:                                   │
│  ├── UPS battery (2-4 hours backup)       │
│  ├── Auto-shutdown on low battery         │
│  └── Auto-restart when power returns      │
│                                           │
│  Connectivity:                            │
│  ├── Offline-first: process locally       │
│  ├── Queue: SQLite-backed request queue   │
│  ├── Sync: flush queue when online        │
│  └── Cloud fallback: API calls when up    │
│                                           │
│  Model:                                   │
│  ├── Primary: Gemma 4 E4B (offline)       │
│  ├── Fallback: Qwen 3.5-3B (offline)     │
│  ├── Cloud: GPT/Gemini (online only)      │
│  └── Auto-switch based on connectivity    │
│                                           │
│  Data:                                    │
│  ├── Sensitive: in-memory only, auto-purge│
│  ├── Non-sensitive: SQLite local          │
│  ├── Backups: daily to USB drive          │
│  └── No customer data in cloud            │
└──────────────────────────────────────────┘
```

---

## Data Privacy Design

Government forms contain sensitive data (ID numbers, KRA PINs, dates of birth). Architecture must handle this:

1. **Process in-memory** — Form data goes through LLM in RAM, not written to disk
2. **Auto-purge** — After form is submitted/printed, clear sensitive fields from memory
3. **No cloud upload** — Sensitive data never leaves the Pi unless explicitly going to a government portal
4. **Audit log** — Log that a form was processed (timestamp, service type) without logging the content
5. **Staff access control** — Only authorized staff can view processed requests

---

## What the AI Space Trends Mean for This Architecture

| Trend | Impact on Architecture | Action |
|-------|----------------------|--------|
| Models getting smaller | More services fit on Pi 5 over time | Monitor new small models, swap in better ones |
| Inference costs dropping | Cloud fallback gets cheaper | Keep cloud as option, don't over-invest in local |
| M-Pesa + AI maturing | More payment features available | Build M-Pesa integration modular, easy to extend |
| Voice-first becoming standard | Customers expect voice | Make voice the default, text as option |
| Open-source winning | No vendor lock-in risk | Stay on Apache 2.0 models, avoid proprietary |
| Memory chip shortage | More customers need the cafe | Scale infrastructure to handle more users |

---

## Files in This Repo

```
aego-cyber-cafe/
├── index.html, about.html, services.html, contact.html  ← existing website
├── architecture/
│   ├── ARCHITECTURE.md          ← this file (validated tech stack)
│   ├── GAP_ANALYSIS.md          ← what was wrong and what's fixed
│   └── IMPLEMENTATION_PLAN.md   ← week-by-week build plan
├── research/
│   ├── AEGO_CYBER_CAFE_AI_BRIEF.md  ← executive summary
│   ├── 01_voice_reasoning_models.md  ← voice/reasoning research
│   ├── 02_multiagent_loops.md        ← multi-agent research
│   ├── 03_quantum_agi.md             ← quantum/AGI research
│   └── 04_emerging_future_openclaw.md ← emerging/OpenClaw research
└── skills/                      ← (to be built) OpenClaw skills
    ├── cv-writer/
    ├── form-filler/
    ├── translator/
    ├── mpesa/
    └── gov-services/
```

---

*Architecture validated July 19, 2026 | Aego Cyber Cafe Engineering*
