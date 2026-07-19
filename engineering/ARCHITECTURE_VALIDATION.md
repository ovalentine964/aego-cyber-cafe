# Architecture Validation: Aego Cyber Cafe
## Honest Assessment — July 19, 2026

---

## The Core Problem Nobody Wants to Say Out Loud

**OpenClaw is a personal AI assistant platform. A cyber cafe is not a person.**

OpenClaw's own documentation states this explicitly:

> *"Personal assistant trust model. This guidance assumes one trusted operator boundary per gateway (single-user, personal-assistant model). OpenClaw is **not** a hostile multi-tenant security boundary for multiple adversarial users sharing one agent or gateway."*
> — [OpenClaw Security Docs](https://docs.openclaw.ai/gateway/security)

The previous architecture document (`architecture/ARCHITECTURE.md`) built everything on OpenClaw as the central orchestrator. This is architecturally wrong for a cyber cafe. Here's why:

| OpenClaw Design Assumption | Cyber Cafe Reality |
|---|---|
| One human, one agent | 20-50 different customers per day |
| Persistent memory across sessions | Customer A's data must NEVER leak to Customer B |
| Heartbeats, persona, SOUL.md | Nobody wants a "personality" — they want a CV |
| Conversational, multi-turn | "Write my CV" → done. Next customer. |
| AGENTS.md, MEMORY.md, daily logs | No memory files. No journaling. Stateless. |
| Single trust boundary | Multiple untrusted users with sensitive data (ID numbers, KRA PINs) |

OpenClaw's multi-tenant solution (`openclaw fleet`) requires running a **separate Gateway instance per tenant** — each in its own container with its own state, credentials, and port. For a cyber cafe with 30 customers/day, that's 30 Gateway processes. On a Raspberry Pi 5 with 8GB RAM. While also running Ollama. This is not viable.

---

## Memory Budget: The Hard Constraint

Everything must fit in 8GB RAM. Let's do the math honestly:

| Component | Realistic RAM Usage | Source |
|---|---|---|
| OS (Raspberry Pi OS Lite, no desktop) | 200-400MB | Measured on Pi 5 |
| Ollama server overhead | 300-500MB | Ollama docs + community reports |
| Gemma 4 E4B (Q4_K_M quantization) | **2.5-3.0GB** | 4B params × 4 bits ÷ 8 = ~2GB model + KV cache overhead |
| Whisper.cpp tiny | 150-200MB | Whisper.cpp benchmarks |
| Piper TTS | 50-100MB | Binary, loads voice model on demand |
| **Subtotal: AI stack** | **3.2-4.2GB** | |
| **Remaining for everything else** | **3.8-4.8GB** | |

Now add the orchestration layer:

| Option | Additional RAM | Fits? |
|---|---|---|
| OpenClaw Gateway (per instance) | 500MB-1GB | Tight. And you'd need multiple instances for multi-tenant. |
| FastAPI server | 30-80MB | ✅ Easily |
| n8n | 300-500MB | Possible but tight |
| FastAPI + n8n (hybrid) | 350-580MB | Possible but tight |

**The previous architecture claimed Gemma 4 E4B uses "1.5GB". This is wrong.** A 4-billion parameter model at Q4 quantization is ~2GB for weights alone, plus KV cache (grows with context length), plus Ollama's overhead. Realistic total: 2.5-3.0GB. The previous doc underestimated by 1-1.5GB, which on a Pi 5 is the difference between "works" and "OOM killer".

---

## Option-by-Option Analysis

### OPTION A: OpenClaw as Orchestrator Only

**Concept:** Use OpenClaw Gateway only for WhatsApp/Telegram channel bridges. Route to standalone Python scripts. No memory, no heartbeats.

**Verdict: ❌ Wrong tool for the job.**

| Criterion | Assessment | Score |
|---|---|---|
| 1. Pi 5 RAM fit | 500MB-1GB for a channel bridge is wasteful. You're using a Formula 1 engine to power a bicycle. | 4/10 |
| 2. Multi-tenant | OpenClaw's session model assumes persistent context. You'd have to actively fight the platform to make it stateless. Memory files (MEMORY.md, AGENTS.md) are per-gateway, not per-customer. | 3/10 |
| 3. Setup complexity | Install OpenClaw, configure Ollama provider, write skills, configure channels. Moderate. But you're learning a platform whose core abstractions (sessions, memory, heartbeats, personas) you don't need. | 5/10 |
| 4. Staff maintenance | OpenClaw is designed for technical users who understand agent concepts. A cyber cafe staff member in Nyatike shouldn't need to understand "skills" or "MCP" or "session keys". | 2/10 |
| 5. Voice pipeline | OpenClaw has voice support, but it's designed for 1:1 conversational AI. The "press button, speak, get response" flow for a kiosk doesn't match. | 5/10 |
| 6. M-Pesa | Would need to build an OpenClaw skill wrapping Daraja API. Doable but adds a layer of indirection. | 5/10 |
| 7. Offline-first | OpenClaw itself works offline, but it's designed for always-on personal assistant use, not bursty cafe workloads. | 5/10 |
| 8. Monthly cost | $0 (open source). But developer time to fight the platform is expensive. | 6/10 |
| 9. Staff workflows | No visual workflow editor. Changes require editing YAML/JSON config and skill files. | 2/10 |
| 10. Multi-location scaling | Would need separate Gateway instance per location. Possible but operationally complex. | 4/10 |

**Total: 41/100**

**The fundamental problem:** You're using a platform designed for "one human having a persistent relationship with an AI" to serve "30 strangers a day who each want a one-shot service." Every architectural decision in OpenClaw — memory, sessions, heartbeats, persona, AGENTS.md — works against you. You'd spend more time disabling features than building services.

---

### OPTION B: Lightweight Custom API Server

**Concept:** Python FastAPI server. WhatsApp via WhatsApp Business Cloud API or whatsapp-web.js. Telegram via python-telegram-bot. Direct Ollama HTTP calls. Custom routing.

**Verdict: ✅ Best option. Purpose-built.**

| Criterion | Assessment | Score |
|---|---|---|
| 1. Pi 5 RAM fit | FastAPI: 30-80MB. Minimal. Leaves maximum headroom for Ollama + models. | 9/10 |
| 2. Multi-tenant | You design it from scratch. Each request gets a unique ID. No shared state between customers. Sensitive data purged after response. This is the correct architecture. | 10/10 |
| 3. Setup complexity | Medium-high. You're building from scratch. But the components are simple: FastAPI + httpx (for Ollama) + python-telegram-bot + SQLite. | 5/10 |
| 4. Staff maintenance | Once built, it's a single Python service. systemd manages it. Logs go to a file. Staff don't touch the code. | 7/10 |
| 5. Voice pipeline | Direct control: mic input → Whisper.cpp subprocess → text → Ollama HTTP → response text → Piper subprocess → speaker output. Clean, no abstraction leakage. | 8/10 |
| 6. M-Pesa | Direct Daraja API integration via httpx. No intermediate platform. | 9/10 |
| 7. Offline-first | Fully offline. Ollama runs locally. WhatsApp/Telegram need internet, but kiosk mode is fully offline. Queue design is straightforward. | 9/10 |
| 8. Monthly cost | $0 for software. WhatsApp Business Cloud API: service conversations are free (customer-initiated). Template messages cost ~$0.01-0.04 each in Africa. For a cafe, mostly service conversations → ~$0-5/month. | 9/10 |
| 9. Staff workflows | No visual editor. But: build a simple admin web UI (Flask/Streamlit) for staff to view requests, manage services, see payments. 1-2 days of work. | 5/10 |
| 10. Multi-location scaling | Deploy the same FastAPI app at each location. Each runs independently. Central dashboard via simple API aggregation. | 8/10 |

**Total: 79/100**

**Two sub-options for WhatsApp:**

| Approach | Pros | Cons |
|---|---|---|
| **WhatsApp Business Cloud API** (official) | Free for service conversations. Reliable. Meta-supported. Green checkmark badge. | Requires Meta Business verification. Template messages cost money. 24-hour response window. |
| **whatsapp-web.js** (unofficial) | Free. Uses personal WhatsApp account. No verification needed. | Against WhatsApp ToS. Account may get banned. Unreliable long-term. Not recommended for business. |

**Recommendation:** Start with WhatsApp Business Cloud API (free tier). It's the right long-term choice. The verification process takes 1-2 weeks but gives you a legitimate, sustainable channel.

---

### OPTION C: n8n as Primary Platform

**Concept:** n8n handles ALL workflow automation AND channel routing. n8n triggers for WhatsApp/Telegram. n8n calls Ollama via HTTP. Skills are n8n workflows.

**Verdict: ⚠️ Good for staff workflows, bad as primary platform.**

| Criterion | Assessment | Score |
|---|---|---|
| 1. Pi 5 RAM fit | n8n (Node.js): 300-500MB. Combined with Ollama (3-4GB) + OS (300MB) = 4-5GB. Leaves 3-4GB. Possible but tight. | 5/10 |
| 2. Multi-tenant | n8n workflows are stateless by default (good). But n8n's credential storage and execution history could leak data between customers if not carefully managed. Requires deliberate design. | 6/10 |
| 3. Setup complexity | n8n is easy to install (`npx n8n`). But building complex AI workflows (voice pipeline, form parsing, M-Pesa) in the visual editor is harder than writing Python. The visual paradigm breaks down for complex logic. | 5/10 |
| 4. Staff maintenance | **This is n8n's strength.** Visual workflow editor. Staff can modify service flows without coding. Drag and drop. This is genuinely useful. | 9/10 |
| 5. Voice pipeline | n8n has no native audio handling. You'd need external scripts for Whisper/Piper anyway, called via Execute Command nodes. Awkward. | 3/10 |
| 6. M-Pesa | n8n has HTTP Request node for Daraja API. Webhook node for callbacks. Works well. | 7/10 |
| 7. Offline-first | n8n works offline for workflow execution. But WhatsApp/Telegram trigger nodes need internet. Kiosk mode possible via webhook triggers. | 6/10 |
| 8. Monthly cost | $0 (self-hosted, fair-code license). | 8/10 |
| 9. Staff workflows | **Best in class.** Visual editor. Non-technical staff can create and modify workflows. This is the killer feature. | 10/10 |
| 10. Multi-location scaling | Deploy n8n at each location. Export/import workflows. Works. | 7/10 |

**Total: 66/100**

**The problem with n8n as primary:** n8n is a workflow automation tool, not an application server. Building a real-time voice pipeline, managing WebSocket connections for Telegram, handling concurrent customer sessions — these are application-server problems. n8n can call external scripts, but at that point you're just using n8n as a scheduler with a visual UI, not as an architecture.

**n8n's real value** is for staff-facing workflows: "When M-Pesa payment received → update spreadsheet → notify staff → trigger print job." That's what it's designed for.

---

### OPTION D: Hybrid — Lightweight API + n8n for Staff

**Concept:** FastAPI handles customer-facing requests. n8n handles staff-facing workflows. Clean separation.

**Verdict: ✅ Good architecture, but more complex than needed at launch.**

| Criterion | Assessment | Score |
|---|---|---|
| 1. Pi 5 RAM fit | FastAPI (50MB) + n8n (400MB) + Ollama (3.5GB) + OS (300MB) + voice (300MB) = ~4.5GB. Fits with 3.5GB headroom. | 7/10 |
| 2. Multi-tenant | FastAPI handles customer isolation correctly. n8n handles staff workflows separately. Clean separation. | 9/10 |
| 3. Setup complexity | Two systems to build, configure, and integrate. Highest setup cost of all options. | 3/10 |
| 4. Staff maintenance | Two systems to monitor. But n8n's visual editor makes staff workflows easy. FastAPI needs developer for changes. | 6/10 |
| 5. Voice pipeline | Same as Option B — direct control via FastAPI. | 8/10 |
| 6. M-Pesa | FastAPI handles customer-facing payments. n8n handles payment reconciliation workflows. Clean. | 9/10 |
| 7. Offline-first | Both work offline. Same as Option B + C combined. | 8/10 |
| 8. Monthly cost | $0 software. Same WhatsApp costs as Option B. | 9/10 |
| 9. Staff workflows | n8n for staff. Best visual editor. | 9/10 |
| 10. Multi-location scaling | Two systems per location. More complex but manageable. | 7/10 |

**Total: 75/100**

**The honest take:** This is the best long-term architecture, but it's overkill for launch. Start with Option B. Add n8n later when staff need to manage workflows themselves (Month 2-3).

---

## Side-by-Side Comparison

| Criterion | A: OpenClaw | B: Custom API | C: n8n Only | D: Hybrid |
|---|---|---|---|---|
| 1. Pi 5 RAM fit | 4 | **9** | 5 | 7 |
| 2. Multi-tenant | 3 | **10** | 6 | 9 |
| 3. Setup complexity | 5 | 5 | 5 | 3 |
| 4. Staff maintenance | 2 | 7 | **9** | 6 |
| 5. Voice pipeline | 5 | **8** | 3 | 8 |
| 6. M-Pesa | 5 | **9** | 7 | 9 |
| 7. Offline-first | 5 | **9** | 6 | 8 |
| 8. Monthly cost | 6 | **9** | 8 | 9 |
| 9. Staff workflows | 2 | 5 | **10** | 9 |
| 10. Multi-location | 4 | **8** | 7 | 7 |
| **TOTAL** | **41** | **79** | **66** | **75** |

**Winner: Option B (Lightweight Custom API Server)**

---

## Recommended Architecture: Option B+ (Enhanced)

Plain Option B is correct but needs enhancements. Here's the recommended stack:

```
┌─────────────────────────────────────────────────────────────┐
│                    CUSTOMER-FACING LAYER                      │
│                                                               │
│  WhatsApp (Business Cloud API)     ← Primary channel          │
│  Telegram (python-telegram-bot)    ← Secondary channel        │
│  Kiosk Web UI (simple HTML/JS)     ← Walk-in customers        │
│  USB Mic + Speaker (direct)        ← Voice at the cafe        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 AEGO SERVICE SERVER (FastAPI)                  │
│                 ~50MB RAM | Python 3.11+                       │
│                                                               │
│  Routes:                                                      │
│  ├── /api/cv          → CV Writing Service                    │
│  ├── /api/translate   → Translation Service                   │
│  ├── /api/form        → Government Form Helper                │
│  ├── /api/voice       → Voice Pipeline (Whisper→LLM→Piper)    │
│  ├── /api/mpesa/*     → M-Pesa Payment Endpoints              │
│  └── /api/admin/*     → Staff Dashboard                       │
│                                                               │
│  Session Management:                                          │
│  ├── Each request gets UUID                                   │
│  ├── No persistent memory between customers                   │
│  ├── Sensitive data purged after response                     │
│  └── SQLite for audit log (service type, timestamp, amount)   │
│                                                               │
│  Multi-tenant guarantee:                                      │
│  ├── Stateless request processing                             │
│  ├── No shared context between customers                      │
│  ├── Per-request temp storage, auto-cleanup                   │
│  └── Customer A's ID number NEVER appears in Customer B's session│
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI / MODEL LAYER                            │
│                                                               │
│  Ollama (localhost:11434)                                     │
│  ├── Gemma 4 E4B Q4_K_M   ← Primary (reasoning, vision)     │
│  └── Qwen 3.5-3B Q4_K_M  ← Multilingual fallback            │
│                                                               │
│  Whisper.cpp (subprocess)                                     │
│  └── tiny model            ← STT for voice input              │
│                                                               │
│  Piper TTS (subprocess)                                       │
│  └── Swahili/English voices ← TTS for voice output            │
│                                                               │
│  Cloud Fallback (when internet available):                    │
│  └── Google Gemini API     ← Complex tasks, better quality    │
│      Free tier: 15 RPM, 1M tokens/day                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    PAYMENT LAYER                               │
│                                                               │
│  M-Pesa Daraja API (Safaricom)                                │
│  ├── STK Push (customer pays)                                 │
│  ├── C2B (receive payments)                                   │
│  ├── B2C (refunds if needed)                                  │
│  └── Callback URL → FastAPI webhook endpoint                  │
│                                                               │
│  SQLite:                                                      │
│  ├── payments table (amount, phone, status, timestamp)        │
│  └── services table (service_type, customer_hash, completed)  │
└─────────────────────────────────────────────────────────────┘
```

### Why This Is Better Than the Previous Architecture

| Aspect | Previous (OpenClaw-based) | Recommended (FastAPI-based) |
|---|---|---|
| Multi-tenant | Fights OpenClaw's 1:1 model | Designed for it from day one |
| Memory usage | 500MB-1GB overhead for OpenClaw | 30-80MB for FastAPI |
| State management | MEMORY.md, AGENTS.md, sessions — all per-agent, not per-customer | Stateless. UUID per request. Auto-purge. |
| Staff interaction | Requires understanding "skills", "MCP", "sessions" | Simple REST API + admin dashboard |
| Voice pipeline | Abstracted through OpenClaw's voice system | Direct subprocess calls. Simple. Debuggable. |
| Data leakage risk | OpenClaw memory files could contain customer data | No persistent customer data by design |
| Dependencies | OpenClaw + Node.js + Ollama + Python | Python + Ollama. That's it. |

---

## Gap Analysis Review: What the Previous Doc Got Right and Wrong

### Gap 1: Coqui TTS → Piper TTS ✅ CORRECT

Coqui shut down in 2023. Piper is the right replacement. It's actively maintained, C++ core, runs on Pi.

**But:** The previous doc said Piper has "Swahili (sw_CD)" support. Reality: Piper's Swahili voice quality is functional but noticeably robotic. For a cyber cafe where customers expect reasonable voice quality, this is acceptable for now but should be upgraded when better Swahili TTS models emerge.

### Gap 2: Whisper Large V3 Turbo → tiny/base ✅ CORRECT, BUT UNDERSTATED

The fix is right — use tiny/base. But the previous doc didn't quantify the accuracy tradeoff.

**Reality check:** Whisper tiny on accented African English will have ~15-25% word error rate. On Swahili, ~10-20% WER. This means 1 in 5-7 words may be wrong. For CV writing (where you review before printing), this is acceptable. For government form filling (where a wrong digit in an ID number is catastrophic), this is NOT acceptable without human review.

**Recommendation:** Always show the transcribed text to the customer (on screen or read back via TTS) before processing. Never auto-submit transcribed data for critical operations.

### Gap 3: Gemma 4 audio output ⚠️ PARTIALLY CORRECT

The previous doc correctly identified that Gemma 4 has audio INPUT but not output. However:

**Additional concern:** Gemma 4 E4B's "native audio input" capability is for the full model. On-device with Q4 quantization on a Pi 5, the audio processing quality and speed may be significantly degraded. The model needs to load the audio encoder + language model simultaneously, which increases memory pressure.

**Recommendation:** Use Whisper.cpp for STT (it's optimized for this exact task) and don't rely on Gemma 4's native audio input for production. Use it as a fallback only.

### Gap 4: Ollama not mentioned ✅ CORRECT

Ollama is the right choice for model serving on Pi 5. It handles quantization, model loading, and provides OpenAI-compatible API. Adding it was necessary.

### Gap 5: M-Pesa MCP ⚠️ CORRECT DIRECTION, WRONG APPROACH

The previous doc correctly identified that the existing MCP server was built for Claude. But the fix ("build custom M-Pesa skill for OpenClaw") still ties M-Pesa to OpenClaw.

**Better fix:** Build M-Pesa as a standalone Python module. It's just HTTP calls to Daraja API. No framework needed. 200 lines of Python.

### Gap 6: Power/reliability ✅ CORRECT

UPS battery backup is essential. The $20-30 estimate is realistic for a basic UPS that gives 2-4 hours of Pi runtime.

**Addition:** Consider a solar backup. Nyatike gets ~5-6 peak sun hours/day. A small 100W panel + battery could keep the Pi running indefinitely during daytime outages. ~$50-80 additional investment.

### Gap 7: Offline queue ✅ CORRECT

SQLite-backed offline queue is the right design. Process locally, sync when online.

### Gap 8: Kimi K3 unverified ✅ CORRECT

Don't depend on unverified claims. Gemma 4 and Qwen 3.5 are confirmed, well-documented, and Apache 2.0 licensed.

### Gap 9: No web UI ❌ THE FIX IS WRONG

The previous doc said "OpenClaw has no built-in customer-facing web UI. Need to build a simple kiosk interface."

This is true but the solution isn't to build a kiosk UI for OpenClaw. The solution is to build a standalone kiosk UI that talks to the FastAPI server. This is a 1-day project with basic HTML/JS.

### Gap 10: Data privacy ✅ CORRECT

In-memory processing, auto-purge, no cloud upload for sensitive data. This is the right approach.

**Addition the previous doc missed:** The previous architecture stored customer data in OpenClaw's memory system (MEMORY.md, daily logs). This is a privacy disaster. OpenClaw's memory files are plain text, searchable, and persist indefinitely. A cyber cafe should NEVER store customer ID numbers, KRA PINs, or personal details in any persistent text file.

---

## What the Previous Analysis Got Wrong (Additional Issues)

### 1. OpenClaw as Central Orchestrator — Architectural Mismatch

The entire architecture is built on OpenClaw as the "brain." But OpenClaw is a personal assistant platform. Its core concepts — SOUL.md, MEMORY.md, AGENTS.md, heartbeats, sessions, personas — are designed for one human having an ongoing relationship with an AI. A cyber cafe serves 30+ strangers a day who each want a one-shot service.

OpenClaw's own security docs explicitly warn against this use case:
> *"OpenClaw is not a hostile multi-tenant security boundary for multiple adversarial users sharing one agent or gateway."*

### 2. RAM Budget Underestimated by 1-1.5GB

The previous doc claims Gemma 4 E4B uses ~1.5GB. Realistic figure with Q4 quantization + KV cache + Ollama overhead: 2.5-3.0GB. This 1-1.5GB error on a Pi 5 with 8GB total is the difference between "system works" and "OOM killer starts terminating processes."

### 3. Skills Architecture Is Wrong for This Use Case

OpenClaw "skills" are designed as extensions of a persistent agent's capabilities. They assume the agent has memory, context, and an ongoing relationship with the user. For a cyber cafe:

- CV writing isn't a "skill" — it's a **service** with a defined input/output
- Form filling isn't a "skill" — it's a **workflow** with payment integration
- Translation isn't a "skill" — it's an **API endpoint**

Calling them "skills" adds conceptual overhead without benefit.

### 4. The Conversation Flow Design Leaks Data

The CV Writer SKILL.md describes a multi-turn conversation flow:
```
INIT → PACKAGE_SELECT → PERSONAL_INFO → EDUCATION → EXPERIENCE → SKILLS → REFERENCES → REVIEW → PAYMENT → GENERATE → DELIVERED
```

In OpenClaw, this conversation state lives in the session. If the session persists (which OpenClaw sessions do), Customer A's personal information (name, phone, education, work history) remains in memory when Customer B starts their session. This is a data leakage risk.

**Fix:** In the FastAPI approach, each conversation gets a UUID. All data lives in a temporary dict keyed by UUID. After delivery or timeout (30 minutes), the dict entry is deleted. No persistence. No leakage.

### 5. Missing: Concurrent User Handling

The previous architecture doesn't address concurrency. What happens when 3 customers send WhatsApp messages simultaneously?

- OpenClaw processes messages sequentially per session
- Ollama can only generate one response at a time per model (unless you run multiple model instances, which won't fit in RAM)

**Reality:** On a Pi 5 with Gemma 4 E4B, inference takes 5-15 seconds per response. With 3 concurrent customers, the 3rd customer waits 15-45 seconds. This is acceptable if handled correctly (queue + progress messages) but must be designed for.

**Fix in FastAPI:** Use an async queue. Customer messages go into a queue. Worker processes them FIFO. Send "Please wait, processing your request..." messages via WhatsApp while queued.

### 6. WhatsApp Business API Pricing Changed

The previous doc references "1000 free conversations/month." This is **outdated**.

**Current reality (2026):**
- **Service conversations** (customer-initiated): **FREE, unlimited**. No cap.
- **Template messages** (business-initiated): ~$0.01-0.04 per message in Africa.
- The old "1000 free conversations" tier is gone.

For a cyber cafe where customers message first ("I need a CV"), almost all interactions are service conversations = **free**.

### 7. No Error Recovery Design

What happens when:
- Ollama crashes? (It will, on Pi 5 under load)
- WhatsApp API times out?
- M-Pesa callback never arrives?
- Power goes out mid-conversation?

The previous architecture has no error recovery design. The FastAPI approach should include:
- Ollama health checks + auto-restart (systemd watchdog)
- WhatsApp message retry with exponential backoff
- M-Pesa callback polling (check transaction status if callback doesn't arrive within 60s)
- Conversation state persisted to SQLite so it survives power outages

---

## Final Recommendation

### Phase 1 (Weeks 1-2): Build Option B

Build the FastAPI server. It's the right foundation.

**What to build:**
1. FastAPI server with health endpoint
2. Ollama integration (httpx → localhost:11434)
3. WhatsApp Business Cloud API webhook handler
4. Telegram bot webhook handler
5. Basic service router (detect intent → route to handler)
6. SQLite database (payments, audit log)
7. systemd service file for auto-restart

**What NOT to build yet:**
- Voice pipeline (add in Phase 2)
- M-Pesa integration (add in Phase 2)
- Staff dashboard (add in Phase 3)
- n8n (add in Phase 3 if needed)

### Phase 2 (Weeks 3-4): Add Core Services

1. CV writing service (text-based first, voice later)
2. Translation service
3. M-Pesa STK Push integration
4. Whisper.cpp + Piper TTS voice pipeline
5. Offline queue (SQLite-backed)

### Phase 3 (Weeks 5-8): Staff Tools & Polish

1. Simple admin web UI (Streamlit or basic HTML)
2. n8n for staff workflows (if needed)
3. Government form filling service
4. Error recovery and monitoring
5. Usage analytics

### Phase 4 (Months 3-6): Scale

1. Multi-location deployment
2. Cloud fallback (Gemini API for complex tasks)
3. Additional languages
4. Solar power backup

---

## What About Option D (Hybrid)?

Option D (FastAPI + n8n) is the best long-term architecture. But for launch:

- You don't need n8n yet. Staff can manage via a simple admin page.
- Adding n8n later is easy — it's a separate service that talks to FastAPI via API.
- Starting with two systems doubles your initial complexity.

**Start with B. Evolve to D when staff need visual workflow editing.** This is typically Month 2-3.

---

## Honest Cost Estimate

| Item | One-Time | Monthly |
|---|---|---|
| Raspberry Pi 5 (8GB) | $80 | — |
| microSD 64GB | $10 | — |
| USB Microphone | $10 | — |
| USB Speaker | $15 | — |
| UPS Battery | $25 | — |
| WhatsApp Business API | $0 | $0-5 |
| Gemini API (cloud fallback) | — | $0-10 |
| Safaricom M-Pesa (Daraja) | — | ~1% transaction fee |
| **Total** | **~$140** | **$0-15/month** |

Developer time: 4-6 weeks for initial build (assuming 1 developer familiar with Python/FastAPI).

---

## Summary

| Question | Answer |
|---|---|
| Should Aego use OpenClaw? | **No.** It's a personal assistant platform, not a multi-tenant service platform. |
| What should Aego use? | **FastAPI + Ollama + WhatsApp Business API.** Purpose-built, minimal, correct. |
| Is the previous architecture doc wrong? | **Yes, fundamentally.** The OpenClaw-centric design is architecturally mismatched for a cyber cafe. |
| Are the 10 gap fixes correct? | **Mostly.** But RAM budget is underestimated by 1-1.5GB, and the data privacy fix doesn't go far enough. |
| What's the biggest risk? | **RAM on Pi 5.** Ollama + Gemma 4 E4B + voice pipeline + OS will use 4-5GB. Leaving only 3-4GB for the application layer. Tight but workable. |
| Can staff maintain this? | **Yes, once built.** The FastAPI server runs as a systemd service. Staff interact via WhatsApp and a simple admin dashboard. They never touch code. |

---

*Analysis completed July 19, 2026 | Aego Cyber Cafe Engineering*
*Author: Architecture validation subagent*
