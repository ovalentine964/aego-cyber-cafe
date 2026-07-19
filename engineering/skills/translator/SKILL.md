# Translation Skill

## Overview
Provides real-time translation between English, Swahili, Dholuo, and Kikuyu. Supports text and voice input, document translation, and photo-based text extraction and translation.

## Triggers
- "translate" / "tarajimu" / "targuma" / "change language"
- "nini maana ya [word]" / "what does [word] mean"
- "how do you say [phrase] in [language]"
- Customer writes in one language and asks for another

## Supported Languages
| Code | Language | Native Name |
|------|----------|-------------|
| en | English | English |
| sw | Swahili | Kiswahili |
| luo | Dholuo | Dholuo |
| ki | Kikuyu | Gĩkũyũ |

## Pricing
- Text translation: **Free** (included with any paid service)
- Document translation: **KES 100** per page
- Voice translation: **Free** with any service

## Capabilities

### 1. Text Translation
```
Customer: "Translate 'I need a job' to Swahili"
Agent: "'I need a job' kwa Kiswahili ni:
📝 'Ninahitaji kazi'

Je, unahitaji kutafsiri zaidi?"
```

### 2. Voice Translation
When customer sends voice note:
```bash
# Step 1: Transcribe audio
bash mimo_api.sh audio /path/to/audio.ogg "Transcribe the speech. Identify the language spoken."

# Step 2: Translate transcription to target language
# (Use model to translate the transcribed text)
```

### 3. Document Translation
- Customer sends photo of document
- Use `mimo-omni` to extract text via OCR
- Translate extracted text
- Return formatted translation

```bash
# Extract text from image
bash mimo_api.sh image /path/to/document.jpg "Extract all text from this document. Preserve formatting."
```

### 4. Word/Phrase Lookup
```
Customer: "Nini maana ya 'opportunity' kwa Dholuo?"
Agent: "'Opportunity' kwa Dholuo ni:
📝 'chance' — misawa
📝 'opportunity' — tembe (kama nafasi ya kazi)

Matumizi: 'I got an opportunity' → 'Anyam chenya tembe'"
```

## Translation Flow

### Step 1: Detect Source Language
Analyze the input text or transcribed voice to identify source language.

### Step 2: Identify Target Language
- Explicit request: "translate to Swahili"
- Implicit: If customer writes in Swahili and asks "translate this", translate to English
- Ask if unclear: "Unataka kutafsiri kwa lugha gani? 🇬🇧 English, 🇰🇪 Kiswahili, au Dholuo?"

### Step 3: Translate
Use the model's multilingual capabilities. For best results:
- Preserve meaning over literal translation
- Use local idioms and expressions where appropriate
- Maintain formal/informal tone based on context

### Step 4: Verify & Deliver
- Show both original and translation
- Ask if customer needs modifications
- Offer alternative translations for ambiguous terms

## Language-Specific Notes

### Dholuo
- No standardized written form in many contexts
- Use common Latin-script conventions
- Tonal differences are lost in text; provide context when ambiguous

### Kikuyu
- Uses Latin script with some special characters
- Some words have multiple meanings based on context

### Swahili
- Official Kenyan language alongside English
- Most customers will be comfortable in Swahili

## Common Translations Reference
Quick reference for common cyber cafe terms:

| English | Swahili | Dholuo |
|---------|---------|--------|
| CV | CV (barua ya wasifu) | CV |
| Job application | Maombi ya kazi | Miw kaze |
| Printing | Kuchapisha | Chopo |
| Copy | Nakala | Nakal |
| Scan | Kuchanganua | Skan |
| Form | Fomu | Fom |
| Signature | Saini | Sain |
| Document | Hati | Hati |
| Photo | Picha | Picha |
| Payment | Malipo | Mach |
| How much? | Bei gani? | En ang'o? |
| Thank you | Asante | Erokamano |

## Error Handling
- Unintelligible audio → ask customer to speak more clearly or type
- Unsupported language → apologize and list supported languages
- Ambiguous translation → provide multiple options with context
- Long document → process in chunks, warn about processing time

## Dependencies
- `mimo-omni` skill (voice transcription and OCR)
- OpenClaw model (translation engine)
