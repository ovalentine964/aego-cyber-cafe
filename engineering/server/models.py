"""
models.py — Pydantic models for Aego Cyber Cafe API.

All request/response schemas. No database models — sessions are in-memory only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────

class SessionState(str, Enum):
    COLLECTING = "collecting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    EXPIRED = "expired"


class ServiceType(str, Enum):
    CV = "cv"
    COVER_LETTER = "cover_letter"
    BOTH = "both"


# ── CV Models ─────────────────────────────────────────────────

class PersonalInfo(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., pattern=r"^0[17]\d{8}$")
    email: Optional[str] = None
    location: Optional[str] = None
    date_of_birth: Optional[str] = None


class Education(BaseModel):
    institution: str = Field(..., min_length=1)
    qualification: str = Field(..., min_length=1)
    year_start: Optional[str] = None
    year_end: Optional[str] = None
    grade: Optional[str] = None


class WorkExperience(BaseModel):
    company: str = Field(..., min_length=1)
    job_title: str = Field(..., min_length=1)
    duration_start: Optional[str] = None
    duration_end: Optional[str] = "Present"
    responsibilities: list[str] = Field(default_factory=list)


class Skills(BaseModel):
    technical: Optional[str] = None
    languages: Optional[str] = None
    soft: Optional[str] = None
    certifications: Optional[str] = None


class CVStartRequest(BaseModel):
    service_type: ServiceType = ServiceType.CV
    language: str = "en"


class CVSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionState = SessionState.COLLECTING
    service_type: ServiceType = ServiceType.CV
    language: str = "en"
    personal_info: Optional[PersonalInfo] = None
    education: list[Education] = Field(default_factory=list)
    experience: list[WorkExperience] = Field(default_factory=list)
    skills: Optional[Skills] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    output_files: dict[str, str] = Field(default_factory=dict)


# ── Government Services Models ────────────────────────────────

class GovServiceField(BaseModel):
    name: str
    value: Any


class GovServiceRequest(BaseModel):
    service_type: str  # e.g. "kra", "ecitizen", "nhif"
    sub_service: str   # e.g. "pin_registration", "account_creation"


class GovFieldSubmission(BaseModel):
    fields: dict[str, Any]


class GovSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionState = SessionState.COLLECTING
    service_type: str = ""
    sub_service: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    output_files: dict[str, str] = Field(default_factory=dict)


# ── Translation Models ────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    source_lang: Optional[str] = None  # auto-detect if None
    target_lang: str = Field(..., pattern=r"^(en|sw|luo|ki)$")


class TranslateResponse(BaseModel):
    original: str
    translated: str
    source_lang: str
    target_lang: str


# ── Voice Models ──────────────────────────────────────────────

class VoiceRequest(BaseModel):
    """Used for voice chat — text in, text+audio out."""
    text: Optional[str] = None
    language: Optional[str] = None


class VoiceResponse(BaseModel):
    transcription: Optional[str] = None
    response_text: str
    audio_url: Optional[str] = None
    language: str = "en"


# ── M-Pesa Models ─────────────────────────────────────────────

class MpesaStkRequest(BaseModel):
    phone: str = Field(..., pattern=r"^(0[17]\d{8}|254[17]\d{8})$")
    amount: int = Field(..., gt=0, le=100000)
    account_ref: str = Field(..., min_length=1, max_length=12)
    description: str = Field(default="Payment", max_length=13)


class MpesaCallback(BaseModel):
    """Safaricom STK Push callback payload."""
    Body: dict[str, Any] = {}


class MpesaStatus(BaseModel):
    checkout_request_id: str


class MpesaTransaction(BaseModel):
    id: int
    checkout_request_id: str
    phone: str
    amount: int
    service: str
    status: str
    mpesa_receipt: Optional[str] = None
    created_at: str
    updated_at: str


# ── Admin Models ──────────────────────────────────────────────

class AdminStats(BaseModel):
    date: str
    total_revenue: float = 0.0
    services_count: int = 0
    popular_services: list[dict[str, Any]] = Field(default_factory=list)
    active_sessions: int = 0


class ServiceRequestRecord(BaseModel):
    id: int
    session_id: str
    service_type: str
    customer_ref: str
    status: str
    amount: float = 0.0
    created_at: str


class SystemHealth(BaseModel):
    ollama_status: str = "unknown"
    ollama_model: str = ""
    disk_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    temperature_celsius: Optional[float] = None
    uptime_seconds: float = 0.0
    active_sessions: int = 0


# ── WhatsApp Models ───────────────────────────────────────────

class WhatsAppMessage(BaseModel):
    """Incoming WhatsApp webhook payload (simplified)."""
    object: str = ""
    entry: list[dict[str, Any]] = Field(default_factory=list)


# ── Telegram Models ───────────────────────────────────────────

class TelegramUpdate(BaseModel):
    """Incoming Telegram webhook payload."""
    update_id: int = 0
    message: Optional[dict[str, Any]] = None


# ── Generic Response ──────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Optional[dict[str, Any]] = None
