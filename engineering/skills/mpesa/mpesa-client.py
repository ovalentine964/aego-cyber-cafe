#!/usr/bin/env python3
"""
M-Pesa Daraja API Client for Aego Cyber Cafe
Handles STK Push, B2C payments, transaction queries, and callbacks.

Usage:
    python3 mpesa-client.py stk-push --phone 0712345678 --amount 300 --account-ref "CV-JOHN" --description "CV Service"
    python3 mpesa-client.py stk-query --checkout-request-id "ws_CO_19072026_12345"
    python3 mpesa-client.py b2c --phone 0712345678 --amount 300 --reason "Refund"
    python3 mpesa-client.py transaction-status --transaction-id "QHJ3K5PLMN"
    python3 mpesa-client.py balance
    python3 mpesa-client.py callback-server --port 8080
"""

import argparse
import base64
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Lock
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import yaml

# Configuration
SKILL_DIR = Path(__file__).parent
CONFIG_PATH = SKILL_DIR / "mpesa-config.yaml"
DB_PATH = Path("/opt/aego/data/aego.db")
LOG_DIR = Path("/opt/aego/logs")

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "mpesa.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("mpesa-client")


class MpesaConfig:
    """M-Pesa configuration loader."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.config = self._load_config()
        self.env = self.config.get("environment", "sandbox")
        self._env_config = self.config.get(self.env, {})
        self._endpoints = self.config.get("endpoints", {}).get(self.env, {})

    def _load_config(self) -> dict:
        """Load YAML configuration."""
        if not self.config_path.exists():
            logger.error(f"Config file not found: {self.config_path}")
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    @property
    def consumer_key(self) -> str:
        return self._env_config.get("consumer_key", "")

    @property
    def consumer_secret(self) -> str:
        return self._env_config.get("consumer_secret", "")

    @property
    def shortcode(self) -> str:
        return self._env_config.get("shortcode", "")

    @property
    def passkey(self) -> str:
        return self._env_config.get("passkey", "")

    @property
    def callback_url(self) -> str:
        return self._env_config.get("callback_url", "")

    @property
    def base_url(self) -> str:
        return self._endpoints.get("base_url", "https://sandbox.safaricom.co.ke")

    @property
    def oauth_url(self) -> str:
        return f"{self.base_url}{self._endpoints.get('oauth', '')}"

    @property
    def stk_push_url(self) -> str:
        return f"{self.base_url}{self._endpoints.get('stk_push', '')}"

    @property
    def stk_query_url(self) -> str:
        return f"{self.base_url}{self._endpoints.get('stk_query', '')}"

    @property
    def b2c_url(self) -> str:
        return f"{self.base_url}{self._endpoints.get('b2c', '')}"

    @property
    def transaction_status_url(self) -> str:
        return f"{self.base_url}{self._endpoints.get('transaction_status', '')}"

    @property
    def account_balance_url(self) -> str:
        return f"{self.base_url}{self._endpoints.get('account_balance', '')}"

    @property
    def reversal_url(self) -> str:
        return f"{self.base_url}{self._endpoints.get('reversal', '')}"

    @property
    def initiator_password(self) -> str:
        return self._env_config.get("initiator_password", "")

    @property
    def security_credential(self) -> str:
        return self._env_config.get("security_credential", "")

    @property
    def timeouts(self) -> dict:
        return self.config.get("timeouts", {})

    @property
    def retry_config(self) -> dict:
        return self.config.get("retry", {})


class TokenManager:
    """Manages OAuth tokens with caching."""

    def __init__(self, config: MpesaConfig):
        self.config = config
        self._token = None
        self._expires_at = 0
        self._lock = Lock()

    def get_token(self) -> str:
        """Get a valid OAuth token, refreshing if needed."""
        with self._lock:
            if self._token and time.time() < self._expires_at:
                return self._token
            return self._refresh_token()

    def _refresh_token(self) -> str:
        """Fetch a new OAuth token from Safaricom."""
        credentials = base64.b64encode(
            f"{self.config.consumer_key}:{self.config.consumer_secret}".encode()
        ).decode()

        req = Request(
            self.config.oauth_url,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
        )

        try:
            timeout = self.config.timeouts.get("connection", 30)
            with urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
                self._token = data["access_token"]
                # Token valid for ~1 hour, refresh 5 min early
                self._expires_at = time.time() + int(data.get("expires_in", 3500)) - 300
                logger.info("OAuth token refreshed successfully")
                return self._token
        except (URLError, HTTPError) as e:
            logger.error(f"Failed to get OAuth token: {e}")
            raise ConnectionError(f"Failed to authenticate with M-Pesa API: {e}")


class MpesaClient:
    """M-Pesa Daraja API client."""

    def __init__(self, config: MpesaConfig = None):
        self.config = config or MpesaConfig()
        self.token_manager = TokenManager(self.config)

    def _make_request(self, url: str, payload: dict, method: str = "POST") -> dict:
        """Make an authenticated API request."""
        token = self.token_manager.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers=headers, method=method)

        retry_config = self.config.retry_config
        max_attempts = retry_config.get("max_attempts", 3)
        delay = retry_config.get("delay_seconds", 5)
        backoff = retry_config.get("backoff_multiplier", 2)

        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                timeout = self.config.timeouts.get("connection", 30)
                with urlopen(req, timeout=timeout) as resp:
                    response_data = json.loads(resp.read())
                    logger.info(f"API request to {url} succeeded (attempt {attempt})")
                    return response_data
            except HTTPError as e:
                last_error = e
                error_body = ""
                try:
                    error_body = e.read().decode()
                except Exception:
                    pass
                logger.warning(
                    f"API request failed (attempt {attempt}/{max_attempts}): "
                    f"HTTP {e.code} - {error_body}"
                )
                # Don't retry on client errors (4xx)
                if 400 <= e.code < 500:
                    raise
            except URLError as e:
                last_error = e
                logger.warning(
                    f"API request failed (attempt {attempt}/{max_attempts}): {e.reason}"
                )

            if attempt < max_attempts:
                wait = delay * (backoff ** (attempt - 1))
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)

        raise ConnectionError(f"API request failed after {max_attempts} attempts: {last_error}")

    def generate_password(self) -> str:
        """Generate the STK push password (base64 of shortcode+passkey+timestamp)."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password_str = f"{self.config.shortcode}{self.config.passkey}{timestamp}"
        return base64.b64encode(password_str.encode()).decode(), timestamp

    def stk_push(
        self,
        phone: str,
        amount: int,
        account_ref: str,
        description: str = "Payment",
    ) -> dict:
        """
        Initiate an STK Push (Lipa Na M-Pesa Online).

        Args:
            phone: Customer phone number (format: 254XXXXXXXXX or 07XXXXXXXX)
            amount: Amount in KES
            account_ref: Account reference (e.g., "CV-JOHNDOE-20260719")
            description: Transaction description

        Returns:
            dict with CheckoutRequestID, ResponseCode, ResponseDescription, MerchantRequestID
        """
        # Normalize phone number to 254 format
        phone = self._normalize_phone(phone)
        password, timestamp = self.generate_password()

        payload = {
            "BusinessShortCode": self.config.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": str(amount),
            "PartyA": phone,
            "PartyB": self.config.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.config.callback_url,
            "AccountReference": account_ref[:12],  # Max 12 chars
            "TransactionDescription": description[:13],  # Max 13 chars
        }

        logger.info(f"Initiating STK Push: phone={phone}, amount={amount}, ref={account_ref}")
        response = self._make_request(self.config.stk_push_url, payload)

        # Log to database
        self._log_transaction(
            phone=phone,
            amount=amount,
            service=account_ref,
            checkout_request_id=response.get("CheckoutRequestID", ""),
            status="initiated",
        )

        return response

    def stk_query(self, checkout_request_id: str) -> dict:
        """
        Query the status of an STK Push transaction.

        Args:
            checkout_request_id: The CheckoutRequestID from stk_push response

        Returns:
            dict with ResponseCode, ResultDesc, etc.
        """
        password, timestamp = self.generate_password()

        payload = {
            "BusinessShortCode": self.config.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }

        logger.info(f"Querying STK status: {checkout_request_id}")
        return self._make_request(self.config.stk_query_url, payload)

    def b2c(
        self,
        phone: str,
        amount: int,
        reason: str = "Payment",
        occasion: str = "",
    ) -> dict:
        """
        Initiate a B2C (Business to Customer) payment / disbursement.

        Args:
            phone: Customer phone number
            amount: Amount in KES
            reason: Payment reason
            occasion: Occasion (optional)

        Returns:
            dict with ConversationID, OriginatorConversationID, ResponseCode, etc.
        """
        phone = self._normalize_phone(phone)

        payload = {
            "InitiatorName": "AegoCafe",
            "SecurityCredential": self.config.security_credential,
            "CommandID": "BusinessPayment",
            "Amount": str(amount),
            "PartyA": self.config.shortcode,
            "PartyB": phone,
            "Remarks": reason[:100],
            "QueueTimeOutURL": f"{self.config.callback_url}/b2c/timeout",
            "ResultURL": f"{self.config.callback_url}/b2c/result",
            "Occasion": occasion[:100] if occasion else reason[:100],
        }

        logger.info(f"Initiating B2C: phone={phone}, amount={amount}, reason={reason}")
        response = self._make_request(self.config.b2c_url, payload)

        # Log refund
        self._log_transaction(
            phone=phone,
            amount=-amount,  # Negative for outgoing
            service=f"refund:{reason}",
            checkout_request_id=response.get("OriginatorConversationID", ""),
            status="b2c_initiated",
        )

        return response

    def transaction_status(self, transaction_id: str) -> dict:
        """
        Query the status of a transaction by Mpesa receipt number.

        Args:
            transaction_id: M-Pesa receipt/transaction ID

        Returns:
            dict with transaction status details
        """
        payload = {
            "Initiator": "AegoCafe",
            "SecurityCredential": self.config.security_credential,
            "TransactionID": transaction_id,
            "PartyA": self.config.shortcode,
            "IdentifierType": "4",  # Organization
            "ResultURL": f"{self.config.callback_url}/transaction/result",
            "QueueTimeOutURL": f"{self.config.callback_url}/transaction/timeout",
            "Remarks": "Transaction status query",
            "Occasion": "Status check",
        }

        logger.info(f"Querying transaction status: {transaction_id}")
        return self._make_request(self.config.transaction_status_url, payload)

    def account_balance(self) -> dict:
        """Query the M-Pesa account balance."""
        payload = {
            "Initiator": "AegoCafe",
            "SecurityCredential": self.config.security_credential,
            "CommandID": "AccountBalance",
            "PartyA": self.config.shortcode,
            "IdentifierType": "4",
            "Remarks": "Balance inquiry",
            "QueueTimeOutURL": f"{self.config.callback_url}/balance/timeout",
            "ResultURL": f"{self.config.callback_url}/balance/result",
        }

        logger.info("Querying account balance")
        return self._make_request(self.config.account_balance_url, payload)

    def wait_for_stk_result(
        self, checkout_request_id: str, timeout: int = None
    ) -> dict:
        """
        Wait for STK push result by polling.

        Args:
            checkout_request_id: The CheckoutRequestID from stk_push
            timeout: Max wait time in seconds

        Returns:
            dict with final transaction status
        """
        if timeout is None:
            timeout = self.config.timeouts.get("stk_push_wait", 60)

        query_delay = self.config.timeouts.get("stk_query_delay", 10)
        start_time = time.time()

        logger.info(f"Waiting for STK result: {checkout_request_id} (timeout: {timeout}s)")

        # Initial delay before first query
        time.sleep(query_delay)

        while time.time() - start_time < timeout:
            try:
                result = self.stk_query(checkout_request_id)
                response_code = result.get("ResponseCode", "")

                if response_code == "0":
                    # Success
                    self._update_transaction_status(checkout_request_id, "success", result)
                    logger.info(f"STK payment successful: {checkout_request_id}")
                    return {
                        "status": "success",
                        "result": result,
                        "mpesa_receipt": result.get("MpesaReceiptNumber", ""),
                    }
                elif response_code == "1032":
                    # User cancelled
                    self._update_transaction_status(checkout_request_id, "cancelled")
                    logger.info(f"STK payment cancelled by user: {checkout_request_id}")
                    return {"status": "cancelled", "result": result}
                elif response_code == "1037":
                    # DS timeout (phone unreachable)
                    self._update_transaction_status(checkout_request_id, "timeout")
                    logger.warning(f"STK payment timeout (DS): {checkout_request_id}")
                    return {"status": "timeout", "result": result}
                else:
                    # Still pending or other error
                    logger.debug(f"STK still pending: {checkout_request_id}, code={response_code}")

            except Exception as e:
                logger.warning(f"Error querying STK status: {e}")

            time.sleep(5)  # Poll every 5 seconds

        # Timeout reached
        self._update_transaction_status(checkout_request_id, "timeout")
        logger.warning(f"STK payment wait timed out: {checkout_request_id}")
        return {"status": "timeout", "message": "No response received within timeout period"}

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone number to 254XXXXXXXXX format."""
        phone = phone.strip().replace(" ", "").replace("-", "")

        if phone.startswith("+"):
            phone = phone[1:]

        if phone.startswith("0"):
            phone = "254" + phone[1:]
        elif phone.startswith("7") or phone.startswith("1"):
            phone = "254" + phone

        if not phone.startswith("254") or len(phone) != 12:
            raise ValueError(f"Invalid phone number format: {phone}. Expected: 07XXXXXXXX or 254XXXXXXXXX")

        return phone

    def _log_transaction(
        self,
        phone: str,
        amount: int,
        service: str,
        checkout_request_id: str = "",
        status: str = "initiated",
    ) -> None:
        """Log transaction to SQLite database."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            # Ensure table exists
            cursor.execute("""
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

            cursor.execute("""
                INSERT INTO transactions (checkout_request_id, phone, amount, service, account_ref, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (checkout_request_id, phone, amount, service, service, status))

            conn.commit()
            conn.close()
            logger.debug(f"Transaction logged: {checkout_request_id}")
        except Exception as e:
            logger.error(f"Failed to log transaction: {e}")

    def _update_transaction_status(
        self,
        checkout_request_id: str,
        status: str,
        raw_response: dict = None,
    ) -> None:
        """Update transaction status in database."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            mpesa_receipt = ""
            if raw_response:
                mpesa_receipt = raw_response.get("MpesaReceiptNumber", "")

            cursor.execute("""
                UPDATE transactions
                SET status = ?, mpesa_receipt = ?, raw_response = ?, updated_at = CURRENT_TIMESTAMP
                WHERE checkout_request_id = ?
            """, (status, mpesa_receipt, json.dumps(raw_response) if raw_response else None, checkout_request_id))

            conn.commit()
            conn.close()
            logger.debug(f"Transaction updated: {checkout_request_id} -> {status}")
        except Exception as e:
            logger.error(f"Failed to update transaction: {e}")


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for M-Pesa callbacks."""

    def do_POST(self):
        """Handle POST callback from M-Pesa."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
            logger.info(f"Callback received on {self.path}: {json.dumps(data, indent=2)}")

            # Process based on path
            if "/b2c/result" in self.path:
                self._handle_b2c_result(data)
            elif "/b2c/timeout" in self.path:
                self._handle_b2c_timeout(data)
            elif "/transaction/result" in self.path:
                self._handle_transaction_result(data)
            elif "/balance/result" in self.path:
                self._handle_balance_result(data)
            else:
                # Default: STK push callback
                self._handle_stk_callback(data)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ResultCode": 0, "ResultDesc": "Success"}).encode())

        except Exception as e:
            logger.error(f"Callback processing error: {e}", exc_info=True)
            self.send_response(500)
            self.end_headers()

    def _handle_stk_callback(self, data: dict) -> None:
        """Handle STK Push callback."""
        body = data.get("Body", {}).get("stkCallback", {})
        result_code = body.get("ResultCode")
        checkout_request_id = body.get("CheckoutRequestID", "")
        result_desc = body.get("ResultDesc", "")

        logger.info(f"STK Callback: {checkout_request_id}, code={result_code}, desc={result_desc}")

        client = MpesaClient()

        if result_code == 0:
            # Extract M-Pesa receipt from callback metadata
            metadata = body.get("CallbackMetadata", {}).get("Item", [])
            mpesa_receipt = ""
            amount = 0
            phone = ""

            for item in metadata:
                name = item.get("Name", "")
                if name == "MpesaReceiptNumber":
                    mpesa_receipt = item.get("Value", "")
                elif name == "Amount":
                    amount = item.get("Value", 0)
                elif name == "PhoneNumber":
                    phone = item.get("Value", "")

            client._update_transaction_status(
                checkout_request_id,
                "success",
                {
                    "MpesaReceiptNumber": mpesa_receipt,
                    "Amount": amount,
                    "PhoneNumber": phone,
                    "ResultCode": result_code,
                    "ResultDesc": result_desc,
                },
            )
            logger.info(f"Payment confirmed: receipt={mpesa_receipt}, amount={amount}, phone={phone}")
        else:
            client._update_transaction_status(checkout_request_id, "failed", body)
            logger.warning(f"Payment failed: {checkout_request_id}, reason={result_desc}")

    def _handle_b2c_result(self, data: dict) -> None:
        """Handle B2C result callback."""
        logger.info(f"B2C Result: {json.dumps(data, indent=2)}")

    def _handle_b2c_timeout(self, data: dict) -> None:
        """Handle B2C timeout callback."""
        logger.warning(f"B2C Timeout: {json.dumps(data, indent=2)}")

    def _handle_transaction_result(self, data: dict) -> None:
        """Handle transaction status result."""
        logger.info(f"Transaction Result: {json.dumps(data, indent=2)}")

    def _handle_balance_result(self, data: dict) -> None:
        """Handle account balance result."""
        logger.info(f"Balance Result: {json.dumps(data, indent=2)}")

    def log_message(self, format, *args):
        """Override to use logger instead of stderr."""
        logger.debug(format % args)


def run_callback_server(port: int = 8080):
    """Start the callback HTTP server."""
    server = HTTPServer(("0.0.0.0", port), CallbackHandler)
    logger.info(f"M-Pesa callback server started on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Callback server shutting down")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Aego Cyber Cafe — M-Pesa Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # STK Push
    stk_parser = subparsers.add_parser("stk-push", help="Initiate STK Push payment")
    stk_parser.add_argument("--phone", required=True, help="Customer phone number")
    stk_parser.add_argument("--amount", required=True, type=int, help="Amount in KES")
    stk_parser.add_argument("--account-ref", required=True, help="Account reference")
    stk_parser.add_argument("--description", default="Payment", help="Transaction description")
    stk_parser.add_argument("--wait", action="store_true", help="Wait for payment result")
    stk_parser.add_argument("--timeout", type=int, default=60, help="Wait timeout in seconds")
    stk_parser.add_argument("--json-output", action="store_true", help="Output as JSON")

    # STK Query
    query_parser = subparsers.add_parser("stk-query", help="Query STK Push status")
    query_parser.add_argument("--checkout-request-id", required=True, help="CheckoutRequestID")
    query_parser.add_argument("--json-output", action="store_true", help="Output as JSON")

    # B2C
    b2c_parser = subparsers.add_parser("b2c", help="Initiate B2C payment (refund)")
    b2c_parser.add_argument("--phone", required=True, help="Recipient phone number")
    b2c_parser.add_argument("--amount", required=True, type=int, help="Amount in KES")
    b2c_parser.add_argument("--reason", default="Refund", help="Payment reason")
    b2c_parser.add_argument("--json-output", action="store_true", help="Output as JSON")

    # Transaction Status
    status_parser = subparsers.add_parser("transaction-status", help="Query transaction status")
    status_parser.add_argument("--transaction-id", required=True, help="M-Pesa transaction ID")
    status_parser.add_argument("--json-output", action="store_true", help="Output as JSON")

    # Account Balance
    subparsers.add_parser("balance", help="Query account balance")

    # Callback Server
    server_parser = subparsers.add_parser("callback-server", help="Start callback HTTP server")
    server_parser.add_argument("--port", type=int, default=8080, help="Port to listen on")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    client = MpesaClient()

    if args.command == "stk-push":
        result = client.stk_push(
            phone=args.phone,
            amount=args.amount,
            account_ref=args.account_ref,
            description=args.description,
        )

        if args.wait:
            checkout_id = result.get("CheckoutRequestID", "")
            if checkout_id:
                print(f"⏳ Waiting for payment result ({args.timeout}s)...")
                final = client.wait_for_stk_result(checkout_id, args.timeout)
                if args.json_output:
                    print(json.dumps(final, indent=2))
                else:
                    status = final.get("status", "unknown")
                    if status == "success":
                        print(f"✅ Payment successful!")
                        print(f"   Receipt: {final.get('mpesa_receipt', 'N/A')}")
                    elif status == "cancelled":
                        print("❌ Payment cancelled by customer")
                    elif status == "timeout":
                        print("⏰ Payment timed out — check later with:")
                        print(f"   python3 mpesa-client.py stk-query --checkout-request-id {checkout_id}")
                    else:
                        print(f"⚠️ Status: {status}")
            else:
                print(f"❌ STK Push failed: {result}")
        else:
            if args.json_output:
                print(json.dumps(result, indent=2))
            else:
                print(f"📱 STK Push sent!")
                print(f"   CheckoutRequestID: {result.get('CheckoutRequestID', 'N/A')}")
                print(f"   Response: {result.get('ResponseDescription', 'N/A')}")
                print(f"\n   Use --wait to wait for payment confirmation")

    elif args.command == "stk-query":
        result = client.stk_query(args.checkout_request_id)
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            code = result.get("ResponseCode", "N/A")
            desc = result.get("ResultDesc", "N/A")
            print(f"📋 STK Query Result:")
            print(f"   Code: {code}")
            print(f"   Description: {desc}")
            if code == "0":
                print(f"   Receipt: {result.get('MpesaReceiptNumber', 'N/A')}")

    elif args.command == "b2c":
        result = client.b2c(
            phone=args.phone,
            amount=args.amount,
            reason=args.reason,
        )
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"💸 B2C Payment Initiated:")
            print(f"   ConversationID: {result.get('ConversationID', 'N/A')}")
            print(f"   Response: {result.get('ResponseDescription', 'N/A')}")

    elif args.command == "transaction-status":
        result = client.transaction_status(args.transaction_id)
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"📋 Transaction Status:")
            print(json.dumps(result, indent=2))

    elif args.command == "balance":
        result = client.account_balance()
        print(f"💰 Account Balance Query:")
        print(json.dumps(result, indent=2))

    elif args.command == "callback-server":
        run_callback_server(args.port)


if __name__ == "__main__":
    main()
