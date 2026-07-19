# CV Writer Skill

## Overview
Assists customers in creating professional CVs and cover letters through conversational AI. Supports voice input, multiple languages (English/Swahili), and generates print-ready PDF documents.

## Triggers
- "write my CV" / "create my CV" / "I need a CV"
- "nataka CV" / "andika CV yangu" / "CV yangu"
- "cover letter" / "barua ya kazi"
- Any mention of CV, resume, or job application documents

## Pricing
- CV only: **KES 300**
- CV + Cover Letter: **KES 450**

## Conversation Flow

### Step 1: Greeting & Package Selection
```
Customer: "Nataka CV"
Agent: "Karibu Aego Cyber Cafe! 🎉

Tunaweza kukusaidia na CV yako.

📦 Chagua package:
1️⃣ CV tu — KES 300
2️⃣ CV + Cover Letter — KES 450

Chagua 1 au 2:"
```

### Step 2: Collect Personal Information
After package selection, collect in order:
1. Full name (jina lako kamili)
2. Phone number (nambari ya simu)
3. Email address (barua pepe — optional)
4. Date of birth (tarehe ya kuzaliwa)
5. Address / Location (mahali unapoishi)
6. Career objective / Professional summary (malengo ya kazi)

**Voice handling:** If customer sends voice note, use `mimo-omni` skill to transcribe, then extract structured data from the transcription.

### Step 3: Collect Education
Ask for each education entry:
- Institution name (jina la shule/college)
- Qualification (cheti, diploma, degree)
- Year started — Year completed
- Grade/marks (optional)

Allow multiple entries: "Je, una elimu nyingine?"

### Step 4: Collect Work Experience
For each job:
- Company name (jina la kampuni)
- Job title (cheo cha kazi)
- Duration (from — to)
- Key responsibilities (majukumu makuu)

If no work experience: "Je, una internship, volunteer work, au mafunzo yoyote?"

### Step 5: Collect Skills
- Technical skills (stadi za kiufundi)
- Languages spoken (lugha unazozungumza)
- Soft skills (stadi za mawasiliano, uongozi, etc.)
- Certifications / Courses (vyeti/mafunzo)

### Step 6: Collect References
- 2-3 references with name, title, phone, relationship
- Option: "Nitaweka 'Available on request' kama huna sasa"

### Step 7: Review & Confirm
Display summary of all collected data. Ask customer to confirm or request changes.

### Step 8: Payment
Trigger M-Pesa STK push via `mpesa` skill:
```
Use skill: mpesa
Action: stk_push
Amount: 300 (or 450)
Phone: [customer phone]
AccountRef: CV-[customer_name]-[timestamp]
```

### Step 9: Generate & Deliver
After payment confirmation:
1. Run `cv-generator.py` with collected JSON data
2. Generate PDF
3. Send PDF to customer via WhatsApp
4. Save backup to `/opt/aego/output/`

## Data Collection State Machine
```
INIT → PACKAGE_SELECT → PERSONAL_INFO → EDUCATION → EXPERIENCE → SKILLS → REFERENCES → REVIEW → PAYMENT → GENERATE → DELIVERED
```

Store conversation state in SQLite `sessions` table to handle interruptions.

## Language Handling
- Detect customer language from first message
- Conduct entire conversation in detected language
- CV content is always in English (industry standard)
- Cover letter can be in English or Swahili per customer choice

## Voice Input Processing
When customer sends voice note:
```bash
bash mimo_api.sh audio /path/to/audio.ogg "Transcribe and extract: full name, phone, education, work experience"
```

## Error Handling
- If customer provides incomplete info → ask again gently with examples
- If payment fails → retry once, then offer pay-on-delivery
- If PDF generation fails → generate HTML version and offer to retry PDF
- If customer switches language mid-conversation → follow their lead

## Output
- PDF file: `/opt/aego/output/cv_{customer_name}_{date}.pdf`
- Cover letter: `/opt/aego/output/cover_{customer_name}_{date}.pdf`
- HTML backup: same path with `.html` extension

## Dependencies
- `cv-generator.py` (in this skill directory)
- `cv-template.html` (template file)
- `cover-letter-template.html` (template file)
- `mpesa` skill (for payments)
- `mimo-omni` skill (for voice transcription)
- `weasyprint` or `wkhtmltopdf` (for PDF conversion)
