import os
import re
import base64
from groq import Groq

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable not set")
        _client = Groq(api_key=api_key)
    return _client


# llama-3.1-8b-instant was deprecated by Groq on 2026-06-17. This text model
# powers the PDF document RAG assistant only (no image input needed there).
MODEL = "openai/gpt-oss-20b"

# Vision-capable model — powers Region Crop VQA and Treatment Advisory, both
# of which need to reason over the MRI image itself, not just numbers.
# "Qwen 3.2" does not exist on Groq; qwen/qwen3.6-27b is the current publicly
# available multimodal model (image + text) on a standard Groq API key.
VISION_MODEL = "qwen/qwen3.6-27b"

# Qwen 3.6 is a hybrid "thinking / non-thinking" model. Left on its default,
# it writes out its full internal planning ("The user wants me to...",
# "Drafting the response...") as part of the visible answer, which can also
# burn the whole token budget before it ever writes the real answer —
# cutting the reply off mid-sentence. reasoning_effort="none" switches it to
# non-thinking mode, and reasoning_format="hidden" is a second safety net
# that drops any reasoning content from the response entirely, so it never
# reaches the doctor-facing UI even in an edge case.
_NON_THINKING = {"reasoning_effort": "none", "reasoning_format": "hidden"}

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _clean_answer(text):
    """Defensive cleanup: strip any leaked <think>...</think> reasoning
    block, in case a model/response variant still emits one even in
    non-thinking mode, so it never reaches the doctor-facing UI."""
    if not text:
        return text
    cleaned = _THINK_BLOCK_RE.sub("", text).strip()
    return cleaned or text


def _image_to_data_url(image_path):
    ext = os.path.splitext(image_path)[1].lower().lstrip(".") or "png"
    mime = "jpeg" if ext == "jpg" else ext
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/{mime};base64,{b64}"


def rag_answer(question, retrieved_chunks):
    if not retrieved_chunks:
        context = "No relevant content was found in the uploaded documents."
    else:
        parts = []
        for c in retrieved_chunks:
            parts.append(f"[Source: {c['source']}, Page {c['page']}]\n{c['text']}")
        context = "\n\n---\n\n".join(parts)

    system = (
        "You are a helpful assistant answering questions strictly using the provided "
        "document excerpts. Always cite the page number(s) you used in the format "
        "(Source: filename, Page N) right after the relevant statement. "
        "If the answer isn't in the excerpts, say you couldn't find it in the uploaded documents."
    )
    user = f"Document excerpts:\n\n{context}\n\nQuestion: {question}"

    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return resp.choices[0].message.content


def vision_answer(image_path, question, supporting_stats=None, known_classification=None, actual_tumor_size=None):
    """Upgrade 4 — Interactive Region Crop VQA.

    Sends the cropped MRI region + the doctor's free-text question to
    Qwen 3.6-27B (Groq) for a true visual answer, grounded with locally
    computed pixel/segmentation stats so the model isn't reasoning on the
    image alone.
    """
    system = (
        "You are a radiology assistant helping a doctor interpret a cropped "
        "region of a brain MRI scan. Answer in EXACTLY 2-3 short sentences, "
        "plain prose, no headings, no bullet points, no restating the "
        "question. Describe only what is visually plausible from the image "
        "and the supplied measurements. Never state a definitive diagnosis — "
        "use language like 'may suggest' or 'is consistent with'. If the "
        "doctor's question contains a typo or an unfamiliar term, interpret "
        "it charitably in light of the known classification result rather "
        "than guessing at an unrelated condition. "
        "IMPORTANT — size questions: if asked about size, how big the tumor "
        "is, or measurements, you MUST report the 'actual tumor size' value "
        "given below (the real, whole-tumor measurement from the "
        "segmentation model). Do NOT report the crop/selection box size as "
        "if it were the tumor's size — that box is just where the doctor "
        "clicked and has no clinical meaning on its own; only mention it if "
        "specifically relevant to describing the selected region itself. "
        "End with a short reminder that this is AI-assisted support and the "
        "physician must confirm any finding."
    )
    context_lines = []
    if known_classification:
        context_lines.append(f"This scan's AI classification result is: {known_classification}.")
    if actual_tumor_size:
        context_lines.append(f"ACTUAL TUMOR SIZE (use this for any size question): {actual_tumor_size}.")
    if supporting_stats:
        context_lines.append(f"Additional measured stats for the selected crop: {supporting_stats}.")
    context_txt = ("\n\n" + " ".join(context_lines)) if context_lines else ""
    user_text = f"Doctor's question about the highlighted region: {question}{context_txt}"

    client = get_client()
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": _image_to_data_url(image_path)}},
                ],
            },
        ],
        temperature=0.4,
        max_tokens=350,
        **_NON_THINKING,
    )
    return _clean_answer(resp.choices[0].message.content)


def treatment_advisory(image_path, measurements_text, guideline_chunks, patient_context=None):
    """Upgrade 2 — Automated Treatment Advisory.

    Combines the scan/overlay image, the ONNX-derived measurements, and
    retrieved hospital-protocol PDF excerpts (via RAG) into one prompt for
    Qwen 3.6-27B, producing a structured note for the doctor. The doctor
    remains the final decision maker — the model is instructed accordingly
    and the output always carries that disclaimer.
    """
    if guideline_chunks:
        parts = []
        for c in guideline_chunks:
            parts.append(f"[Source: {c['source']}, Page {c['page']}]\n{c['text']}")
        guideline_context = "\n\n---\n\n".join(parts)
    else:
        guideline_context = (
            "No hospital protocol / guideline PDFs have been uploaded yet — "
            "base the note only on general, widely-accepted principles and "
            "clearly flag that no institution-specific protocol was available."
        )

    system = (
        "You are a clinical decision-support assistant preparing a structured "
        "treatment advisory note for a neuro-oncologist reviewing a brain MRI. "
        "You are NOT diagnosing and you are NOT prescribing treatment — you are "
        "organizing the AI scan findings and any retrieved protocol guidance "
        "into a clear, precise note the doctor can quickly review.\n\n"
        "GROUNDING RULES (strict):\n"
        "- Only state facts that are directly supported by the measurements "
        "text or the guideline excerpts given below. Do not invent anatomical "
        "location, laterality, or scan orientation details beyond what is "
        "explicitly stated in the measurements.\n"
        "- Only ONE 2D image is provided. Never reference other views, planes, "
        "or slices (e.g. sagittal, coronal) unless the measurements text says "
        "so explicitly.\n"
        "- If the guideline excerpts don't cover something, say so plainly "
        "instead of filling the gap with generic textbook language dressed up "
        "as specific guidance.\n"
        "- Use confidence/measurement labels EXACTLY as named in the "
        "measurements text (e.g. if it says 'segmentation confidence', do "
        "not call it 'detection confidence' or vice versa) — the doctor sees "
        "the same labels in the app UI, and renaming them creates a mismatch "
        "that looks like conflicting numbers.\n\n"
        "FORMAT: use exactly these four headings — "
        "'Summary of AI Findings', 'Guideline-Based Considerations', "
        "'Suggested Next Steps for Doctor Review', 'Cautions & Limitations'. "
        "Each section: MAXIMUM 2 short bullet points (1 is fine if that's "
        "all that's needed), each bullet one sentence. No filler sentences, "
        "no repeating the same fact across sections, no restating the "
        "obvious. Target the whole note under 130 words total — a doctor "
        "should be able to read it in 20 seconds. Always make clear the "
        "doctor is the final decision maker (can be a single short clause, "
        "doesn't need its own bullet)."
    )
    user_text = (
        f"AI scan measurements:\n{measurements_text}\n\n"
        f"Patient context: {patient_context or 'Not provided'}\n\n"
        f"Retrieved guideline / protocol excerpts:\n{guideline_context}\n\n"
        "Prepare the structured treatment advisory note."
    )

    client = get_client()
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": _image_to_data_url(image_path)}},
                ],
            },
        ],
        temperature=0.3,
        max_tokens=450,
        **_NON_THINKING,
    )
    return _clean_answer(resp.choices[0].message.content)
