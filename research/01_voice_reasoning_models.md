# Voice & Reasoning On-Device Models — Research Report

**Report Date:** July 19, 2026
**Prepared for:** Aego Cyber Cafe / Valentine — AI-Powered Services for Africa
**Scope:** Developments in on-device voice/reasoning models relevant to Hadhi, SomoPal, and Aego Cyber Cafe services

---

## Executive Summary

The week ending July 19, 2026 marks a pivotal moment for on-device AI. Google's **Gemma 4 family** (released April 2026) now offers edge models with **native audio and vision** in as little as 2B effective parameters. OpenAI launched **GPT-Realtime-2** with voice reasoning and real-time translation across 70+ languages. Google released **Gemini 3.5 Live Translate** for speech-to-speech translation in 70+ languages. The open-source STT landscape has consolidated around **Whisper variants**, **Moonshine** (edge/mobile), **Canary Qwen** (top accuracy), and **Parakeet TDT** (ultra-low latency). Small reasoning models are maturing rapidly — Qwen 3.5 Small spans 0.8B–9B with 201 languages and thinking/non-thinking modes, and Phi-4 offers multimodal speech+vision+text in 5.6B parameters.

**Bottom line for Aego:** The technology stack for a voice-first, offline-capable, multilingual AI assistant for rural Africa is now viable. The recommended path is a **hybrid architecture** — on-device models for core voice/reasoning (Gemma 4 E4B, Whisper/Moonshine for STT, Phi-4 multimodal) with cloud fallback for complex tasks — achieving offline-first operation at minimal per-user cost.

---

## 1. On-Device Voice & Reasoning Model Releases

### 1.1 Google Gemma 4 Family — The Breakthrough for Edge AI

**Released:** April 2, 2026 | **License:** Apache 2.0 (fully open, commercial use allowed)

| Model | Effective Params | RAM (INT4) | Native Audio | Native Vision | Function Calling |
|-------|-----------------|------------|--------------|---------------|-----------------|
| **E2B** | 2B | 2–3 GB | ✅ | ✅ | ✅ |
| **E4B** | 4B | 4–6 GB | ✅ | ✅ | ✅ |
| **12B** | 12B | 16 GB | ✅ | ✅ | ✅ |
| **26B MoE** | 4B active / 26B total | ~16 GB | ✅ | ✅ | ✅ |
| **31B Dense** | 31B | ~32 GB | ✅ | ✅ | ✅ |

**Key technical details:**
- **Mixture-of-Experts (MoE) architecture** — only a subset of experts activate per input, keeping runtime cost low while maintaining rich representational capacity
- **Native audio input** — raw audio goes directly into the model without a separate STT pipeline step; fewer models to load, less latency, fewer failure points
- **Multimodal in one inference** — text, images, and audio processed simultaneously in the same context window
- **128K context window** on larger models
- **E2B runs on Raspberry Pi 5** (8GB RAM) at 3–8 tokens/second using llama.cpp with GGUF quantized weights
- **E4B runs on mid-range Android** (2023+, 6GB RAM, Snapdragon 8-series) at 10–25 tokens/second on flagship devices
- **12B model** (released June 3, 2026) — first mid-sized Gemma with native audio, runs on laptops with 16GB VRAM, performance nearing the 26B model
- **Multi-Token Prediction (MTP) drafters** built-in for latency reduction

**Sources:**
- Google Blog: "Gemma 4: Byte for byte, the most capable open models" (Apr 2, 2026) — https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/
- Google Blog: "Introducing Gemma 4 12B" (Jun 3, 2026) — https://blog.google/innovation-and-ai/technology/developers-tools/introducing-gemma-4-12b/
- MindStudio: "Gemma 4 for Edge Deployment" (Apr 3, 2026) — https://www.mindstudio.ai/blog/gemma-4-edge-deployment-e2b-e4b-models
- MindStudio: "Gemma 4 E2B vs E4B" (Apr 9, 2026) — https://www.mindstudio.ai/blog/gemma-4-e2b-vs-e4b-edge-models-audio-vision-phone

### 1.2 Microsoft Phi-4 Family

**Key models:**
- **Phi-4 Mini (3.8B):** Optimized for text tasks, strong reasoning for its size
- **Phi-4 Multimodal (5.6B):** Simultaneously processes **speech, vision, and text** in a single architecture — this is critical for our use cases

**Significance:** Phi-4 Multimodal is one of the few small models that handles voice input natively alongside text and vision. At 5.6B parameters, it fits on devices with 8–12GB RAM in quantized form.

**License:** MIT (fully open)

**Source:** Digital Applied: "Small Language Models Business Guide: Gemma, Phi, Qwen" (Apr 3, 2026) — https://www.digitalapplied.com/blog/small-language-models-business-guide-gemma-phi-qwen

### 1.3 Alibaba Qwen 3.5 Small Series

- **Parameter range:** 0.8B, 1.5B, 3B, 7B, 9B
- **Context window:** 256K tokens (largest among small models)
- **Language support:** 201 languages
- **Thinking/Non-thinking modes:** Can switch between fast inference and deliberate reasoning — critical for balancing latency and accuracy on edge devices
- **License:** Apache 2.0

**Why this matters for Aego:** The 201-language support and thinking modes make Qwen 3.5 uniquely suited for multilingual African contexts where users may code-switch between Swahili, English, Luo, and other local languages.

**Source:** Digital Applied: "Small Language Models Business Guide" (Apr 3, 2026) — https://www.digitalapplied.com/blog/small-language-models-business-guide-gemma-phi-qwen

### 1.4 Meta's On-Device LLM Perspective (2026)

Vikas Chandra (Meta AI Sr. Director) published a comprehensive overview of on-device LLMs in 2026:

**Key insights:**
- **Memory is the real bottleneck, not compute** — Mobile NPUs now deliver 35–60 TOPS (comparable to 2017 data center GPUs), but memory bandwidth is 50–90 GB/s vs. 2–3 TB/s on data center GPUs (30–50x gap)
- **Available RAM on mobile: <4GB** after OS overhead — this limits model size and MoE suitability
- **MobileLLM finding:** Deep-thin architectures (more layers, smaller hidden dimensions) outperform wide-shallow ones below 1B parameters
- **125M parameter model** with right architecture runs at 50 tokens/second on iPhone, handles basic tasks
- **Apple A19 Pro Neural Engine:** ~35 TOPS; **Qualcomm Snapdragon 8 Elite Gen 5:** ~60 TOPS; **MediaTek Dimensity 9400+:** ~50 TOPS
- **Going from 16-bit to 4-bit** isn't just 4x less storage — it's 4x less memory traffic per token, directly translating to throughput

**Source:** Vikas Chandra: "On-Device LLMs: State of the Union, 2026" (Jan 24, 2026) — https://v-chandra.github.io/on-device-llms/

### 1.5 Qualcomm & MediaTek On-Device AI

Both chipmakers are shipping 2026 phone SoCs optimized for on-device inference:
- **Samsung, Google, and Qualcomm** shipping phones in 2026 that support models up to 4B parameters in Q4 quantization
- Edge AI deployment in manufacturing grew **3x between 2025 and 2026**, with SLMs as the primary driver
- Three deployment tiers emerging: **sub-2B for IoT/mobile, 3B–5B for desktop/edge servers, 9B+ for local server deployments**

**Source:** Digital Applied (Apr 3, 2026) — https://www.digitalapplied.com/blog/small-language-models-business-guide-gemma-phi-qwen

---

## 2. Voice AI Breakthroughs

### 2.1 OpenAI GPT-Realtime-2 (May 7, 2026)

Three new API models for voice intelligence:

| Model | Capability | Languages |
|-------|-----------|-----------|
| **GPT-Realtime-2** | Voice-to-voice with GPT-5-class reasoning | Multiple |
| **GPT-Realtime-Translate** | Live speech translation | 70+ input → 13 output languages |
| **GPT-Realtime-Whisper** | Streaming speech-to-text | Multiple |

**GPT-Realtime-2 features:**
- **Preambles:** "Let me check that" phrases while reasoning — better UX
- **Parallel tool calls** with audible transparency
- **128K context window** (up from 32K)
- **Adjustable reasoning effort:** minimal, low, medium, high, xhigh
- **15.2% higher on Big Bench Audio** than GPT-Realtime-1.5
- **13.8% higher on Audio MultiChallenge** for instruction following

**Limitation:** Cloud-only, proprietary, per-token pricing — not suitable for offline deployment but excellent for hybrid architectures with cloud fallback.

**Source:** OpenAI: "Advancing voice intelligence with new models in the API" (May 7, 2026) — https://openai.com/index/advancing-voice-intelligence-with-new-models-in-the-api/

### 2.2 Google Gemini 3.5 Live Translate (June 9, 2026)

- **Speech-to-speech translation** in 70+ languages
- **Near real-time** — stays just a few seconds behind the speaker
- **Preserves intonation, pacing, and pitch** of the original speaker
- **Automatic language detection** — no manual configuration needed
- **Noise robustness** for loud environments
- **Available via:** Gemini Live API, Google AI Studio, Google Meet, Google Translate (Android/iOS)
- **2,000+ language combinations** possible in a single meeting

**Key partnerships:** Grab testing for multilingual driver-traveler communication (10M+ voice calls/month).

**Source:** Google Blog: "Gemini 3.5 Live Translate is here" (Jun 9, 2026) — https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-live-3-5-translate/

### 2.3 Microsoft Azure Live Interpreter API (Sep 2025)

- Real-time speech translation in Azure
- Public preview status
- Enterprise-grade with Azure compliance

**Source:** Microsoft Tech Community (Sep 12, 2025) — https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/announcing-live-interpreter-api---now-in-public-preview/4453649

### 2.4 Industry Trends — 7 Voice AI Predictions for 2026

From Speechmatics (Feb 2026):
1. **Voice becomes healthcare infrastructure** — not just a transcription feature
2. **High-stakes workflows demand different architectures** — cascading and speech-to-speech will coexist
3. **Operationalization replaces proof-of-concept** — near-zero latency orchestration matters more than standalone demos
4. **Speech recognition, translation, and AI voices maturing into a single seamless workflow**

**Source:** Speechmatics: "7 Voice AI predictions" (Feb 3, 2026) — https://www.speechmatics.com/company/articles-and-news/7-voice-ai-predictions-from-teams-building-at-scale-in-2026

---

## 3. Open-Source Speech-to-Text Models (2026 Landscape)

### 3.1 Comprehensive STT Model Comparison

| Model | WER (%) | RTFx | Parameters | Languages | VRAM | License | Best For |
|-------|---------|------|------------|-----------|------|---------|----------|
| **Canary Qwen 2.5B** | 5.63 | 418x | 2.5B | English | ~4GB | CC-BY-4.0 | Max English accuracy |
| **IBM Granite Speech 3.3 8B** | 5.85 | N/A | ~9B | EN/FR/DE/ES + translation | High | Apache 2.0 | Enterprise ASR + translation |
| **Whisper Large V3** | 7.4 | varies | 1.55B | 99+ | ~10GB | MIT | Multilingual leader |
| **Whisper Large V3 Turbo** | 7.75 | 216x | 809M | 99+ | ~6GB | MIT | Speed + multilingual |
| **Distil-Whisper** | ~7.5 | 5–6x Whisper | 756M | English | ~5GB | MIT | Efficient English |
| **Parakeet TDT 1.1B** | ~8.0 | >2,000x | 1.1B | English | ~4GB | CC-BY-4.0 | Ultra-low latency streaming |
| **Moonshine** | varies | fast | Small | English | Low | Open | **Edge & mobile** |
| **Faster-Whisper** | ~7.4 | 4x Whisper | 1.55B | 99+ | ~10GB | MIT | Production Whisper |
| **SpeechBrain** | varies | varies | varies | Multi | varies | Apache 2.0 | Research + customization |

**Sources:**
- Northflank: "Best open source STT model in 2026" (Jan 6, 2026) — https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks
- AssemblyAI: "Top 8 open source STT options for voice applications in 2026" (Jun 9, 2026) — https://www.assemblyai.com/blog/top-open-source-stt-options-for-voice-applications

### 3.2 Key STT Insights for Aego

**For offline/edge deployment in rural Kenya, the most relevant models are:**

1. **Moonshine** — Purpose-built for edge and mobile. Small enough to run on budget Android phones. Best for basic voice commands and short utterances.

2. **Whisper Large V3 Turbo** — 6x faster than full Whisper, 99+ languages, 6GB VRAM. Can run on a mid-range laptop at the Aego Cyber Cafe. **Best balance of multilingual support and speed.**

3. **Distil-Whisper** — 756M parameters, 6x faster than Whisper Large V3. Good for English-centric use cases.

4. **whisper.cpp** — The C/C++ port of Whisper with 46,900+ GitHub stars. Runs entirely offline on any platform. The backbone of most offline STT solutions in 2026.

**Critical gap for African languages:** Most STT models are optimized for high-resource languages. Swahili has reasonable support in Whisper (trained on some data), but Dholuo, Kikuyu, and other Kenyan languages have minimal training data. **Fine-tuning Whisper on local language data should be a priority.**

### 3.3 Offline Speech Recognition Market

- Global speech/voice recognition market: $9.66B (2025) → $23.11B (2030)
- 20%+ of vendors now offer on-device processing for privacy concerns
- On-premise speech solutions expanding at 22.71% CAGR through 2031
- whisper.cpp is the de facto standard for offline STT

**Source:** Weesper Neon Flow: "Best Offline Speech Recognition Software 2026" (Feb 23, 2026) — https://weesperneonflow.ai/en/blog/2026-02-23-best-offline-speech-recognition-software-2026-mac-windows/

---

## 4. Reasoning Model Updates

### 4.1 Efficient Reasoning Research

**Speculative Chain-of-Thought (SCoT)** — ACL 2026 Findings:
- Uses large models to draft reasoning chains, small models to verify and execute
- Achieves reasoning quality of large models at small-model inference cost
- Published at ACL 2026

**Source:** ACL Anthology: "Efficient Reasoning for LLMs through Speculative Chain-of-Thought" — https://aclanthology.org/2026.findings-acl.76.pdf

**Pruning Long Chain-of-Thought** (Jan 2026):
- Efficient method for reasoning that achieves strong performance using only small-scale preference data
- Reduces the token overhead of chain-of-thought reasoning — critical for on-device deployment where every token costs memory bandwidth

**Source:** OpenReview: "Pruning Long Chain-of-Thought of Large Reasoning Models" (Jan 26, 2026) — https://openreview.net/forum?id=8xSU8Oscvg

**Hierarchical Chain-of-Thought Prompting** (Mar 2026):
- Enhances LLM reasoning with structured hierarchical prompting
- Improves accuracy on multi-step reasoning tasks

**Source:** arXiv: "Hierarchical Chain-of-Thought Prompting" (Mar 31, 2026) — https://arxiv.org/html/2604.00130v1

### 4.2 Key Trend: Reasoning in Small Models

The IBM analysis notes that "advances enabling smaller models to effectively engage in CoT reasoning have democratized access to sophisticated reasoning capabilities." This is driven by:
- **Self-consistency** — generating multiple reasoning paths and selecting the most consistent answer
- **Distillation** — training small models to mimic large model reasoning chains
- **Dynamic compute allocation** — using thinking/non-thinking modes (as in Qwen 3.5) to reason deeply only when needed

**Source:** IBM: "What is chain of thought (CoT) prompting?" — https://www.ibm.com/think/topics/chain-of-thoughts

---

## 5. Analysis: Impact on Aego Ecosystem Products

### 5.1 Hadhi — Voice-Based AI CFO for Informal Workers

**Current challenge:** Hadhi needs to understand financial questions in local languages (Swahili, Dholuo, Kikuyu), reason about informal economy patterns, and respond via voice — all on basic Android phones with intermittent connectivity.

**Recommended stack:**

| Component | Model | Why |
|-----------|-------|-----|
| **STT (offline)** | Whisper Large V3 Turbo (via whisper.cpp) | 99+ languages, 6GB VRAM, can run on Aego's local server or mid-range phone |
| **STT (edge/budget)** | Moonshine | For the most resource-constrained devices |
| **Reasoning (offline)** | Gemma 4 E4B or Qwen 3.5-3B | Native audio input eliminates STT pipeline; Qwen's 201 languages + thinking mode ideal for financial reasoning |
| **Reasoning (cloud fallback)** | GPT-Realtime-2 or Gemini 3.5 | For complex financial analysis requiring deeper reasoning |
| **TTS (offline)** | Coqui TTS or Piper | Open-source TTS with Swahili support |
| **Translation** | Gemini 3.5 Live Translate (cloud) or fine-tuned Gemma 4 (offline) | 70+ languages, near real-time |

**Architecture recommendation:**
1. **Primary (offline):** Whisper.cpp → Gemma 4 E4B (with native audio, this can be a single model) → TTS
2. **Fallback (online):** GPT-Realtime-2 for complex reasoning, Gemini 3.5 Live Translate for translation
3. **Sync:** Queue financial transactions offline, sync when connectivity returns

**Cost implications:**
- Open-source stack (Whisper + Gemma 4 + Coqui TTS): **$0 per query** after hardware investment
- Cloud fallback (GPT-Realtime-2): ~$0.01–0.05 per voice interaction
- **Break-even vs. cloud-only: <18 months** for high-volume workloads

**Offline feasibility for rural Kenya:** ✅ Fully feasible with Gemma 4 E4B on a $150–200 Android phone (6GB RAM) or a Raspberry Pi 5 at the Aego Cyber Cafe.

### 5.2 SomoPal — Voice-First KCSE Tutor

**Current challenge:** SomoPal needs to explain complex academic concepts (math, science, English) via voice, adapt to student understanding, and work offline on student devices.

**Recommended stack:**

| Component | Model | Why |
|-----------|-------|-----|
| **STT** | Whisper Large V3 Turbo or Moonshine | Multilingual, handles student speech patterns |
| **Reasoning** | Gemma 4 12B (laptop/server) or E4B (phone) | 12B model has near-26B reasoning quality, native audio, runs on 16GB laptop |
| **Vision** | Gemma 4 12B or Phi-4 Multimodal | Can process textbook images, diagrams, handwritten math |
| **TTS** | Coqui TTS / Piper | Natural voice output |
| **Explanation reasoning** | Qwen 3.5-7B (thinking mode) | Deep reasoning for math/science problems when needed |

**Key advantage of Gemma 4 12B:**
- Native audio input — student speaks, model understands directly
- Native vision — student photographs a problem, model solves it
- 16GB VRAM requirement — runs on a mid-range laptop at the Aego Cyber Cafe
- Apache 2.0 license — can fine-tune for KCSE curriculum

**Offline feasibility:** ✅ The E4B runs on student phones; the 12B runs on the Aego Cyber Cafe's local server. For the most complex tutoring, cloud fallback to GPT-Realtime-2 or Gemini.

### 5.3 Aego Cyber Cafe Services (CV Writing, Government Services)

**Current challenge:** Automate document creation, form filling, and government service navigation via voice interaction in local languages.

**Recommended stack:**

| Component | Model | Why |
|-----------|-------|-----|
| **STT** | Whisper Large V3 Turbo | Multilingual, handles accented English + Swahili |
| **Document reasoning** | Gemma 4 26B MoE or 31B Dense | Complex document generation, form understanding |
| **Form understanding** | Gemma 4 E4B (vision) | Can photograph government forms and understand them |
| **Function calling** | Gemma 4 E4B/E2B | Native function calling enables structured form filling |
| **Translation** | Gemini 3.5 Live Translate or Qwen 3.5 | Translate between English/Swahili for government forms |

**Key advantage:** Gemma 4's **native function calling** means the model can output structured JSON that maps directly to form fields — no freeform parsing needed. A user speaks their details, the model fills the form.

**Offline feasibility:** ✅ Runs entirely on a Raspberry Pi 5 or local server at the cafe.

---

## 6. Cost Analysis

### 6.1 Open-Source vs. Proprietary

| Approach | Per-Query Cost | Upfront Cost | Offline Capable | African Language Support |
|----------|---------------|--------------|-----------------|------------------------|
| **Fully open-source (Gemma 4 + Whisper + Coqui)** | $0 | Hardware only ($150–500) | ✅ Full | Needs fine-tuning |
| **Hybrid (open-source + cloud fallback)** | $0.001–0.05 | Hardware + cloud budget | ✅ Partial | Better (cloud models) |
| **Fully cloud (GPT-Realtime-2 + Gemini)** | $0.01–0.10 | Minimal | ❌ | Best |

### 6.2 Hardware Requirements for Aego Cyber Cafe

| Deployment | Hardware | Cost (USD) | Models Supported |
|------------|----------|------------|-----------------|
| **Budget phone (student)** | Android, 6GB RAM, Snapdragon 6-series | $100–150 | Gemma 4 E2B, Moonshine, Phi-4 Mini |
| **Mid-range phone (Hadhi user)** | Android, 8GB RAM, Snapdragon 8-series | $200–300 | Gemma 4 E4B, Whisper Turbo, Phi-4 Multimodal |
| **Aego Cafe server** | Laptop/PC, 16GB+ RAM, GPU | $500–1000 | Gemma 4 12B, Qwen 3.5-9B, full Whisper |
| **Raspberry Pi 5** | 8GB RAM | $80 | Gemma 4 E2B, Moonshine, basic reasoning |
| **Edge server (cafe back-end)** | Desktop, 32GB RAM, RTX 4060+ | $1000–1500 | Gemma 4 26B MoE, full pipeline |

### 6.3 Cost Savings

ITRI research indicates edge AI deployment grew 3x between 2025–2026. Organizations report **70–90% cost reduction** after hardware investment, with break-even typically under 18 months.

**For Aego serving 1,000 users/day:**
- Cloud-only: ~$30–100/day = $900–3,000/month
- Hybrid (90% offline): ~$3–10/day = $90–300/month + one-time hardware
- **Savings: $600–2,700/month**

---

## 7. Recommendations & Next Steps

### 7.1 Immediate Actions (Next 30 Days)

1. **Prototype Gemma 4 E4B + Whisper.cpp pipeline** on a Raspberry Pi 5 or mid-range Android phone
   - Test native audio input for Swahili/English
   - Measure latency and accuracy for Hadhi's financial Q&A use case
   - Apache 2.0 license — no restrictions

2. **Evaluate Qwen 3.5-3B** for multilingual reasoning (201 languages, thinking mode)
   - Test code-switching between Swahili, English, and Dholuo
   - Compare with Gemma 4 E4B for Hadhi use case

3. **Fine-tune Whisper on Kenyan language data**
   - Collect Swahili, Dholuo, Kikuyu speech samples
   - Fine-tune Whisper Large V3 Turbo for improved local language WER
   - Use NeMo toolkit for Canary Qwen if English accuracy is priority

### 7.2 Short-Term (1–3 Months)

4. **Build the hybrid architecture**
   - On-device: Gemma 4 E4B (voice-in, reasoning, voice-out) + Whisper.cpp fallback
   - Cloud: GPT-Realtime-2 for complex reasoning, Gemini 3.5 Live Translate for translation
   - Offline queue + sync pattern for intermittent connectivity

5. **Prototype SomoPal with Gemma 4 12B**
   - Deploy on a laptop at the Aego Cyber Cafe
   - Test KCSE math/science tutoring with native audio + vision
   - Student photographs a problem → model explains step-by-step via voice

6. **Test Gemma 4 E4B function calling** for Aego's form-filling automation
   - Government forms → structured JSON output
   - Voice input → form completion workflow

### 7.3 Medium-Term (3–6 Months)

7. **Fine-tune Gemma 4 on Aego-specific data**
   - Financial advice patterns for informal workers (Hadhi)
   - KCSE curriculum content (SomoPal)
   - Government form templates (Aego services)
   - Apache 2.0 license allows full customization

8. **Build local language TTS**
   - Fine-tune Coqui TTS or Piper for Swahili, Dholuo, Kikuyu
   - Deploy on-device for natural voice responses

9. **Deploy Aego Cyber Cafe edge server**
   - Gemma 4 26B MoE for complex tasks
   - Local inference serving for all cafe customers
   - Zero per-query cost for walk-in users

### 7.4 Strategic Considerations

- **Apache 2.0 licensing** (Gemma 4, Qwen 3.5) is critical for Aego — no commercial restrictions, can fine-tune and deploy freely
- **Native audio in Gemma 4** eliminates the need for a separate STT model in many cases — simpler pipeline, lower latency, fewer failure points
- **The "125M parameter model runs at 50 tokens/second on iPhone"** finding from Meta means even the cheapest Android phones can run basic AI tasks
- **Privacy by design** — on-device inference means informal workers' financial data never leaves their phone
- **Battery/thermal constraints** are real — design for burst inference (process request → respond → sleep) rather than always-on

---

## 8. Models to Watch (Emerging, Not Yet Fully Evaluated)

| Model | Status | Relevance |
|-------|--------|-----------|
| **Kyutai Moshi** | Open-source speech-to-speech model | Direct voice-to-voice without STT/TTS pipeline |
| **MiniCPM-V** | Small multimodal model | Competitive with Phi-4 for vision+language on edge |
| **Liquid Foundation Models** | Hybrid architectures for edge | Novel approach to efficient on-device inference |
| **Samsung Gauss** | On-device model for Galaxy phones | May set hardware baseline for budget Android deployment |
| **Apple Intelligence updates** | On-device + Private Cloud Compute | iOS baseline, but less relevant for Android-first Africa |

---

## 9. Key Papers & Resources

1. **"Efficient Reasoning for LLMs through Speculative Chain-of-Thought"** — ACL 2026 Findings — https://aclanthology.org/2026.findings-acl.76.pdf
2. **"Pruning Long Chain-of-Thought of Large Reasoning Models"** — OpenReview, Jan 2026 — https://openreview.net/forum?id=8xSU8Oscvg
3. **"Hierarchical Chain-of-Thought Prompting"** — arXiv, Mar 2026 — https://arxiv.org/html/2604.00130v1
4. **"On-Device LLMs: State of the Union, 2026"** — Meta AI, Jan 2026 — https://v-chandra.github.io/on-device-llms/
5. **"Small Language Models Business Guide: Gemma, Phi, Qwen"** — Digital Applied, Apr 2026 — https://www.digitalapplied.com/blog/small-language-models-business-guide-gemma-phi-qwen
6. **Northflank STT Benchmarks** — Jan 2026 — https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks
7. **AssemblyAI: Top 8 Open Source STT** — Jun 2026 — https://www.assemblyai.com/blog/top-open-source-stt-options-for-voice-applications

---

## 10. Conclusion

The convergence of three trends makes this the right time for Aego to build on-device voice AI:

1. **Models are small enough:** Gemma 4 E4B (4B params, 4GB RAM) with native audio/vision matches what 100B+ models delivered 18 months ago
2. **Hardware is cheap enough:** A $150 Android phone or $80 Raspberry Pi 5 can run meaningful AI inference
3. **Licensing is open enough:** Apache 2.0 (Gemma 4, Qwen 3.5) and MIT (Whisper) mean no commercial barriers

**The recommended architecture is:**
- **Device layer:** Gemma 4 E4B + whisper.cpp for offline voice processing
- **Cafe layer:** Gemma 4 12B/26B on local server for complex tasks
- **Cloud layer:** GPT-Realtime-2 + Gemini 3.5 Live Translate for fallback and translation

This gives Hadhi, SomoPal, and Aego Cyber Cafe services **offline-first operation** with intelligent cloud escalation — the right architecture for rural Kenya where connectivity is a feature, not a guarantee.

---

*Report generated July 19, 2026. Sources accessed same week unless otherwise noted.*
