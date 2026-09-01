import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from utils import rag, llm

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/api/rag/upload", methods=["POST"])
def api_rag_upload():
    if "pdf" not in request.files:
        return jsonify({"error": "No PDF uploaded"}), 400
    file = request.files["pdf"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({"error": "Invalid filename"}), 400

    save_path = os.path.join(rag.DOC_DIR, filename)
    file.save(save_path)
    # ingest_pdf removes any previously-indexed chunks for this same filename
    # first, so re-uploading the same document replaces it instead of
    # duplicating its chunks in the index.
    result = rag.ingest_pdf(save_path)
    return jsonify(result)


@chat_bp.route("/api/rag/documents")
def api_rag_documents():
    return jsonify(rag.list_documents())


@chat_bp.route("/api/rag/chat", methods=["POST"])
def api_rag_chat():
    data = request.get_json(force=True)
    question = (data or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is empty"}), 400
    if not rag.has_documents():
        return jsonify({"error": "Please upload at least one PDF first."}), 400

    chunks = rag.retrieve(question, top_k=5)
    try:
        answer = llm.rag_answer(question, chunks)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    sources = [{"source": c["source"], "page": c["page"]} for c in chunks]
    return jsonify({"answer": answer, "sources": sources})
