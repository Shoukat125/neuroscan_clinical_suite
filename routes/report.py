import io
import os
from flask import Blueprint, request, jsonify, send_file

from utils import report
from core.config import UPLOAD_DIR, RESULT_DIR

report_bp = Blueprint("report", __name__)


@report_bp.route("/api/report/pdf", methods=["POST"])
def api_report_pdf():
    """Official PDF clinical report export (Upgrade 5)."""
    data = request.get_json(force=True) or {}
    uid = data.get("uid")
    analysis = data.get("analysis")
    patient = data.get("patient") or {}
    notes = data.get("notes")

    if not uid or not analysis:
        return jsonify({"error": "uid and analysis data are required"}), 400

    matches = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(uid)]
    image_path = os.path.join(UPLOAD_DIR, matches[0]) if matches else None

    overlay_path = None
    overlay_url = analysis.get("overlay_image")
    if overlay_url:
        overlay_name = os.path.basename(overlay_url)
        candidate = os.path.join(RESULT_DIR, overlay_name)
        if os.path.exists(candidate):
            overlay_path = candidate

    pdf_bytes = report.generate_pdf_report(
        patient=patient, analysis=analysis,
        image_path=image_path, overlay_path=overlay_path, notes=notes,
    )

    patient_name = (patient.get("name") or "patient").strip().replace(" ", "_") or "patient"
    filename = f"neuroscan_report_{patient_name}_{uid}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
