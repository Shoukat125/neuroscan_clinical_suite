import os
import re
from pypdf import PdfReader
from rank_bm25 import BM25Okapi

DOC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rag_docs")
os.makedirs(DOC_DIR, exist_ok=True)

_index = {
    "chunks": [],       # list of {"text":..., "page":..., "source":...}
    "bm25": None,
    "tokenized": [],
}


def _tokenize(text):
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _chunk_page_text(text, max_words=180):
    """Split a page's text into smaller overlapping chunks for finer retrieval."""
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks = []
    step = max_words - 30
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + max_words])
        if chunk.strip():
            chunks.append(chunk)
        if i + max_words >= len(words):
            break
    return chunks


def ingest_pdf(filepath):
    """Extract text per page, chunk it, and add to the in-memory BM25 index.

    If a document with the same source filename was already ingested before,
    its old chunks are removed first so re-uploading doesn't duplicate entries
    in the index (which would skew BM25 ranking).
    """
    reader = PdfReader(filepath)
    source = os.path.basename(filepath)

    # Drop any previously-indexed chunks for this source before re-adding.
    _index["chunks"] = [c for c in _index["chunks"] if c["source"] != source]

    added = 0
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if not text:
            continue
        for chunk in _chunk_page_text(text):
            _index["chunks"].append({"text": chunk, "page": page_num, "source": source})
            added += 1
    _rebuild_index()
    return {"source": source, "pages": len(reader.pages), "chunks_added": added}


def list_documents():
    sources = {}
    for c in _index["chunks"]:
        sources.setdefault(c["source"], set()).add(c["page"])
    return [{"source": s, "pages": len(p)} for s, p in sources.items()]


def remove_document(source):
    _index["chunks"] = [c for c in _index["chunks"] if c["source"] != source]
    _rebuild_index()


def _rebuild_index():
    _index["tokenized"] = [_tokenize(c["text"]) for c in _index["chunks"]]
    if _index["tokenized"]:
        _index["bm25"] = BM25Okapi(_index["tokenized"])
    else:
        _index["bm25"] = None


def retrieve(query, top_k=5):
    """Vectorless retrieval: BM25 lexical search over page-level chunks."""
    if not _index["bm25"]:
        return []
    tokenized_query = _tokenize(query)
    if not tokenized_query:
        return []
    scores = _index["bm25"].get_scores(tokenized_query)
    # BM25 IDF can go negative on very small corpora; only require that the
    # chunk shares at least one query term, not a positive absolute score.
    chunk_tokens = _index["tokenized"]
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    results = []
    qset = set(tokenized_query)
    for i in ranked:
        if not (qset & set(chunk_tokens[i])):
            continue
        c = _index["chunks"][i]
        results.append({
            "text": c["text"],
            "page": c["page"],
            "source": c["source"],
            "score": float(scores[i]),
        })
    return results


def has_documents():
    return len(_index["chunks"]) > 0
