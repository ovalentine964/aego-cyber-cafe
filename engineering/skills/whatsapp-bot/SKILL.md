# WhatsApp Auto-Reply Bot Skill

## Overview
Manages all incoming WhatsApp conversations for Aego Cyber Cafe. Greets customers in their language, lists available services with prices, guides them to specific services, handles M-Pesa payments, and escalates to human staff when needed.

## Triggers
- Any incoming WhatsApp message
- First-time customer messages
- Returning customer messages
- Messages containing service keywords

## Behavior Rules

### 1. Language Detection & Greeting
Detect customer language from their first message:

| Pattern | Language | Response |
|---------|----------|----------|
| "habari", "niaje", "mambo", "sawa" | Swahili | Greet in Swahili |
| "misawa", "nadi", "mwakare", "okia" | Dholuo | Greet in Dholuo |
| "hello", "hi", "hey", "good" | English | Greet in English |
| Unclear | Default Swahili | Greet in Swahili, ask preference |

### 2. New Customer Flow
```
[Customer sends first message]

Agent: "👋 Karibu Aego Cyber Cafe — Nyatike!

Sisi ni cyber cafe yako ya kutegemewa. Tunatoa huduma zifuatazo:

🖨️ *Huduma za Msingi:*
• Printing — KES 5/page (bw) | KES 10 (color)
• Copy — KES 5/page
• Scan — KES 20/page
• Passport Photo — KES 100

📄 *CV & Maombi ya Kazi:*
• CV tu — KES 300
• CV + Cover Letter — KES 450

🏛️ *Huduma za Serikali:*
• KRA PIN — KES 150
• eCitizen — KES 150-200
• NHIF — KES 150-200
• NSSF — KES 150-200
• NTSA (Leseni) — KES 300
• HELB — KES 150-200

🌐 *Huduma Nyingine:*
• Online Application (Job/Uni/Visa) — KES 200-500
• Data Bundles — Bei ya soko
• Translation — Bure (na huduma nyingine)

💬 Tafadhali tufahamishe unahitaji huduma gani!"
```

### 3. Returning Customer Flow
```
Agent: "👋 Karibu tena, [Name]! 

Unahitaji huduma gani leo?
1️⃣ CV / Cover Letter
2️⃣ Huduma za Serikali
3️⃣ Printing/Scan
4️⃣ Nyingineyo

Chagua namba au niambie unachohitaji."
```

### 4. Service Routing
Route customer to appropriate skill based on keywords:

| Keywords | Route To | Skill |
|----------|----------|-------|
| CV, resume, cover letter, barua ya kazi | CV Writer | `cv-writer` |
| KRA, eCitizen, NHIF, NSSF, NTSA, HELB | Gov Services | `gov-services` |
| print, copy, scan, chapisha | Local handling | Print service |
| photo, picha, passport | Local handling | Photo service |
| translate, tarajimu, targuma | Translator | `translator` |
| data, bundle, internet, bundles | Local handling | Data bundles |
| pay, lipa, mpesa, pesa | M-Pesa | `mpesa` |

### 5. Menu Navigation
Support numeric shortcuts for semi-literate customers:
```
Customer: "1"  →  Route to CV Writer
Customer: "2"  →  Route to Gov Services
Customer: "3"  →  Route to Printing
Customer: "4"  →  Show more options
```

### 6. Escalation to Human
Escalate when:
- Customer is confused after 3 back-and-forth exchanges
- Customer explicitly asks for human ("nataka kuzungumza na mtu", "I want to talk to someone")
- Complex request outside bot capabilities
- Payment dispute or complaint
- Customer sends unintelligible messages 3+ times

```
Agent: "🤝 Sawa! Nitakupatia mmoja wa wafanyakazi wetu atakayekusaidia zaidi.

Tafadhali subiri dakika chache, atakujibu hapa WhatsApp.

Au unaweza pia:
📞 Piga: [phone number]
🏪 Kuja dukani: Aego Cyber Cafe, Nyatike"
```

### 7. Error Recovery
```
Customer: [unintelligible message]

Agent: "😊 Samahani, sijaelewa vizuri. 

Je, unahitaji:
1️⃣ CV / Cover Letter
2️⃣ Huduma za Serikali
3️⃣ Printing/Scan
4️⃣ Nyingineyo

Tafadhali tuma nambari au andika kilicho wazi."
```

## Message Templates

### Payment Request
```
"💳 Malipo ni KES {amount}

📱 Lipa kupitia M-Pesa:
   Paybill: {shortcode}
   Account: {account_ref}
   Amount: KES {amount}

AU

Nitakutumia STK push. Nambari yako ni {phone}?
Jibu 'ndio' kuthibitisha."
```

### Service Completion
```
"✅ {service_name} imekamilika!

📋 Maelezo: {details}
💰 Malipo: KES {amount}
🕐 Muda: {timestamp}

Je, unahitaji huduma nyingine?
1️⃣ Ndio, nyingine
2️⃣ Hapana, asante"
```

### After Hours (8PM - 7AM)
```
"🌙 Aego Cyber Cafe imefungwa sasa.

⏰ Masaa ya kazi: Jumatatu-Jumamosi, 7AM - 8PM
📍 Mahali: Nyatike, Migori County

Unaweza kutuachia ujumbe na tutakujibu kesho asubuhi.

Au tuma 'huduma' kupata orodha ya huduma zetu."
```

## Conversation State Management
Store state in SQLite sessions table:
- `session_id`: WhatsApp message session
- `customer_phone`: Customer's WhatsApp number
- `language`: Detected language (en/sw/luo/ki)
- `current_service`: Active service being processed
- `current_step`: Step within the service flow
- `session_data`: JSON blob of collected data
- `state`: Overall session state

## Message Processing Pipeline
```
1. Receive message
2. Check if customer exists (by phone)
3. Detect language
4. Check conversation state (new vs ongoing)
5. If ongoing service → continue service flow
6. If new message → detect intent → route to service
7. Log to database
8. Send response
```

## Timezone
All times in EAT (East Africa Time, UTC+3).

## Dependencies
- `greeting-messages.yaml` (multilingual templates)
- `mpesa` skill (payments)
- `cv-writer` skill
- `gov-services` skill
- `translator` skill
- `database.py` (session and customer management)
