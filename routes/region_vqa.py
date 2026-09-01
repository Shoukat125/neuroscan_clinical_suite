import os
import uuid
import cv2
from flask import Blueprint, request, jsonify, url_for

from utils import inference, llm
from core.config import UPLOAD_DIR, RESULT_DIR

vqa_bp = Blueprint("vqa", __name__)


@vqa_bp.route("/api/region-vqa", methods=["POST"])
def api_region_vqa():
    """Interactive region crop Q&A (Upgrade 4) — now powered by Qwen 3.6-27B."""
    data = request.get_json(force=True) or {}
    uid = data.get("uid")
    box = data.get("box")  # [x1, y1, x2, y2] in ORIGINAL image pixel coords
    question = (data.get("question") or "").strip()
    known_classification = data.get("known_classification")  # e.g. "glioma" — helps the model ignore typos in the question

    if not uid or not box or len(box) != 4:
        return jsonify({"error": "uid and a 4-value box [x1,y1,x2,y2] are required"}), 400
    if not question:
        return jsonify({"error": "Question is empty"}), 400

    # Find the originally uploaded file for this uid (any extension).
    matches = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(uid)]
    if not matches:
        return jsonify({"error": "Original scan not found for this uid — please re-analyze first."}), 404
    saved_path = os.path.join(UPLOAD_DIR, matches[0])

    image = cv2.imread(saved_path)
    if image is None:
        return jsonify({"error": "Could not read the original scan"}), 400

    h, w = image.shape[:2]
    x1, y1, x2, y2 = box
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    if x2 <= x1 or y2 <= y1:
        return jsonify({"error": "Selected region is empty — draw a larger box"}), 400

    crop = image[y1:y2, x1:x2]
    crop_name = f"{uid}_crop_{uuid.uuid4().hex[:6]}.png"
    crop_path = os.path.join(RESULT_DIR, crop_name)
    cv2.imwrite(crop_path, crop)

    # Local, model-free stats — sent to the LLM as grounding, and returned
    # to the client regardless of whether the LLM call succeeds.
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    mean_intensity = round(float(gray.mean()), 1)
    std_intensity = round(float(gray.std()), 1)
    region_area_pct = round(100 * crop.shape[0] * crop.shape[1] / (h * w), 2)

    overlap_pct = None
    actual_size_summary = None
    seg = inference.segment_tumor(image)
    if seg["segments"]:
        crop_px = (x2 - x1) * (y2 - y1)
        per_segment = []  # (label, area_pct, area_px, overlap_px_in_crop)
        total_mask_px_in_crop = 0
        for s in seg["segments"]:
            mask_crop = s["mask"][y1:y2, x1:x2]
            ov_px = int(mask_crop.sum())
            total_mask_px_in_crop += ov_px
            per_segment.append((s["label"], s["area_pct"], s["area_px"], ov_px))
        overlap_pct = round(100 * total_mask_px_in_crop / crop_px, 1) if crop_px else 0.0

        # IMPORTANT: different segments can carry DIFFERENT labels (e.g. a
        # glioma region and a separate meningioma region both detected in
        # the same scan). Summing their areas together and calling it "the
        # full tumor" is clinically wrong — they are not one tumor. Instead,
        # identify which specific labeled region the doctor's crop actually
        # overlaps, and report that region's own (real, whole-region) size.
        overlapping = [p for p in per_segment if p[3] > 0]
        if overlapping:
            best_label, best_pct, best_px, _ = max(overlapping, key=lambda p: p[3])
            if len(overlapping) > 1:
                actual_size_summary = (
                    f"your selection overlaps more than one detected region — "
                    f"most overlap is with the {best_label} region: {best_pct}% of "
                    f"scan area ({best_px:,} pixels), as measured by the segmentation "
                    f"model across that whole region (not just your crop box)"
                )
            else:
                actual_size_summary = (
                    f"the {best_label} region you selected measures {best_pct}% of "
                    f"scan area ({best_px:,} pixels), as measured by the segmentation "
                    f"model across the whole region (not just your crop box)"
                )
        else:
            # Crop doesn't overlap any segmented region — give context about
            # what WAS detected elsewhere, without implying it's inside the crop.
            others = ", ".join(f"{lbl} {pct}%" for lbl, pct, _, _ in [(l, p, x, o) for l, p, x, o in per_segment])
            actual_size_summary = (
                f"your selection does not overlap any segmented tumor region. "
                f"Detected region(s) elsewhere in this scan: {others}"
            )

    stats = {
        "mean_intensity": mean_intensity,
        "std_intensity": std_intensity,
        "region_area_pct": region_area_pct,
        "tumor_overlap_pct": overlap_pct,
    }
    stats_summary = (
        f"selected crop size {x2 - x1}x{y2 - y1}px ({region_area_pct}% of scan — this is just the "
        f"doctor's manual selection box, NOT the tumor's real size), "
        f"mean intensity {mean_intensity} (std {std_intensity}), "
        f"tumor mask overlap within this crop {overlap_pct if overlap_pct is not None else 'n/a'}%"
    )

    try:
        answer = llm.vision_answer(
            crop_path, question, supporting_stats=stats_summary,
            known_classification=known_classification,
            actual_tumor_size=actual_size_summary,
        )
        powered_by = "qwen3.6-27b"
    except Exception as e:
        # Keep the feature usable (e.g. missing/invalid API key, network
        # issue, rate limit) by falling back to the stats-only summary
        # instead of a hard failure — important for a live demo.
        answer = (
            f"(Vision model unavailable right now: {e}) Based on locally "
            f"computed measurements only — {stats_summary}."
        )
        powered_by = "local-stub-fallback"

    return jsonify({
        "question": question,
        "crop_image": url_for("static", filename=f"results/{crop_name}"),
        "answer": answer,
        "stats": stats,
        "powered_by": powered_by,
    })
