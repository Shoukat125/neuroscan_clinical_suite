import os
import uuid
import cv2
import numpy as np
from flask import url_for

from utils import inference
from core.config import UPLOAD_DIR, RESULT_DIR, COLORS


def run_full_analysis(saved_path, uid):
    """Run classify -> (detect + segment if tumor) -> overlay image.

    Returns a dict in the same shape /api/analyze has always returned.
    Shared by /api/analyze, /api/compare, and the PDF report generator so
    all three stay in sync with one implementation.
    """
    image = cv2.imread(saved_path)
    if image is None:
        return None

    cls_result = inference.classify_image(image)

    response = {
        "classification": cls_result,
        "detection": None,
        "segmentation": None,
        "overlay_image": None,
        "overlay_path": None,
    }

    if cls_result["is_tumor"]:
        det = inference.detect_tumor(image)
        seg = inference.segment_tumor(image)

        response["detection"] = {
            "latency_ms": det["latency_ms"],
            "boxes": [
                {"label": d["label"], "confidence": round(d["confidence"], 3), "box": [round(v, 1) for v in d["box"]]}
                for d in det["detections"]
            ],
        }

        seg_summary = []
        overlay = image.copy()
        h, w = image.shape[:2]
        for s in seg["segments"]:
            color = COLORS.get(s["label"], (0, 255, 0))
            mask = s["mask"].astype(bool)
            overlay[mask] = (overlay[mask] * 0.5 + np.array(color) * 0.5).astype(np.uint8)
            x1, y1, x2, y2 = [int(v) for v in s["box"]]
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
            label_txt = f"{s['label']} {s['confidence']:.2f}"
            cv2.putText(overlay, label_txt, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            seg_summary.append({
                "label": s["label"],
                "confidence": round(s["confidence"], 3),
                "area_px": s["area_px"],
                "area_pct": s["area_pct"],
                "box": [round(v, 1) for v in s["box"]],
            })

        overlay_name = f"{uid}_overlay.png"
        overlay_path = os.path.join(RESULT_DIR, overlay_name)
        cv2.imwrite(overlay_path, overlay)

        response["segmentation"] = {
            "latency_ms": seg["latency_ms"],
            "segments": seg_summary,
            "image_size": {"width": w, "height": h},
        }
        response["overlay_image"] = url_for("static", filename=f"results/{overlay_name}")
        response["overlay_path"] = overlay_path

    return response


def _save_upload(file_storage):
    """Save an uploaded FileStorage to UPLOAD_DIR with a fresh uid. Returns (uid, saved_path, saved_name)."""
    ext = os.path.splitext(file_storage.filename)[1].lower() or ".png"
    uid = uuid.uuid4().hex[:10]
    saved_name = f"{uid}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_name)
    file_storage.save(saved_path)
    return uid, saved_path, saved_name


def total_tumor_area_pct(analysis):
    """Sum area_pct across all segments (handles multiple detected regions)."""
    if not analysis or not analysis.get("segmentation"):
        return 0.0
    return round(sum(s["area_pct"] for s in analysis["segmentation"]["segments"]), 3)
