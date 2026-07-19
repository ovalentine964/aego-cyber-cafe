#!/usr/bin/env python3
"""
CV Generator for Aego Cyber Cafe
Generates professional CVs and cover letters from JSON data.
Supports HTML output and PDF conversion via weasyprint or wkhtmltopdf.

Usage:
    python3 cv-generator.py --data /path/to/data.json --type cv --output /opt/aego/output/
    python3 cv-generator.py --data /path/to/data.json --type cover-letter --output /opt/aego/output/
    python3 cv-generator.py --data /path/to/data.json --type both --output /opt/aego/output/
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/opt/aego/logs/cv-generator.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Directories
SKILL_DIR = Path(__file__).parent
CV_TEMPLATE = SKILL_DIR / "cv-template.html"
COVER_TEMPLATE = SKILL_DIR / "cover-letter-template.html"
DEFAULT_OUTPUT = Path("/opt/aego/output")


def ensure_output_dir(output_dir: Path) -> None:
    """Create output directory if it doesn't exist."""
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory ready: {output_dir}")


def ensure_log_dir() -> None:
    """Create log directory if it doesn't exist."""
    log_dir = Path("/opt/aego/logs")
    log_dir.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Convert a name to a safe filename."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9\s_-]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name[:50]  # Limit length


def load_template(template_path: Path) -> str:
    """Load an HTML template file."""
    if not template_path.exists():
        logger.error(f"Template not found: {template_path}")
        raise FileNotFoundError(f"Template not found: {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def render_mustache(template: str, data: dict, prefix: str = "") -> str:
    """
    Simple Mustache-like template rendering.
    Handles:
      - {{KEY}} — simple variable substitution
      - {{#KEY}}...{{/KEY}} — section rendering (truthy)
      - {{^KEY}}...{{/KEY}} — inverted section (falsy)
      - Nested keys via dot notation
    """
    result = template

    # Handle sections {{#KEY}}...{{/KEY}} and {{^KEY}}...{{/KEY}}
    def get_nested(data, key):
        """Get value from nested dict using dot notation."""
        keys = key.split(".")
        val = data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return None
        return val

    # Process inverted sections {{^KEY}}...{{/KEY}} first
    for match in re.finditer(r"\{\{\^(\w+(?:\.\w+)*)\}\}(.*?)\{\{/\1\}\}", result, re.DOTALL):
        key = match.group(1)
        content = match.group(2)
        val = get_nested(data, prefix + key) if prefix else get_nested(data, key)
        if not val:
            result = result.replace(match.group(0), content)
        else:
            result = result.replace(match.group(0), "")

    # Process regular sections {{#KEY}}...{{/KEY}}
    for match in re.finditer(r"\{\{#(\w+(?:\.\w+)*)\}\}(.*?)\{\{/\1\}\}", result, re.DOTALL):
        key = match.group(1)
        content = match.group(2)
        full_key = prefix + key if prefix else key
        val = get_nested(data, full_key) if prefix else get_nested(data, key)

        if val is None:
            result = result.replace(match.group(0), "")
        elif isinstance(val, list):
            rendered = ""
            for item in val:
                if isinstance(item, dict):
                    rendered += render_mustache(content, item)
                else:
                    rendered += content.replace("{{.}}", str(item))
            result = result.replace(match.group(0), rendered)
        elif isinstance(val, bool) and val:
            result = result.replace(match.group(0), content)
        elif isinstance(val, str) and val:
            result = result.replace(match.group(0), content)
        else:
            result = result.replace(match.group(0), "")

    # Process simple variable substitution {{KEY}}
    for match in re.finditer(r"\{\{(\w+(?:\.\w+)*)\}\}", result):
        key = match.group(1)
        val = get_nested(data, prefix + key) if prefix else get_nested(data, key)
        if val is not None:
            result = result.replace(match.group(0), str(val))
        else:
            result = result.replace(match.group(0), "")

    return result


def prepare_cv_data(raw_data: dict) -> dict:
    """
    Transform raw conversation data into template-ready format.
    Handles various input formats from OpenClaw conversation.
    """
    data = {}

    # Personal Info
    personal = raw_data.get("personal_info", raw_data)
    data["FULL_NAME"] = personal.get("full_name", personal.get("name", ""))
    data["PHONE"] = personal.get("phone", personal.get("phone_number", ""))
    data["EMAIL"] = personal.get("email", "")
    data["LOCATION"] = personal.get("location", personal.get("address", ""))
    data["DATE_OF_BIRTH"] = personal.get("date_of_birth", personal.get("dob", ""))

    # Summary
    data["SUMMARY"] = raw_data.get("summary", raw_data.get("career_objective", raw_data.get("objective", "")))

    # Education
    education = raw_data.get("education", [])
    if education:
        data["EDUCATION"] = True
        entries = []
        for edu in education:
            entries.append({
                "INSTITUTION": edu.get("institution", edu.get("school", "")),
                "QUALIFICATION": edu.get("qualification", edu.get("degree", edu.get("certificate", ""))),
                "YEAR_START": edu.get("year_start", edu.get("from", "")),
                "YEAR_END": edu.get("year_end", edu.get("to", edu.get("year", ""))),
                "GRADE": edu.get("grade", edu.get("marks", "")),
            })
        data["EDUCATION_ENTRIES"] = entries

    # Work Experience
    experience = raw_data.get("experience", raw_data.get("work_experience", []))
    if experience:
        data["EXPERIENCE"] = True
        entries = []
        for exp in experience:
            responsibilities = exp.get("responsibilities", exp.get("duties", []))
            entry = {
                "COMPANY": exp.get("company", exp.get("employer", "")),
                "JOB_TITLE": exp.get("job_title", exp.get("title", exp.get("position", ""))),
                "DURATION_START": exp.get("from", exp.get("duration_start", exp.get("start", ""))),
                "DURATION_END": exp.get("to", exp.get("duration_end", exp.get("end", exp.get("present", "Present")))),
            }
            if responsibilities:
                entry["RESPONSIBILITIES"] = True
                entry["RESPONSIBILITIES_LIST"] = (
                    responsibilities if isinstance(responsibilities, list)
                    else [r.strip() for r in responsibilities.split(",")]
                )
            entries.append(entry)
        data["EXPERIENCE_ENTRIES"] = entries

    # Skills
    skills = raw_data.get("skills", {})
    if skills:
        data["SKILLS"] = True
        if isinstance(skills, dict):
            data["TECHNICAL_SKILLS"] = skills.get("technical", skills.get("technical_skills", ""))
            data["LANGUAGES"] = skills.get("languages", skills.get("spoken_languages", ""))
            data["SOFT_SKILLS"] = skills.get("soft", skills.get("soft_skills", ""))
            data["CERTIFICATIONS"] = skills.get("certifications", skills.get("certificates", ""))
        elif isinstance(skills, list):
            data["TECHNICAL_SKILLS"] = ", ".join(skills)

    # References
    references = raw_data.get("references", [])
    if references:
        data["REFERENCES"] = True
        if references == "available_on_request" or references == ["available_on_request"]:
            data["REFERENCES_AVAILABLE"] = False
        else:
            data["REFERENCES_AVAILABLE"] = True
            ref_list = []
            for ref in references:
                ref_list.append({
                    "NAME": ref.get("name", ""),
                    "TITLE": ref.get("title", ref.get("position", "")),
                    "PHONE": ref.get("phone", ref.get("phone_number", "")),
                    "EMAIL": ref.get("email", ""),
                    "RELATIONSHIP": ref.get("relationship", ref.get("relation", "")),
                })
            data["REFERENCES_LIST"] = ref_list
    else:
        data["REFERENCES"] = True
        data["REFERENCES_AVAILABLE"] = False

    return data


def prepare_cover_letter_data(raw_data: dict) -> dict:
    """Transform raw data into cover letter template format."""
    data = prepare_cv_data(raw_data)

    # Cover letter specific fields
    cover = raw_data.get("cover_letter", raw_data)
    data["DATE"] = datetime.now().strftime("%B %d, %Y")
    data["JOB_TITLE"] = cover.get("job_title", cover.get("position", "[Job Title]"))
    data["COMPANY"] = cover.get("company", cover.get("employer", ""))
    data["COMPANY_ADDRESS"] = cover.get("company_address", cover.get("address", ""))

    # Recipient
    recipient = cover.get("recipient", {})
    if recipient:
        data["RECIPIENT"] = True
        data["RECIPIENT_NAME"] = recipient.get("name", "The Hiring Manager")
        data["RECIPIENT_TITLE"] = recipient.get("title", "")
        data["COMPANY"] = recipient.get("company", data.get("COMPANY", ""))
        data["COMPANY_ADDRESS"] = recipient.get("address", data.get("COMPANY_ADDRESS", ""))

    # Salutation
    salutation = cover.get("salutation", "")
    if not salutation:
        if recipient and recipient.get("name"):
            salutation = f"Mr./Ms. {recipient['name'].split()[-1]}"
        else:
            salutation = "Sir/Madam"
    data["SALUTATION"] = salutation

    # Paragraphs
    data["OPENING_PARAGRAPH"] = cover.get("opening_paragraph",
        "I believe my skills and experience make me an excellent candidate for this role.")

    data["BODY_PARAGRAPH_1"] = cover.get("body_paragraph_1", cover.get("qualifications_paragraph",
        "I possess the qualifications and skills required for this position. "
        "My background has equipped me with strong competencies relevant to this role."))

    data["BODY_PARAGRAPH_2"] = cover.get("body_paragraph_2", cover.get("experience_paragraph",
        "My previous experience has taught me the value of hard work, attention to detail, "
        "and effective communication. I am confident I can make a meaningful contribution to your organization."))

    bp3 = cover.get("body_paragraph_3", cover.get("motivation_paragraph", ""))
    if bp3:
        data["BODY_PARAGRAPH_3"] = bp3

    data["CLOSING_PARAGRAPH"] = cover.get("closing_paragraph",
        "I am eager to bring my dedication and skills to your team and contribute to the continued success of your organization.")

    return data


def render_html(template: str, data: dict) -> str:
    """Render HTML template with data."""
    return render_mustache(template, data)


def convert_to_pdf(html_content: str, output_path: Path) -> bool:
    """
    Convert HTML to PDF. Tries weasyprint first, then wkhtmltopdf.
    Returns True on success, False on failure.
    """
    pdf_path = output_path.with_suffix(".pdf")

    # Try weasyprint
    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(str(pdf_path))
        logger.info(f"PDF generated with weasyprint: {pdf_path}")
        return True
    except ImportError:
        logger.warning("weasyprint not available, trying wkhtmltopdf...")
    except Exception as e:
        logger.warning(f"weasyprint failed: {e}, trying wkhtmltopdf...")

    # Try wkhtmltopdf
    try:
        result = subprocess.run(
            ["wkhtmltopdf", "--quiet", "--page-size", "A4",
             "--margin-top", "15mm", "--margin-bottom", "15mm",
             "--margin-left", "20mm", "--margin-right", "20mm",
             "-", str(pdf_path)],
            input=html_content.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"PDF generated with wkhtmltopdf: {pdf_path}")
            return True
        else:
            logger.error(f"wkhtmltopdf failed: {result.stderr.decode()}")
    except FileNotFoundError:
        logger.error("wkhtmltopdf not found in PATH")
    except Exception as e:
        logger.error(f"wkhtmltopdf error: {e}")

    return False


def generate_cv(data: dict, output_dir: Path) -> dict:
    """Generate CV from data. Returns dict with file paths."""
    ensure_output_dir(output_dir)

    template = load_template(CV_TEMPLATE)
    prepared = prepare_cv_data(data)
    html_content = render_html(template, prepared)

    name = sanitize_filename(prepared.get("FULL_NAME", "customer"))
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cv_{name}_{date_str}"

    # Save HTML
    html_path = output_dir / f"{filename}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"HTML CV saved: {html_path}")

    # Generate PDF
    pdf_path = output_dir / f"{filename}.pdf"
    pdf_success = convert_to_pdf(html_content, html_path)

    result = {
        "html_path": str(html_path),
        "pdf_path": str(pdf_path) if pdf_success else None,
        "customer_name": prepared.get("FULL_NAME", ""),
        "generated_at": datetime.now().isoformat(),
    }

    if not pdf_success:
        logger.warning("PDF generation failed. HTML version available.")
        result["warning"] = "PDF generation failed. HTML version provided."

    return result


def generate_cover_letter(data: dict, output_dir: Path) -> dict:
    """Generate cover letter from data. Returns dict with file paths."""
    ensure_output_dir(output_dir)

    template = load_template(COVER_TEMPLATE)
    prepared = prepare_cover_letter_data(data)
    html_content = render_html(template, prepared)

    name = sanitize_filename(prepared.get("FULL_NAME", "customer"))
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cover_{name}_{date_str}"

    # Save HTML
    html_path = output_dir / f"{filename}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"HTML cover letter saved: {html_path}")

    # Generate PDF
    pdf_path = output_dir / f"{filename}.pdf"
    pdf_success = convert_to_pdf(html_content, html_path)

    result = {
        "html_path": str(html_path),
        "pdf_path": str(pdf_path) if pdf_success else None,
        "customer_name": prepared.get("FULL_NAME", ""),
        "generated_at": datetime.now().isoformat(),
    }

    if not pdf_success:
        logger.warning("PDF generation failed for cover letter. HTML version available.")
        result["warning"] = "PDF generation failed. HTML version provided."

    return result


def main():
    ensure_log_dir()

    parser = argparse.ArgumentParser(
        description="Aego Cyber Cafe — CV & Cover Letter Generator"
    )
    parser.add_argument(
        "--data", required=True,
        help="Path to JSON file with customer data"
    )
    parser.add_argument(
        "--type", choices=["cv", "cover-letter", "both"], default="cv",
        help="Type of document to generate (default: cv)"
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT),
        help=f"Output directory (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--json-output", action="store_true",
        help="Output result as JSON to stdout"
    )

    args = parser.parse_args()

    # Load data
    try:
        with open(args.data, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Data file not found: {args.data}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in data file: {e}")
        sys.exit(1)

    output_dir = Path(args.output)
    results = {}

    try:
        if args.type in ("cv", "both"):
            results["cv"] = generate_cv(data, output_dir)
            logger.info("CV generation complete")

        if args.type in ("cover-letter", "both"):
            results["cover_letter"] = generate_cover_letter(data, output_dir)
            logger.info("Cover letter generation complete")

        if args.json_output:
            print(json.dumps(results, indent=2))
        else:
            for doc_type, result in results.items():
                print(f"\n✅ {doc_type.upper()} generated:")
                print(f"   HTML: {result['html_path']}")
                if result.get("pdf_path"):
                    print(f"   PDF:  {result['pdf_path']}")
                if result.get("warning"):
                    print(f"   ⚠️  {result['warning']}")

    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
