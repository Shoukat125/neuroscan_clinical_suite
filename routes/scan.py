from flask import Blueprint, render_template, request, jsonify, url_for

from utils import inference
from core.analysis import run_full_analysis, _save_upload, total_tumor_area_pct

scan_bp = Blueprint("scan", __name__)


@scan_bp.route("/")
def index():
    return render_template("index.html")


@scan_bp.route("/api/model-info")
def api_model_info():
    info = {
        "classifier": inference.model_info(inference.CLASSIFIER_PATH),
        "detector": inference.model_info(inference.DETECT_PATH),
        "segmenter": inference.model_info(inference.SEG_PATH),
    }
    return jsonify(info)


@scan_bp.route("/api/analyze", methods=["POST"])
def api_analyze():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    uid, saved_path, saved_name = _save_upload(file)
    result = run_full_analysis(saved_path, uid)
    if result is None:
        return jsonify({"error": "Could not read image file"}), 400

    result["uploaded_image"] = url_for("static", filename=f"uploads/{saved_name}")
    result.pop("overlay_path", None)  # internal filesystem path, not for the client
    result["uid"] = uid
    return jsonify(result)


@scan_bp.route("/api/compare", methods=["POST"])
def api_compare():
    """Longitudinal analysis: compare an older MRI scan against a newer one
    for the same patient and report tumor area growth/shrinkage."""
    if "old_image" not in request.files or "new_image" not in request.files:
        return jsonify({"error": "Both old_image and new_image files are required"}), 400

    old_file = request.files["old_image"]
    new_file = request.files["new_image"]
    if old_file.filename == "" or new_file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    old_uid, old_path, old_name = _save_upload(old_file)
    new_uid, new_path, new_name = _save_upload(new_file)

    old_result = run_full_analysis(old_path, old_uid)
    new_result = run_full_analysis(new_path, new_uid)
    if old_result is None or new_result is None:
        return jsonify({"error": "Could not read one of the image files"}), 400

    for r in (old_result, new_result):
        r.pop("overlay_path", None)

    old_area = total_tumor_area_pct(old_result)
    new_area = total_tumor_area_pct(new_result)
    point_change = round(new_area - old_area, 3)
    if old_area > 0:
        percent_change = round((new_area - old_area) / old_area * 100, 1)
    else:
        percent_change = None  # no baseline tumor area to compare against

    if not old_result["classification"]["is_tumor"] and not new_result["classification"]["is_tumor"]:
        verdict = "no_tumor"
    elif abs(point_change) < 0.5:
        verdict = "stable"
    elif point_change > 0:
        verdict = "growing"
    else:
        verdict = "shrinking"

    return jsonify({
        "old": {
            **old_result,
            "uploaded_image": url_for("static", filename=f"uploads/{old_name}"),
            "area_pct": old_area,
        },
        "new": {
            **new_result,
            "uploaded_image": url_for("static", filename=f"uploads/{new_name}"),
            "area_pct": new_area,
        },
        "comparison": {
            "old_area_pct": old_area,
            "new_area_pct": new_area,
            "point_change_pct": point_change,
            "percent_change": percent_change,
            "verdict": verdict,
        },
    })
