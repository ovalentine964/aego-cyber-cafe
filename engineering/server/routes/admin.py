"""
routes/admin.py — Staff Dashboard API for Aego Cyber Cafe.

Endpoints:
  GET  /api/admin/stats     — today's revenue, services count, popular services
  GET  /api/admin/requests  — recent service requests
  GET  /api/admin/payments  — recent payments
  GET  /api/admin/health    — system health (Ollama, disk, temp, connectivity)
  POST /api/admin/approve/{request_id} — staff approval for generated documents

Basic auth (username/password from env vars).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import time
from datetime import datetime, date
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import cfg
from models import APIResponse, AdminStats, SystemHealth
from session_manager import SessionManager

logger = logging.getLogger("aego.routes.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])
security = HTTPBasic()

# Will be set by main.py
sessions: SessionManager = None  # type: ignore
_start_time: float = time.time()


def init(session_mgr: SessionManager) -> None:
    """Initialize route dependencies."""
    global sessions
    sessions = session_mgr


def _verify_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Verify basic auth credentials."""
    if credentials.username != cfg.ADMIN_USERNAME:
        raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Basic"})
    if credentials.password != cfg.ADMIN_PASSWORD:
        raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Basic"})
    return credentials.username


def _get_db():
    """Get SQLite connection with row factory."""
    db_path = Path(cfg.DATA_DIR) / "aego.db"
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/stats", response_model=APIResponse)
async def get_stats(username: str = Depends(_verify_auth)) -> APIResponse:
    """Get today's revenue, services count, and popular services."""
    today = date.today().isoformat()
    active_sessions = await sessions.count_active()

    conn = _get_db()
    if conn is None:
        return APIResponse(
            success=True,
            message="No data yet",
            data=AdminStats(
                date=today,
                active_sessions=active_sessions,
            ).model_dump(),
        )

    try:
        # Today's revenue
        row = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
            FROM transactions
            WHERE status = 'success' AND DATE(created_at) = ?
            """,
            (today,),
        ).fetchone()
        total_revenue = row["total"] if row else 0
        services_count = row["count"] if row else 0

        # Popular services
        popular = conn.execute(
            """
            SELECT service, COUNT(*) as count, SUM(amount) as revenue
            FROM transactions
            WHERE status = 'success' AND DATE(created_at) = ?
            GROUP BY service
            ORDER BY count DESC
            LIMIT 5
            """,
            (today,),
        ).fetchall()

        popular_list = [
            {"service": r["service"], "count": r["count"], "revenue": r["revenue"]}
            for r in popular
        ]

        return APIResponse(
            success=True,
            message="Today's stats",
            data=AdminStats(
                date=today,
                total_revenue=total_revenue,
                services_count=services_count,
                popular_services=popular_list,
                active_sessions=active_sessions,
            ).model_dump(),
        )
    finally:
        conn.close()


@router.get("/requests", response_model=APIResponse)
async def get_requests(
    limit: int = 20,
    username: str = Depends(_verify_auth),
) -> APIResponse:
    """Get recent service requests from transactions."""
    conn = _get_db()
    if conn is None:
        return APIResponse(success=True, message="No data", data={"requests": []})

    try:
        rows = conn.execute(
            """
            SELECT id, checkout_request_id, phone, amount, service, status,
                   mpesa_receipt, created_at
            FROM transactions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (min(limit, 100),),
        ).fetchall()

        requests_list = [
            {
                "id": r["id"],
                "checkout_request_id": r["checkout_request_id"],
                "phone": r["phone"],
                "amount": r["amount"],
                "service": r["service"],
                "status": r["status"],
                "receipt": r["mpesa_receipt"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

        return APIResponse(
            success=True,
            message=f"Last {len(requests_list)} requests",
            data={"requests": requests_list},
        )
    finally:
        conn.close()


@router.get("/payments", response_model=APIResponse)
async def get_payments(
    limit: int = 20,
    username: str = Depends(_verify_auth),
) -> APIResponse:
    """Get recent successful payments."""
    conn = _get_db()
    if conn is None:
        return APIResponse(success=True, message="No data", data={"payments": []})

    try:
        rows = conn.execute(
            """
            SELECT id, checkout_request_id, phone, amount, service,
                   mpesa_receipt, created_at
            FROM transactions
            WHERE status = 'success'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (min(limit, 100),),
        ).fetchall()

        payments = [
            {
                "id": r["id"],
                "checkout_request_id": r["checkout_request_id"],
                "phone": r["phone"],
                "amount": r["amount"],
                "service": r["service"],
                "receipt": r["mpesa_receipt"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

        return APIResponse(
            success=True,
            message=f"Last {len(payments)} payments",
            data={"payments": payments},
        )
    finally:
        conn.close()


@router.get("/health", response_model=APIResponse)
async def get_health(username: str = Depends(_verify_auth)) -> APIResponse:
    """Get system health: Ollama, disk, memory, temperature, connectivity."""
    health = SystemHealth()
    health.uptime_seconds = time.time() - _start_time
    health.active_sessions = await sessions.count_active()

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{cfg.OLLAMA_HOST}/api/tags")
            if resp.status_code == 200:
                health.ollama_status = "running"
                models = resp.json().get("models", [])
                health.ollama_model = ", ".join(m["name"] for m in models[:3])
            else:
                health.ollama_status = "error"
    except Exception:
        health.ollama_status = "unreachable"

    # Disk usage
    try:
        usage = shutil.disk_usage(cfg.DATA_DIR)
        health.disk_usage_percent = round((usage.used / usage.total) * 100, 1)
    except Exception:
        pass

    # Memory usage (Linux /proc/meminfo)
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = int(parts[1].strip().split()[0])  # kB
                    mem[key] = val
            total = mem.get("MemTotal", 0)
            available = mem.get("MemAvailable", 0)
            health.memory_usage_mb = round((total - available) / 1024, 1)
    except Exception:
        pass

    # Temperature (Raspberry Pi thermal zone)
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp_milli = int(f.read().strip())
            health.temperature_celsius = round(temp_milli / 1000, 1)
    except Exception:
        pass

    return APIResponse(
        success=True,
        message="System health",
        data=health.model_dump(),
    )


@router.post("/approve/{request_id}", response_model=APIResponse)
async def approve_request(
    request_id: int,
    username: str = Depends(_verify_auth),
) -> APIResponse:
    """Staff approval for a generated document/service request."""
    conn = _get_db()
    if conn is None:
        raise HTTPException(404, "No database found")

    try:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (request_id,)
        ).fetchone()

        if not row:
            raise HTTPException(404, f"Request {request_id} not found")

        conn.execute(
            """
            UPDATE transactions
            SET status = 'approved', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (request_id,),
        )
        conn.commit()

        logger.info(f"Request {request_id} approved by {username}")

        return APIResponse(
            success=True,
            message=f"Request {request_id} approved",
            data={
                "request_id": request_id,
                "service": row["service"],
                "status": "approved",
                "approved_by": username,
            },
        )
    finally:
        conn.close()
