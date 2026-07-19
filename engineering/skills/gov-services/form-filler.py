#!/usr/bin/env python3
"""
Government Services Form Filler for Aego Cyber Cafe
Fills government form templates with customer data and generates printable forms.

Usage:
    python3 form-filler.py --service kra --sub pin_registration --data /path/to/data.json --output /opt/aego/output/
    python3 form-filler.py --list-services
    python3 form-filler.py --list-fields kra pin_registration
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/opt/aego/logs/form-filler.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

SKILL_DIR = Path(__file__).parent
CATALOG_PATH = SKILL_DIR / "service-catalog.json"
DEFAULT_OUTPUT = Path("/opt/aego/output")


def load_catalog() -> dict:
    """Load the service catalog."""
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_service(catalog: dict, service_key: str, sub_key: str) -> dict:
    """Get a specific service definition."""
    services = catalog.get("services", {})
    if service_key not in services:
        raise ValueError(f"Unknown service: {service_key}. Available: {list(services.keys())}")

    service = services[service_key]
    sub_services = service.get("sub_services", {})
    if sub_key not in sub_services:
        raise ValueError(f"Unknown sub-service: {sub_key}. Available: {list(sub_services.keys())}")

    return sub_services[sub_key]


def validate_field(field_def: dict, value: str) -> tuple[bool, str]:
    """
    Validate a field value against its definition.
    Returns (is_valid, error_message).
    """
    if not value and field_def.get("required"):
        return False, f"{field_def['label']} is required"

    if not value:
        return True, ""

    pattern = field_def.get("pattern")
    if pattern:
        if not re.match(pattern, str(value)):
            example = field_def.get("example", "")
            return False, f"{field_def['label']}: invalid format. Example: {example}"

    field_type = field_def.get("type")
    if field_type == "number":
        try:
            float(value)
        except ValueError:
            return False, f"{field_def['label']}: must be a number"

    return True, ""


def validate_all_fields(service: dict, data: dict) -> list[str]:
    """Validate all fields for a service. Returns list of error messages."""
    errors = []
    for field_def in service.get("fields", []):
        value = data.get(field_def["name"], "")
        is_valid, error_msg = validate_field(field_def, value)
        if not is_valid:
            errors.append(error_msg)
    return errors


def generate_filled_form_html(service: dict, service_info: dict, data: dict) -> str:
    """Generate a filled form as HTML for printing."""

    service_name = service.get("name", "Government Service")
    service_name_sw = service.get("name_sw", service_name)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build field rows
    field_rows = ""
    for field_def in service.get("fields", []):
        name = field_def["name"]
        label = field_def.get("label", name)
        label_sw = field_def.get("label_sw", "")
        value = data.get(name, "")
        sensitive = field_def.get("sensitive", False)

        # Mask sensitive fields
        display_value = value
        if sensitive and value:
            display_value = "••••••••"

        display_label = f"{label}"
        if label_sw:
            display_label += f" ({label_sw})"

        field_rows += f"""
        <tr>
            <td class="field-label">{display_label}</td>
            <td class="field-value">{display_value}</td>
        </tr>"""

    # Build steps section
    steps = service.get("steps", [])
    steps_sw = service.get("steps_sw", [])
    steps_html = ""
    if steps:
        steps_html = "<h3>📋 Next Steps / Hatua Zifuatazo</h3><ol>"
        for i, step in enumerate(steps):
            step_sw = steps_sw[i] if i < len(steps_sw) else ""
            steps_html += f"<li>{step}"
            if step_sw:
                steps_html += f"<br><em style='color:#666;'>{step_sw}</em>"
            steps_html += "</li>"
        steps_html += "</ol>"

    # Required documents
    docs = service.get("required_documents", [])
    docs_sw = service.get("required_documents_sw", [])
    docs_html = ""
    if docs:
        docs_html = "<h3>📄 Required Documents / Nyaraka Zinazohitajika</h3><ul>"
        for i, doc in enumerate(docs):
            doc_sw = docs_sw[i] if i < len(docs_sw) else ""
            docs_html += f"<li>{doc}"
            if doc_sw:
                docs_html += f"<br><em style='color:#666;'>{doc_sw}</em>"
            docs_html += "</li>"
        docs_html += "</ul>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{service_name} - Aego Cyber Cafe</title>
    <style>
        @page {{ size: A4; margin: 15mm; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            background: #fff;
        }}
        .form-container {{
            max-width: 210mm;
            margin: 0 auto;
            padding: 20px 30px;
        }}
        .header {{
            text-align: center;
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            font-size: 18pt;
            color: #2c3e50;
            margin-bottom: 5px;
        }}
        .header .subtitle {{
            font-size: 10pt;
            color: #666;
        }}
        .header .logo-text {{
            font-size: 24pt;
            font-weight: 700;
            color: #3498db;
            margin-bottom: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        .field-label {{
            font-weight: 600;
            padding: 8px 12px;
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            width: 40%;
            vertical-align: top;
        }}
        .field-value {{
            padding: 8px 12px;
            border: 1px solid #dee2e6;
            width: 60%;
        }}
        h3 {{
            font-size: 12pt;
            color: #2c3e50;
            margin: 15px 0 10px 0;
            border-bottom: 1px solid #eee;
            padding-bottom: 5px;
        }}
        ol, ul {{
            padding-left: 25px;
            margin-bottom: 15px;
        }}
        li {{
            margin-bottom: 8px;
            font-size: 10.5pt;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 15px;
            border-top: 2px solid #eee;
            font-size: 9pt;
            color: #888;
            text-align: center;
        }}
        .fee-box {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 10px 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            text-align: center;
        }}
        .fee-box .amount {{
            font-size: 16pt;
            font-weight: 700;
            color: #856404;
        }}
        .stamp-area {{
            margin-top: 30px;
            display: flex;
            justify-content: space-between;
        }}
        .stamp-box {{
            border: 1px dashed #ccc;
            padding: 15px;
            width: 45%;
            min-height: 80px;
            text-align: center;
            color: #999;
            font-size: 9pt;
        }}
        @media print {{
            .form-container {{ padding: 0; }}
        }}
    </style>
</head>
<body>
    <div class="form-container">
        <div class="header">
            <div class="logo-text">🅰️ AEGO CYBER CAFE</div>
            <div class="subtitle">Nyatike, Migori County | 📞 07XX XXX XXX</div>
            <h1>{service_name}</h1>
            <div class="subtitle">{service_name_sw}</div>
        </div>

        <div class="fee-box">
            Service Fee / Ada ya Huduma: <span class="amount">KES {service.get('fee', 'N/A')}</span><br>
            <small>Processing Time / Muda wa Usindikaji: {service.get('processing_time', 'N/A')}</small>
        </div>

        <table>
            {field_rows}
        </table>

        {docs_html}
        {steps_html}

        <div class="stamp-area">
            <div class="stamp-box">
                Customer Signature / Saini ya Mteja<br><br><br>
                Date: _______________
            </div>
            <div class="stamp-box">
                Agent Signature / Saini ya Wakala<br><br><br>
                Date: {timestamp}
            </div>
        </div>

        <div class="footer">
            <p>Generated by Aego Cyber Cafe | {timestamp}</p>
            <p>This form was filled with customer-provided information. Please verify all details before submission.</p>
            <p>Fomu hii imejazwa na maelezo yaliyotolewa na mteja. Tafadhali thibitisha maelezo yote kabla ya kuwasilisha.</p>
        </div>
    </div>
</body>
</html>"""

    return html


def generate_steps_guide(service: dict, language: str = "en") -> str:
    """Generate a text-based step-by-step guide for the service."""
    service_name = service.get("name", "Service")
    steps = service.get("steps", []) if language == "en" else service.get("steps_sw", service.get("steps", []))

    guide = f"=== {service_name} ===\n\n"
    guide += f"Fee: KES {service.get('fee', 'N/A')}\n"
    guide += f"Processing Time: {service.get('processing_time', 'N/A')}\n\n"

    if steps:
        guide += "Steps:\n"
        for i, step in enumerate(steps, 1):
            guide += f"  {i}. {step}\n"

    return guide


def list_services(catalog: dict) -> None:
    """Print all available services."""
    print("\n=== Aego Cyber Cafe — Government Services ===\n")
    for key, service in catalog["services"].items():
        print(f"  {service['icon']} {key}: {service['name']}")
        for sub_key, sub in service.get("sub_services", {}).items():
            print(f"      └─ {sub_key}: {sub['name']} (KES {sub['fee']})")
        print()


def list_fields(catalog: dict, service_key: str, sub_key: str) -> None:
    """Print all fields for a service."""
    service = get_service(catalog, service_key, sub_key)
    print(f"\n=== Fields for {service['name']} ===\n")
    print(f"Fee: KES {service['fee']}")
    print(f"Processing Time: {service['processing_time']}\n")

    for field in service.get("fields", []):
        required = "✓ Required" if field.get("required") else "○ Optional"
        pattern = f" (pattern: {field['pattern']})" if field.get("pattern") else ""
        example = f" (e.g., {field['example']})" if field.get("example") else ""
        print(f"  {required} | {field['label']} ({field['name']}){pattern}{example}")


def ensure_output_dir(output_dir: Path) -> None:
    """Create output directory if it doesn't exist."""
    output_dir.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Aego Cyber Cafe — Government Services Form Filler"
    )
    parser.add_argument("--service", help="Service key (e.g., kra, ecitizen, nhif)")
    parser.add_argument("--sub", help="Sub-service key (e.g., pin_registration)")
    parser.add_argument("--data", help="Path to JSON file with customer data")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory")
    parser.add_argument("--list-services", action="store_true", help="List all services")
    parser.add_argument("--list-fields", nargs=2, metavar=("SERVICE", "SUB"), help="List fields for a service")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't generate form")
    parser.add_argument("--json-output", action="store_true", help="Output result as JSON")
    parser.add_argument("--language", choices=["en", "sw"], default="en", help="Language for steps guide")

    args = parser.parse_args()

    # Ensure log directory
    log_dir = Path("/opt/aego/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    catalog = load_catalog()

    if args.list_services:
        list_services(catalog)
        return

    if args.list_fields:
        list_fields(catalog, args.list_fields[0], args.list_fields[1])
        return

    if not args.service or not args.sub or not args.data:
        parser.error("--service, --sub, and --data are required (or use --list-services)")

    # Load customer data
    try:
        with open(args.data, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Data file not found: {args.data}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        sys.exit(1)

    # Get service definition
    try:
        service = get_service(catalog, args.service, args.sub)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    service_info = catalog["services"][args.service]

    # Validate
    errors = validate_all_fields(service, data)
    if errors:
        print("❌ Validation errors:", file=sys.stderr)
        for err in errors:
            print(f"   • {err}", file=sys.stderr)
        if args.validate_only or not args.json_output:
            sys.exit(1)

    if args.validate_only and not errors:
        print("✅ All fields are valid!")
        return

    # Generate form
    output_dir = Path(args.output)
    ensure_output_dir(output_dir)

    html_content = generate_filled_form_html(service, service_info, data)

    name = re.sub(r"[^a-z0-9_]", "", data.get("full_name", "customer").lower().replace(" ", "_"))
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{args.service}_{args.sub}_{name}_{date_str}"

    html_path = output_dir / f"{filename}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"Form saved: {html_path}")

    # Try PDF conversion
    pdf_path = output_dir / f"{filename}.pdf"
    pdf_success = False

    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(str(pdf_path))
        pdf_success = True
        logger.info(f"PDF saved: {pdf_path}")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"weasyprint failed: {e}")

    if not pdf_success:
        try:
            import subprocess
            result = subprocess.run(
                ["wkhtmltopdf", "--quiet", "--page-size", "A4", "-", str(pdf_path)],
                input=html_content.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0:
                pdf_success = True
                logger.info(f"PDF saved: {pdf_path}")
        except Exception:
            pass

    # Generate steps guide
    steps_guide = generate_steps_guide(service, args.language)
    guide_path = output_dir / f"{filename}_guide.txt"
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(steps_guide)

    result = {
        "service": args.service,
        "sub_service": args.sub,
        "html_path": str(html_path),
        "pdf_path": str(pdf_path) if pdf_success else None,
        "guide_path": str(guide_path),
        "fee": service.get("fee"),
        "processing_time": service.get("processing_time"),
        "generated_at": datetime.now().isoformat(),
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n✅ Form generated for {service['name']}:")
        print(f"   HTML: {html_path}")
        if pdf_success:
            print(f"   PDF:  {pdf_path}")
        print(f"   Guide: {guide_path}")
        print(f"   Fee: KES {service.get('fee')}")


if __name__ == "__main__":
    main()
