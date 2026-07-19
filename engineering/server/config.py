"""
config.py — Configuration from environment variables for Aego Cyber Cafe server.

All settings are loaded from environment variables with sensible defaults.
Designed for Raspberry Pi 5 with 8GB RAM — conservative memory defaults.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    """Immutable server configuration loaded from environment."""

    # ── Ollama LLM ────────────────────────────────────────────
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma4:4b")
    OLLAMA_FALLBACK_MODEL: str = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen3.5:3b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))

    # ── WhatsApp Business Cloud API ───────────────────────────
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "aego_verify_token")

    # ── Telegram Bot ──────────────────────────────────────────
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

    # ── M-Pesa Daraja API ────────────────────────────────────
    MPESA_CONSUMER_KEY: str = os.getenv("MPESA_CONSUMER_KEY", "")
    MPESA_CONSUMER_SECRET: str = os.getenv("MPESA_CONSUMER_SECRET", "")
    MPESA_SHORTCODE: str = os.getenv("MPESA_SHORTCODE", "174379")
    MPESA_PASSKEY: str = os.getenv("MPESA_PASSKEY", "")
    MPESA_CALLBACK_URL: str = os.getenv("MPESA_CALLBACK_URL", "")
    MPESA_ENV: str = os.getenv("MPESA_ENV", "sandbox")

    # ── Admin Dashboard ───────────────────────────────────────
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "aego2026")

    # ── Directories ───────────────────────────────────────────
    DATA_DIR: str = os.getenv("DATA_DIR", "/opt/aego/data")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "/opt/aego/output")

    # ── Server ────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "1"))  # 1 worker for Pi 5
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    CORS_ORIGINS: list = field(default_factory=lambda: ["*"])

    # ── Session ───────────────────────────────────────────────
    SESSION_TTL_MINUTES: int = int(os.getenv("SESSION_TTL_MINUTES", "30"))

    # ── Queue ─────────────────────────────────────────────────
    QUEUE_TIMEOUT: int = int(os.getenv("QUEUE_TIMEOUT", "60"))
    QUEUE_MAX_RETRIES: int = int(os.getenv("QUEUE_MAX_RETRIES", "1"))

    # ── Voice Pipeline ────────────────────────────────────────
    VOICE_CONFIG: str = os.getenv("VOICE_CONFIG", str(
        Path(__file__).parent.parent / "voice" / "config.yaml"
    ))

    # ── Skills Paths ──────────────────────────────────────────
    SKILLS_DIR: str = os.getenv("SKILLS_DIR", str(
        Path(__file__).parent.parent / "skills"
    ))
    KIOSK_DIR: str = os.getenv("KIOSK_DIR", str(
        Path(__file__).parent.parent / "kiosk" / "kiosk" / "public"
    ))

    @property
    def mpesa_base_url(self) -> str:
        if self.MPESA_ENV == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        Path(self.DATA_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.DATA_DIR).joinpath("logs").mkdir(parents=True, exist_ok=True)


# Singleton config instance
cfg = Config()
