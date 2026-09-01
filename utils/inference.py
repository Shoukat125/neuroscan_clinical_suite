import onnxruntime as ort
import numpy as np
import cv2
import os
import time

MODEL_DIR = os.path.dirname(os.path.dirname(__file__))

CLASSIFIER_PATH = os.path.join(MODEL_DIR, "brain_tumor_classifier.onnx")
DETECT_PATH = os.path.join(MODEL_DIR, "brain_tumor_yolov8s_best.onnx")
SEG_PATH = os.path.join(MODEL_DIR, "brain_tumor_seg_yolov8n_best.onnx")

# Keras flow_from_directory sorts class folders alphabetically.
CLASSIFIER_LABELS = ["glioma", "meningioma", "notumor", "pituitary"]
YOLO_LABELS = {0: "glioma", 1: "meningioma", 2: "pituitary"}

_sessions = {}


def _get_session(path):
    if path not in _sessions:
        _sessions[path] = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    return _sessions[path]


def model_info(path):
    size_mb = round(os.path.getsize(path) / (1024 * 1024), 2)
    sess = _get_session(path)
    inputs = [(i.name, i.shape) for i in sess.get_inputs()]
    outputs = [(o.name, o.shape) for o in sess.get_outputs()]
    return {
        # NOTE: full filesystem path is intentionally NOT exposed here —
        # it leaked the local machine's folder structure to the frontend.
        "filename": os.path.basename(path),
        "size_mb": size_mb,
        "inputs": inputs,
        "outputs": outputs,
        "runtime": "ONNX Runtime (CPU)",
    }


def classify_image(image_bgr):
    """Run the Keras/tf2onnx classifier. Returns dict with label, confidence, all_scores, timing."""
    t0 = time.time()
    sess = _get_session(CLASSIFIER_PATH)
    img = cv2.resize(image_bgr, (224, 224))
    # NOTE: this model has a Keras Rescaling layer baked in (divides by 255
    # internally), so we must feed raw 0-255 values here, not pre-normalized ones.
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
    img = np.expand_dims(img, axis=0)  # NHWC, matches input [1,224,224,3]

    input_name = sess.get_inputs()[0].name
    out = sess.run(None, {input_name: img})[0][0]

    # The exported model already applies softmax internally (raw outputs sum to ~1).
    # Re-applying softmax would flatten the distribution, so only do it if the
    # raw outputs are NOT already a valid probability distribution.
    if abs(float(out.sum()) - 1.0) < 1e-3 and out.min() >= 0:
        probs = out
    else:
        exp = np.exp(out - np.max(out))
        probs = exp / exp.sum()

    idx = int(np.argmax(probs))
    elapsed = (time.time() - t0) * 1000
    return {
        "label": CLASSIFIER_LABELS[idx],
        "confidence": float(probs[idx]),
        "all_scores": {CLASSIFIER_LABELS[i]: float(probs[i]) for i in range(len(CLASSIFIER_LABELS))},
        "latency_ms": round(elapsed, 1),
        "is_tumor": CLASSIFIER_LABELS[idx] != "notumor",
    }


def _letterbox(image, new_shape=640):
    h, w = image.shape[:2]
    scale = min(new_shape / h, new_shape / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(image, (nw, nh))
    canvas = np.full((new_shape, new_shape, 3), 114, dtype=np.uint8)
    top = (new_shape - nh) // 2
    left = (new_shape - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    return canvas, scale, left, top


def _nms(boxes, scores, iou_thresh=0.45):
    idxs = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), score_threshold=0.25, nms_threshold=iou_thresh)
    if len(idxs) == 0:
        return []
    return idxs.flatten().tolist()


def detect_tumor(image_bgr, conf_thresh=0.25):
    """Run YOLOv8s detection model. Returns list of boxes + timing."""
    t0 = time.time()
    sess = _get_session(DETECT_PATH)
    h0, w0 = image_bgr.shape[:2]
    canvas, scale, padx, pady = _letterbox(image_bgr, 640)
    blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))[None, ...]

    input_name = sess.get_inputs()[0].name
    out = sess.run(None, {input_name: blob})[0]  # [1, 7, 8400] -> 4 box + 3 classes
    out = out[0].T  # [8400, 7]

    boxes_xywh = out[:, :4]
    class_scores = out[:, 4:]
    class_ids = np.argmax(class_scores, axis=1)
    confs = class_scores[np.arange(len(class_ids)), class_ids]

    keep = confs > conf_thresh
    boxes_xywh, class_ids, confs = boxes_xywh[keep], class_ids[keep], confs[keep]

    results = []
    if len(boxes_xywh) > 0:
        x1 = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2
        y1 = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2
        bw = boxes_xywh[:, 2]
        bh = boxes_xywh[:, 3]
        boxes_for_nms = np.stack([x1, y1, bw, bh], axis=1)
        idxs = _nms(boxes_for_nms, confs)
        for i in idxs:
            bx1 = (x1[i] - padx) / scale
            by1 = (y1[i] - pady) / scale
            bw_ = bw[i] / scale
            bh_ = bh[i] / scale
            bx1, by1 = max(0, bx1), max(0, by1)
            bx2 = min(w0, bx1 + bw_)
            by2 = min(h0, by1 + bh_)
            results.append({
                "label": YOLO_LABELS.get(int(class_ids[i]), str(class_ids[i])),
                "confidence": float(confs[i]),
                "box": [float(bx1), float(by1), float(bx2), float(by2)],
            })

    elapsed = (time.time() - t0) * 1000
    return {"detections": results, "latency_ms": round(elapsed, 1)}


def segment_tumor(image_bgr, conf_thresh=0.25):
    """Run YOLOv8n-seg model. Returns list of {label, confidence, box, mask(np.uint8 HxW), area_px, area_pct}."""
    t0 = time.time()
    sess = _get_session(SEG_PATH)
    h0, w0 = image_bgr.shape[:2]
    canvas, scale, padx, pady = _letterbox(image_bgr, 640)
    blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))[None, ...]

    input_name = sess.get_inputs()[0].name
    out0, out1 = sess.run(None, {input_name: blob})
    # out0: [1, 39, 8400] = 4 box + 3 cls + 32 mask coeffs
    # out1: [1, 32, 160, 160] proto masks
    preds = out0[0].T  # [8400, 39]
    boxes_xywh = preds[:, :4]
    class_scores = preds[:, 4:7]
    mask_coeffs = preds[:, 7:]
    class_ids = np.argmax(class_scores, axis=1)
    confs = class_scores[np.arange(len(class_ids)), class_ids]

    keep = confs > conf_thresh
    boxes_xywh = boxes_xywh[keep]
    class_ids = class_ids[keep]
    confs = confs[keep]
    mask_coeffs = mask_coeffs[keep]

    results = []
    if len(boxes_xywh) > 0:
        x1 = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2
        y1 = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2
        bw = boxes_xywh[:, 2]
        bh = boxes_xywh[:, 3]
        boxes_for_nms = np.stack([x1, y1, bw, bh], axis=1)
        idxs = _nms(boxes_for_nms, confs)

        proto = out1[0]  # [32, 160, 160]
        proto_flat = proto.reshape(32, -1)  # [32, 160*160]

        for i in idxs:
            mask = mask_coeffs[i] @ proto_flat  # [160*160]
            mask = mask.reshape(160, 160)
            mask = 1 / (1 + np.exp(-mask))  # sigmoid
            mask_full = cv2.resize(mask, (640, 640))

            # Box coords for the returned "box" field — pad removed + unscaled to original image.
            bx1 = x1[i] - padx
            by1 = y1[i] - pady
            bx2 = bx1 + bw[i]
            by2 = by1 + bh[i]

            # ⚠️ FIX: mask_full is still in the *padded* 640x640 canvas frame —
            # same frame as the raw model coords x1[i]/y1[i] (BEFORE subtracting
            # padx/pady). Cropping it with the already pad-subtracted bx1/by1
            # (as the original code did) silently shifts the mask off the real
            # tumor location for any non-square input image. We crop using the
            # raw (un-shifted) model-space coords here, and remove the letterbox
            # padding only once, afterwards.
            mx1c, my1c = max(0, int(x1[i])), max(0, int(y1[i]))
            mx2c, my2c = min(640, int(x1[i] + bw[i])), min(640, int(y1[i] + bh[i]))

            full_mask = np.zeros((640, 640), dtype=np.uint8)
            if my2c > my1c and mx2c > mx1c:
                mask_crop = mask_full[my1c:my2c, mx1c:mx2c]
                mask_bin = (mask_crop > 0.5).astype(np.uint8)
                full_mask[my1c:my2c, mx1c:mx2c] = mask_bin

            # Remove letterbox padding ONCE, still in the padded-canvas frame.
            pad_top, pad_left = int(pady), int(padx)
            pad_bottom, pad_right = 640 - pad_top, 640 - pad_left
            unpadded = full_mask[pad_top:pad_bottom, pad_left:pad_right]
            if unpadded.size == 0:  # safety net, shouldn't happen in practice
                unpadded = full_mask
            orig_mask = cv2.resize(unpadded, (w0, h0), interpolation=cv2.INTER_NEAREST)

            area_px = int(orig_mask.sum())
            area_pct = round(100 * area_px / (w0 * h0), 3)

            obx1 = max(0, (bx1 - 0) / scale)
            oby1 = max(0, (by1 - 0) / scale)
            obx2 = min(w0, (bx2) / scale)
            oby2 = min(h0, (by2) / scale)

            results.append({
                "label": YOLO_LABELS.get(int(class_ids[i]), str(class_ids[i])),
                "confidence": float(confs[i]),
                "box": [float(obx1), float(oby1), float(obx2), float(oby2)],
                "mask": orig_mask,
                "area_px": area_px,
                "area_pct": area_pct,
            })

    elapsed = (time.time() - t0) * 1000
    return {"segments": results, "latency_ms": round(elapsed, 1)}
