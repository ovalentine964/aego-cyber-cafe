"""
routes/gov.py — Government Services endpoints for Aego Cyber Cafe.

Services: KRA, eCitizen, NHIF, NSSF, NTSA, HELB
Flow: list services → start → fields → validate → generate
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from models import (
    APIResponse,
    GovFieldSubmission,
    GovServiceRequest,
    SessionState,
)
from session_manager import SessionManager

logger = logging.getLogger("aego.routes.gov")
router = APIRouter(prefix="/api/gov", tags=["government"])

# Will be set by main.py
sessions: SessionManager = None  # type: ignore
skills_dir: str = ""
output_dir: str = ""
_catalog: dict | None = None
_form_filler = None


def init(session_mgr: SessionManager, skills_path: str, output_path: str) -> None:
    """Initialize route dependencies."""
    global sessions, skills_dir, output_dir
    sessions = session_mgr
    skills_dir = skills_path
    output_dir = output_path


def _load_catalog() -> dict:
    """Load service-catalog.json (cached)."""
    global _catalog
    if _catalog is None:
        catalog_path = Path(skills_dir) / "gov-services" / "service-catalog.json"
        with open(catalog_path, "r", encoding="utf-8") as f:
            _catalog = json.load(f)
    return _catalog


def _load_form_filler():
    """Load form-filler.py module (cached)."""
    global _form_filler
    if _form_filler is None:
        ff_path = Path(skills_dir) / "gov-services" / "form-filler.py"
        spec = importlib.util.spec_from_file_location("form_filler", str(ff_path))
        _form_filler = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_form_filler)
    return _form_filler


def _get_service(service_key: str, sub_key: str) -> tuple[dict, dict]:
    """Get service definition from catalog. Raises 404 if not found."""
    catalog = _load_catalog()
    services = catalog.get("services", {})

    if service_key not in services:
        raise HTTPException(
            404,
            f"Unknown service: {service_key}. "
            f"Available: {list(services.keys())}"
        )

    service = services[service_key]
    sub_services = service.get("sub_services", {})

    if sub_key not in sub_services:
        raise HTTPException(
            404,
            f"Unknown sub-service: {sub_key}. "
            f"Available: {list(sub_services.keys())}"
        )

    return service, sub_services[sub_key]


@router.get("/services", response_model=APIResponse)
async def list_services() -> APIResponse:
    """List all government services with fees and required fields."""
    catalog = _load_catalog()
    services = catalog.get("services", {})

    result = []
    for key, svc in services.items():
        sub_list = []
        for sub_key, sub in svc.get("sub_services", {}).items():
            sub_list.append({
                "key": sub_key,
                "name": sub.get("name"),
                "name_sw": sub.get("name_sw"),
                "fee": sub.get("fee"),
                "processing_time": sub.get("processing_time"),
                "description": sub.get("description"),
                "description_sw": sub.get("description_sw"),
                "required_documents": sub.get("required_documents", []),
                "fields": [
                    {
                        "name": f["name"],
                        "label": f.get("label"),
                        "type": f.get("type"),
                        "required": f.get("required", False),
                    }
                    for f in sub.get("fields", [])
                ],
            })

        result.append({
            "key": key,
            "name": svc.get("name"),
            "name_sw": svc.get("name_sw"),
            "icon": svc.get("icon"),
            "sub_services": sub_list,
        })

    return APIResponse(
        success=True,
        message="Government services catalog",
        data={"services": result},
    )


@router.post("/{service_type}/start", response_model=APIResponse)
async def start_service(service_type: str, req: GovServiceRequest) -> APIResponse:
    """Begin a government service session."""
    service, sub = _get_service(service_type, req.sub_service)

    session = await sessions.create(service_type=f"gov_{service_type}_{req.sub_service}")
    session.set("service_type", service_type)
    session.set("sub_service", req.sub_service)
    session.set("service_def", sub)
    session.set("fields", {})

    logger.info(f"Gov service started: {session.session_id} ({service_type}/{req.sub_service})")

    return APIResponse(
        success=True,
        message=f"Session started for {sub['name']}. Submit required fields.",
        data={
            "session_id": session.session_id,
            "service": sub["name"],
            "fee": sub.get("fee"),
            "fields": [
                {
                    "name": f["name"],
                    "label": f.get("label"),
                    "type": f.get("type"),
                    "required": f.get("required", False),
                    "pattern": f.get("pattern"),
                    "example": f.get("example"),
                    "options": f.get("options"),
                }
                for f in sub.get("fields", [])
            ],
            "next_step": "fields",
        },
    )


@router.post("/{session_id}/fields", response_model=APIResponse)
async def submit_fields(session_id: str, submission: GovFieldSubmission) -> APIResponse:
    """Submit required fields for a government service."""
    session = await _get_session(session_id)
    stored_fields = session.get("fields", {})
    stored_fields.update(submission.fields)
    session.set("fields", stored_fields)

    service_def = session.get("service_def", {})
    required = [f["name"] for f in service_def.get("fields", []) if f.get("required")]
    submitted = list(stored_fields.keys())
    missing = [f for f in required if f not in stored_fields or not stored_fields[f]]

    return APIResponse(
        success=True,
        message=f"Fields submitted. {len(missing)} required fields remaining.",
        data={
            "submitted": submitted,
            "missing_required": missing,
            "all_required_filled": len(missing) == 0,
            "next_step": "validate" if not missing else "fields",
        },
    )


@router.post("/{session_id}/validate", response_model=APIResponse)
async def validate_fields(session_id: str) -> APIResponse:
    """Validate all submitted fields against service requirements."""
    session = await _get_session(session_id)
    service_def = session.get("service_def", {})
    fields = session.get("fields", {})

    ff = _load_form_filler()
    errors = ff.validate_all_fields(service_def, fields)

    if errors:
        return APIResponse(
            success=False,
            message="Validation errors found.",
            data={
                "valid": False,
                "errors": errors,
                "next_step": "fields",
            },
        )

    return APIResponse(
        success=True,
        message="All fields are valid! Ready to generate.",
        data={
            "valid": True,
            "next_step": "generate",
        },
    )


@router.post("/{session_id}/generate", response_model=APIResponse)
async def generate_form(session_id: str) -> APIResponse:
    """Generate the filled government form."""
    session = await _get_session(session_id)
    await sessions.update_state(session_id, SessionState.PROCESSING)

    service_type = session.get("service_type", "")
    sub_service = session.get("sub_service", "")
    service_def = session.get("service_def", {})
    fields = session.get("fields", {})

    # Validate first
    ff = _load_form_filler()
    errors = ff.validate_all_fields(service_def, fields)
    if errors:
        await sessions.update_state(session_id, SessionState.COLLECTING)
        raise HTTPException(400, f"Validation errors: {errors}")

    try:
        catalog = _load_catalog()
        service_info = catalog["services"].get(service_type, {})

        # Generate HTML form
        html_content = ff.generate_filled_form_html(service_def, service_info, fields)

        # Save HTML
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        import re as _re
        name = _re.sub(r"[^a-z0-9_]", "", fields.get("full_name", "customer").lower().replace(" ", "_"))
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{service_type}_{sub_service}_{name}_{date_str}"

        html_path = output / f"{filename}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        result = {
            "html_path": str(html_path),
            "fee": service_def.get("fee"),
            "processing_time": service_def.get("processing_time"),
        }

        # Try PDF
        try:
            from weasyprint import HTML
            pdf_path = output / f"{filename}.pdf"
            HTML(string=html_content).write_pdf(str(pdf_path))
            result["pdf_path"] = str(pdf_path)
        except Exception:
            pass  # HTML is still available

        # Generate steps guide
        guide = ff.generate_steps_guide(service_def)
        guide_path = output / f"{filename}_guide.txt"
        with open(guide_path, "w", encoding="utf-8") as f:
            f.write(guide)
        result["guide_path"] = str(guide_path)

        session.set("output_files", result)
        await sessions.update_state(session_id, SessionState.COMPLETED)

        return APIResponse(
            success=True,
            message=f"Form generated for {service_def.get('name', service_type)}!",
            data={
                "session_id": session_id,
                "files": result,
                "fee": service_def.get("fee"),
            },
        )

    except Exception as e:
        logger.error(f"Form generation failed: {e}", exc_info=True)
        await sessions.update_state(session_id, SessionState.COLLECTING)
        raise HTTPException(500, f"Form generation failed: {e}")


# ── Helpers ───────────────────────────────────────────────────

async def _get_session(session_id: str):
    """Get session or raise 404."""
    session = await sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found or expired.")
    return session
