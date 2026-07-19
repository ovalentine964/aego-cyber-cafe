"""
routes/mpesa.py — M-Pesa Payment endpoints for Aego Cyber Cafe.

Endpoints:
  POST /api/mpesa/stk-push        — initiate STK push to customer phone
  POST /api/mpesa/callback         — Safaricom callback endpoint
  GET  /api/mpesa/status/{id}      — check payment status

Uses the mpesa-client.py module from skills/mpesa/.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request

from config import cfg
from models import APIResponse, MpesaStkRequest, MpesaCallback

logger = logging.getLogger("aego.routes.mpesa")
router = APIRouter(prefix="/api/mpesa", tags=["mpesa"])

# In-memory store for pending STK requests (checkout_id → status)
_pending_payments: dict[str, dict] = {}


def init() -> None:
    """Initialize route dependencies. Ensure DB tables exist."""
    _ensure_db()


def _ensure_db() -> None:
    """Ensure the transactions table exists."""
    db_path = Path(cfg.DATA_DIR) / "aego.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checkout_request_id TEXT,
            phone TEXT NOT NULL,
            amount INTEGER NOT NULL,
            service TEXT,
            account_ref TEXT,
            mpesa_receipt TEXT,
            status TEXT DEFAULT 'initiated',
            raw_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _log_transaction(
    phone: str,
    amount: int,
    service: str,
    checkout_request_id: str = "",
    status: str = "initiated",
) -> int:
    """Log transaction to SQLite. Returns row ID."""
    db_path = Path(cfg.DATA_DIR) / "aego.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        """
        INSERT INTO transactions (checkout_request_id, phone, amount, service, account_ref, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (checkout_request_id, phone, amount, service, service, status),
    )
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def _update_transaction(checkout_request_id: str, status: str, receipt: str = "", raw: dict | None = None) -> None:
    """Update transaction status."""
    db_path = Path(cfg.DATA_DIR) / "aego.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        UPDATE transactions
        SET status = ?, mpesa_receipt = ?, raw_response = ?, updated_at = CURRENT_TIMESTAMP
        WHERE checkout_request_id = ?
        """,
        (status, receipt, json.dumps(raw) if raw else None, checkout_request_id),
    )
    conn.commit()
    conn.close()


async def _get_oauth_token() -> str:
    """Get M-Pesa OAuth token from Safaricom."""
    import base64
    credentials = base64.b64encode(
        f"{cfg.MPESA_CONSUMER_KEY}:{cfg.MPESA_CONSUMER_SECRET}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{cfg.mpesa_base_url}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {credentials}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]


def _generate_stk_password() -> tuple[str, str]:
    """Generate STK push password and timestamp."""
    import base64
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password_str = f"{cfg.MPESA_SHORTCODE}{cfg.MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(password_str.encode()).decode(), timestamp


def _normalize_phone(phone: str) -> str:
    """Normalize phone to 254XXXXXXXXX format."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif phone.startswith("7") or phone.startswith("1"):
        phone = "254" + phone
    if not phone.startswith("254") or len(phone) != 12:
        raise ValueError(f"Invalid phone: {phone}")
    return phone


@router.post("/stk-push", response_model=APIResponse)
async def stk_push(req: MpesaStkRequest) -> APIResponse:
    """Initiate M-Pesa STK Push to customer phone."""
    if not cfg.MPESA_CONSUMER_KEY or not cfg.MPESA_PASSKEY:
        raise HTTPException(500, "M-Pesa not configured. Set MPESA_* environment variables.")

    try:
        phone = _normalize_phone(req.phone)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        token = await _get_oauth_token()
        password, timestamp = _generate_stk_password()

        callback_url = cfg.MPESA_CALLBACK_URL or f"https://your-domain.com/api/mpesa/callback"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{cfg.mpesa_base_url}/mpesa/stkpush/v1/processrequest",
                json={
                    "BusinessShortCode": cfg.MPESA_SHORTCODE,
                    "Password": password,
                    "Timestamp": timestamp,
                    "TransactionType": "CustomerPayBillOnline",
                    "Amount": str(req.amount),
                    "PartyA": phone,
                    "PartyB": cfg.MPESA_SHORTCODE,
                    "PhoneNumber": phone,
                    "CallBackURL": callback_url,
                    "AccountReference": req.account_ref[:12],
                    "TransactionDescription": req.description[:13],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        checkout_id = data.get("CheckoutRequestID", "")

        # Log to DB
        _log_transaction(
            phone=phone,
            amount=req.amount,
            service=req.account_ref,
            checkout_request_id=checkout_id,
            status="initiated",
        )

        # Track in memory for status checks
        _pending_payments[checkout_id] = {
            "status": "pending",
            "phone": phone,
            "amount": req.amount,
            "created_at": time.time(),
        }

        logger.info(f"STK Push initiated: {checkout_id} (phone={phone}, amount={req.amount})")

        return APIResponse(
            success=True,
            message="STK Push sent. Customer should check their phone.",
            data={
                "checkout_request_id": checkout_id,
                "merchant_request_id": data.get("MerchantRequestID", ""),
                "response_code": data.get("ResponseCode", ""),
                "response_description": data.get("ResponseDescription", ""),
                "customer_message": data.get("CustomerMessage", ""),
            },
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"STK Push API error: {e.response.text}")
        raise HTTPException(502, f"M-Pesa API error: {e.response.text}")
    except Exception as e:
        logger.error(f"STK Push failed: {e}", exc_info=True)
        raise HTTPException(500, f"STK Push failed: {e}")


@router.post("/callback")
async def mpesa_callback(request: Request) -> dict:
    """
    Safaricom M-Pesa STK Push callback endpoint.
    Safaricom sends payment confirmation here.
    """
    try:
        body = await request.json()
        logger.info(f"M-Pesa callback received: {json.dumps(body, indent=2)}")

        stk = body.get("Body", {}).get("stkCallback", {})
        result_code = stk.get("ResultCode")
        checkout_id = stk.get("CheckoutRequestID", "")
        result_desc = stk.get("ResultDesc", "")

        if result_code == 0:
            # Payment successful — extract receipt
            metadata = stk.get("CallbackMetadata", {}).get("Item", [])
            receipt = ""
            amount = 0
            phone = ""

            for item in metadata:
                name = item.get("Name", "")
                if name == "MpesaReceiptNumber":
                    receipt = item.get("Value", "")
                elif name == "Amount":
                    amount = item.get("Value", 0)
                elif name == "PhoneNumber":
                    phone = item.get("Value", "")

            _update_transaction(checkout_id, "success", receipt, stk)
            _pending_payments[checkout_id] = {
                "status": "success",
                "receipt": receipt,
                "amount": amount,
                "phone": phone,
            }
            logger.info(f"Payment confirmed: {checkout_id} receipt={receipt}")

        else:
            _update_transaction(checkout_id, "failed", raw=stk)
            _pending_payments[checkout_id] = {
                "status": "failed",
                "reason": result_desc,
            }
            logger.warning(f"Payment failed: {checkout_id} — {result_desc}")

        # Always return success to Safaricom
        return {"ResultCode": 0, "ResultDesc": "Success"}

    except Exception as e:
        logger.error(f"Callback processing error: {e}", exc_info=True)
        return {"ResultCode": 0, "ResultDesc": "Received"}


@router.get("/status/{checkout_request_id}", response_model=APIResponse)
async def payment_status(checkout_request_id: str) -> APIResponse:
    """Check M-Pesa payment status."""
    # Check in-memory first
    pending = _pending_payments.get(checkout_request_id)
    if pending:
        return APIResponse(
            success=True,
            message=f"Payment status: {pending['status']}",
            data=pending,
        )

    # Check database
    db_path = Path(cfg.DATA_DIR) / "aego.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM transactions WHERE checkout_request_id = ?",
            (checkout_request_id,),
        ).fetchone()
        conn.close()

        if row:
            return APIResponse(
                success=True,
                message=f"Payment status: {row['status']}",
                data={
                    "status": row["status"],
                    "phone": row["phone"],
                    "amount": row["amount"],
                    "receipt": row["mpesa_receipt"],
                    "created_at": row["created_at"],
                },
            )

    # If not found locally, query Safaricom
    if cfg.MPESA_CONSUMER_KEY and cfg.MPESA_PASSKEY:
        try:
            token = await _get_oauth_token()
            password, timestamp = _generate_stk_password()

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{cfg.mpesa_base_url}/mpesa/stkpushquery/v1/query",
                    json={
                        "BusinessShortCode": cfg.MPESA_SHORTCODE,
                        "Password": password,
                        "Timestamp": timestamp,
                        "CheckoutRequestID": checkout_request_id,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()

            code = data.get("ResponseCode", "")
            status = "success" if code == "0" else "pending" if code == "1037" else "unknown"

            return APIResponse(
                success=True,
                message=f"Safaricom status: {data.get('ResultDesc', 'unknown')}",
                data={
                    "status": status,
                    "response_code": code,
                    "result_desc": data.get("ResultDesc", ""),
                    "mpesa_receipt": data.get("MpesaReceiptNumber", ""),
                },
            )
        except Exception as e:
            logger.warning(f"STK query failed: {e}")

    raise HTTPException(404, "Payment not found")
