# M-Pesa Integration Skill

## Overview
Handles all M-Pesa payment processing for Aego Cyber Cafe. Supports STK Push (Lipa Na M-Pesa Online), payment confirmation via callbacks, transaction status queries, and B2C disbursements for refunds.

## Triggers
- Any service requiring payment (CV writing, government services, etc.)
- "pay" / "lipa" / "malipo" / "M-Pesa" / "pesa"
- Payment confirmation callbacks from Safaricom

## Pricing
Payment processing is included in service fees. No additional charges.

## Payment Flow

### Step 1: Initiate Payment
When a service requires payment:
```
Agent: "💳 Malipo ni KES {amount}

Tuma M-Pesa kwa:
📱 Paybill: {shortcode}
💰 Account: {account_ref}
💵 Amount: KES {amount}

AU

Nitakutumia STK push kwenye simu yako. Nambari yako ni {phone}?
Jibu 'ndio' kuthibitisha."
```

### Step 2: STK Push
```python
# Trigger STK push via mpesa-client.py
python3 mpesa-client.py stk-push \
    --phone 0712345678 \
    --amount 300 \
    --account-ref "CV-JOHNDOE-20260719" \
    --description "CV Writing Service"
```

### Step 3: Wait for Confirmation
The system waits for the M-Pesa callback (up to 60 seconds).
During this time:
```
Agent: "⏳ Subiri... M-Pesa inashughulikia malipo yako.
📱 Angalia simu yako na uweke PIN yako ya M-Pesa."
```

### Step 4: Payment Result
On success:
```
Agent: "✅ Malipo yamefanikiwa!
📋 Receipt: QHJ3K5PLMN
💰 Amount: KES 300
🕐 Time: 2026-07-19 16:45

Sasa tutaanza kukutengenezea CV yako..."
```

On failure:
```
Agent: "❌ Malipo hayajafanika. Jaribu tena.
Sababu: {error_reason}

Je, unataka:
1️⃣ Jaribu tena
2️⃣ Lipa baadaye
3️⃣ Lipa pesa taslimu ukiwa dukani"
```

## Voice Handling
For customers who send voice notes about payment:
```bash
bash mimo_api.sh audio /path/to/audio.ogg "Extract: phone number, payment amount, any payment details mentioned"
```

## M-Pesa Transaction States
| State | Description | Action |
|-------|-------------|--------|
| initiated | STK push sent to phone | Wait for customer response |
| pending | Waiting for callback | Wait up to 60s |
| success | Payment confirmed | Proceed with service |
| failed | Payment declined/failed | Offer retry or alternatives |
| timeout | No response in time | Offer retry |
| cancelled | Customer cancelled | Offer alternatives |

## Database Records
Every transaction is recorded in SQLite via `database.py`:
```json
{
    "id": "TXN-20260719-001",
    "phone": "0712345678",
    "amount": 300,
    "service": "cv_writer",
    "account_ref": "CV-JOHNDOE-20260719",
    "mpesa_receipt": "QHJ3K5PLMN",
    "status": "success",
    "timestamp": "2026-07-19T16:45:00+03:00"
}
```

## Error Scenarios & Recovery
| Error | Recovery |
|-------|----------|
| STK push timeout | Retry once, then offer manual paybill |
| Insufficient funds | Ask customer to top up and retry |
| Wrong PIN | Customer retries on phone |
| Network error | Wait 30s, retry |
| Duplicate transaction | Check DB, reuse existing confirmation |
| Callback missing | Query transaction status after 90s |

## B2C Disbursement (Refunds)
For refund scenarios:
```python
python3 mpesa-client.py b2c \
    --phone 0712345678 \
    --amount 300 \
    --reason "Refund for failed CV generation"
```

## Security Notes
- Never display full M-Pesa credentials
- Log all transactions for audit
- Validate phone number format before STK push
- Amount must match service price (no customer-set amounts)
- All transactions are one-way (customer → business) except refunds

## Dependencies
- `mpesa-client.py` (Daraja API client)
- `mpesa-config.yaml` (API configuration)
- `database.py` (transaction storage)
