import os
from flask import Blueprint, request, jsonify

from utils import rag, llm
from core.config import UPLOAD_DIR, RESULT_DIR

advisory_bp = Blueprint("advisory", __name__)


@advisory_bp.route("/api/treatment-advisory", methods=["POST"])
def api_treatment_advisory():
    """Automated Treatment Advisory (Upgrade 2).

    Combines the ONNX scan measurements with any uploaded hospital
    protocol / guideline PDFs (via the existing RAG index) and the scan
    image itself, and asks Qwen 3.6-27B to draft a structured note for
    the doctor. The doctor remains the final decision maker.
    """
    data = request.get_json(force=True) or {}
    uid = data.get("uid")
    analysis = data.get("analysis")
    patient = data.get("patient") or {}

    if not uid or not analysis:
        return jsonify({"error": "uid and analysis data are required"}), 400

    cls = analysis.get("classification") or {}
    if not cls.get("is_tumor"):
        return jsonify({"error": "No tumor was detected on this scan — no treatment advisory needed."}), 400

    matches = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(uid)]
    if not matches:
        return jsonify({"error": "Original scan not found for this uid — please re-analyze first."}), 404
    image_path = os.path.join(UPLOAD_DIR, matches[0])

    # Prefer the overlay (shows detected/segmented tumor) if available.
    overlay_path = None
    overlay_url = analysis.get("overlay_image")
    if overlay_url:
        candidate = os.path.join(RESULT_DIR, os.path.basename(overlay_url))
        if os.path.exists(candidate):
            overlay_path = candidate
    image_for_llm = overlay_path or image_path

    # Build a plain-text measurements summary for the prompt.
    label = cls.get("label", "unknown")
    conf = cls.get("confidence")
    lines = [f"Classification: {label} (confidence {conf * 100:.1f}%)" if conf is not None else f"Classification: {label}"]
    seg = analysis.get("segmentation") or {}
    img_size = seg.get("image_size") or {}
    img_w, img_h = img_size.get("width"), img_size.get("height")
    for s in seg.get("segments", []):
        loc_txt = ""
        if img_w and img_h and s.get("box"):
            bx1, by1, bx2, by2 = s["box"]
            cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
            h_third = "left side" if cx < img_w / 3 else ("right side" if cx > 2 * img_w / 3 else "horizontal center")
            v_third = "upper part" if cy < img_h / 3 else ("lower part" if cy > 2 * img_h / 3 else "vertical middle")
            loc_txt = f", positioned in the {v_third}, {h_third} of this image"
        lines.append(
            f"- {s['label']} region: area {s['area_pct']}% of scan ({s['area_px']:,}px), "
            f"segmentation confidence {s['confidence'] * 100:.1f}%{loc_txt}"
        )
    lines.append(
        "Note: only ONE 2D image is provided (a single slice from the uploaded scan). "
        "No sagittal/coronal views or other slices are available — do not reference them."
    )
    measurements_text = "\n".join(lines)

    # RAG retrieval — search uploaded guideline PDFs for this tumor type.
    guideline_chunks = rag.retrieve(f"{label} tumor treatment protocol guidelines", top_k=4)

    patient_context = ", ".join(f"{k}: {v}" for k, v in patient.items() if v) or None

    try:
        note = llm.treatment_advisory(image_for_llm, measurements_text, guideline_chunks, patient_context)
        powered_by = "qwen3.6-27b"
    except Exception as e:
        return jsonify({"error": f"Treatment advisory generation failed: {e}"}), 502

    return jsonify({
        "note": note,
        "guideline_sources": [{"source": c["source"], "page": c["page"]} for c in guideline_chunks],
        "powered_by": powered_by,
    })
