"""
routes/cv.py — CV Writing endpoints for Aego Cyber Cafe.

Flow: start → personal → education → experience → skills → generate → download
Each endpoint validates input and stores data in session.
Auto-purges after 30 minutes.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from models import (
    APIResponse,
    CVStartRequest,
    CVSession,
    Education,
    PersonalInfo,
    SessionState,
    Skills,
    WorkExperience,
)
from session_manager import SessionManager

logger = logging.getLogger("aego.routes.cv")
router = APIRouter(prefix="/api/cv", tags=["cv"])

# Will be set by main.py during startup
sessions: SessionManager = None  # type: ignore
skills_dir: str = ""
output_dir: str = ""


def init(session_mgr: SessionManager, skills_path: str, output_path: str) -> None:
    """Initialize route dependencies."""
    global sessions, skills_dir, output_dir
    sessions = session_mgr
    skills_dir = skills_path
    output_dir = output_path


@router.post("/start", response_model=APIResponse)
async def start_cv_session(req: CVStartRequest) -> APIResponse:
    """Begin a new CV writing session. Returns session_id."""
    session = await sessions.create(service_type=f"cv_{req.service_type.value}")
    session.set("cv_data", {
        "service_type": req.service_type.value,
        "language": req.language,
    })

    logger.info(f"CV session started: {session.session_id}")
    return APIResponse(
        success=True,
        message="CV session started. Provide your personal info next.",
        data={
            "session_id": session.session_id,
            "service_type": req.service_type.value,
            "next_step": "personal",
        },
    )


@router.post("/{session_id}/personal", response_model=APIResponse)
async def add_personal_info(session_id: str, info: PersonalInfo) -> APIResponse:
    """Add personal information to CV session."""
    session = await _get_session(session_id)
    cv_data = session.get("cv_data", {})
    cv_data["personal_info"] = info.model_dump()
    session.set("cv_data", cv_data)
    await sessions.update_state(session_id, SessionState.COLLECTING)

    return APIResponse(
        success=True,
        message=f"Personal info saved for {info.full_name}. Next: education.",
        data={"next_step": "education"},
    )


@router.post("/{session_id}/education", response_model=APIResponse)
async def add_education(session_id: str, edu: Education) -> APIResponse:
    """Add education entry to CV session."""
    session = await _get_session(session_id)
    cv_data = session.get("cv_data", {})
    edu_list = cv_data.get("education", [])
    edu_list.append(edu.model_dump())
    cv_data["education"] = edu_list
    session.set("cv_data", cv_data)

    return APIResponse(
        success=True,
        message=f"Education added: {edu.institution}. Add more or proceed to experience.",
        data={
            "education_count": len(edu_list),
            "next_step": "experience",
        },
    )


@router.post("/{session_id}/experience", response_model=APIResponse)
async def add_experience(session_id: str, exp: WorkExperience) -> APIResponse:
    """Add work experience entry to CV session."""
    session = await _get_session(session_id)
    cv_data = session.get("cv_data", {})
    exp_list = cv_data.get("experience", [])
    exp_list.append(exp.model_dump())
    cv_data["experience"] = exp_list
    session.set("cv_data", cv_data)

    return APIResponse(
        success=True,
        message=f"Experience added: {exp.job_title} at {exp.company}. Add more or proceed to skills.",
        data={
            "experience_count": len(exp_list),
            "next_step": "skills",
        },
    )


@router.post("/{session_id}/skills", response_model=APIResponse)
async def add_skills(session_id: str, skills: Skills) -> APIResponse:
    """Add skills to CV session."""
    session = await _get_session(session_id)
    cv_data = session.get("cv_data", {})
    cv_data["skills"] = skills.model_dump()
    session.set("cv_data", cv_data)

    return APIResponse(
        success=True,
        message="Skills saved. Ready to generate your CV!",
        data={"next_step": "generate"},
    )


@router.post("/{session_id}/generate", response_model=APIResponse)
async def generate_cv(session_id: str) -> APIResponse:
    """Generate CV PDF from collected data."""
    session = await _get_session(session_id)
    await sessions.update_state(session_id, SessionState.PROCESSING)

    cv_data = session.get("cv_data", {})
    if not cv_data.get("personal_info"):
        raise HTTPException(400, "Personal info is required before generating CV.")

    try:
        # Import and use the existing cv-generator module
        cv_gen_path = Path(skills_dir) / "cv-writer"
        if str(cv_gen_path) not in sys.path:
            sys.path.insert(0, str(cv_gen_path))

        # Use the generator functions directly
        result = _run_cv_generator(cv_data, session)

        session.set("output_files", result)
        await sessions.update_state(session_id, SessionState.COMPLETED)

        return APIResponse(
            success=True,
            message="CV generated successfully!",
            data={
                "session_id": session_id,
                "files": result,
                "download_url": f"/api/cv/{session_id}/download",
            },
        )
    except Exception as e:
        logger.error(f"CV generation failed: {e}", exc_info=True)
        await sessions.update_state(session_id, SessionState.COLLECTING)
        raise HTTPException(500, f"CV generation failed: {e}")


@router.get("/{session_id}/download")
async def download_cv(session_id: str) -> FileResponse:
    """Download the generated CV file."""
    session = await _get_session(session_id)
    files = session.get("output_files", {})

    pdf_path = files.get("pdf_path")
    html_path = files.get("html_path")

    # Prefer PDF, fall back to HTML
    file_path = pdf_path or html_path
    if not file_path or not Path(file_path).exists():
        raise HTTPException(404, "No generated CV found. Generate first.")

    media_type = "application/pdf" if file_path.endswith(".pdf") else "text/html"
    filename = Path(file_path).name

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )


# ── Helpers ───────────────────────────────────────────────────

async def _get_session(session_id: str):
    """Get session or raise 404."""
    session = await sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found or expired.")
    return session


def _run_cv_generator(cv_data: dict, session) -> dict:
    """
    Run the CV generator from skills/cv-writer/cv-generator.py.
    Imports and calls the generator functions directly (no subprocess).
    """
    import importlib.util

    cv_gen_path = Path(skills_dir) / "cv-writer" / "cv-generator.py"
    spec = importlib.util.spec_from_file_location("cv_generator", str(cv_gen_path))
    cv_gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cv_gen)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    service_type = session.get("cv_data", {}).get("service_type", "cv")
    result = {}

    if service_type in ("cv", "both"):
        result = cv_gen.generate_cv(cv_data, output)

    if service_type in ("cover_letter", "both"):
        cl_result = cv_gen.generate_cover_letter(cv_data, output)
        result.update(cl_result)

    return result
