# Government Services Skill

## Overview
Guides customers through Kenyan government service applications. Supports voice-guided step-by-step flows for KRA, eCitizen, NHIF, NSSF, NTSA, and HELB services. Validates inputs and generates filled forms.

## Triggers
- "KRA" / "kra pin" / "cra pin" / "tax"
- "eCitizen" / "ecitizen" / "serikali" / "government"
- "NHIF" / "nhif" / "health insurance" / "bima ya afya"
- "NSSF" / "nssf" / "social security" / "pension"
- "NTSA" / "ntsa" / "driving license" / "leseni" / "licence"
- "HELB" / "helb" / "loan" / "student loan"
- "government service" / "huduma za serikali"

## Pricing
| Service | Fee (KES) |
|---------|-----------|
| KRA PIN Registration | 150 |
| KRA PIN Retrieval | 150 |
| KRA Returns Filing | 200 |
| eCitizen Account Creation | 150 |
| eCitizen Service Application | 200 |
| NHIF Registration | 150 |
| NHIF Replacement Card | 200 |
| NSSF Registration | 150 |
| NSSF Statement | 200 |
| NTSA License Application | 300 |
| NTSA Logbook Transfer | 300 |
| HELB Application | 200 |
| HELB Statement | 150 |

## Conversation Flow

### Step 1: Service Identification
```
Customer: "Nataka KRA PIN"
Agent: "Sawa! Nitakusaidia na KRA PIN. 🏛️

Je, unahitaji:
1️⃣ KRA PIN mpya (Registration)
2️⃣ Kupata PIN uliyopotea (Retrieval)
3️⃣ Kujaza Returns (Tax Returns)

Chagua 1, 2, au 3:"
```

### Step 2: Document Checklist
Before collecting data, inform customer of required documents:
```
Agent: "Kabla ya kuanza, hakuna una:
✅ Kitambulisho (National ID / Passport)
✅ Nambari ya simu
✅ [Service-specific documents]

Uko tayari?"
```

### Step 3: Information Collection
Collect required fields per service (see service-catalog.json).
Use validation patterns for each field.

### Step 4: Data Validation
Validate in real-time:
- National ID: exactly 8 digits
- KRA PIN: format A123456789B (letter + 9 digits + letter)
- Phone: 07XX or 01XX format, 10 digits
- NHIF Number: numeric, 8-10 digits

### Step 5: Payment
Trigger M-Pesa payment via `mpesa` skill.

### Step 6: Service Execution
- Generate filled forms
- Guide customer through portal steps
- Provide step-by-step screenshots/instructions

## Voice Input Handling
```bash
# Transcribe voice note
bash mimo_api.sh audio /path/to/audio.ogg "Extract: full name, ID number, phone number, and any other personal details mentioned"
```

## Validation Patterns
| Field | Pattern | Example |
|-------|---------|---------|
| National ID | `^\d{8}$` | 12345678 |
| KRA PIN | `^[A-Z]\d{9}[A-Z]$` | A123456789B |
| Phone | `^0[17]\d{8}$` | 0712345678 |
| NHIF No | `^\d{8,10}$` | 12345678 |
| NSSF No | `^\d{8,10}$` | 12345678 |

## Error Handling
- Invalid input format → show example of correct format
- Missing documents → list what's needed, offer to continue when ready
- Portal downtime → save progress, offer to continue later
- Payment failure → retry once, then offer alternative payment

## State Management
Store in SQLite sessions table:
- Current service and sub-service
- Collected data fields
- Current step in flow
- Payment status

## Dependencies
- `service-catalog.json` (service definitions)
- `form-filler.py` (form generation)
- `mpesa` skill (payments)
- `mimo-omni` skill (voice transcription)
