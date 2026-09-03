# NeuroScan Clinical Suite — Brain Tumor Analysis Web App

A Flask app that chains three fine-tuned models (classification → detection → segmentation),
along with a vectorless PDF RAG chatbot powered by Groq.

## Folder Structure

```
braincare/
├── app.py                  # Flask routes
├── requirements.txt
├── models/                 # your 3 .onnx files go here
├── utils/
│   ├── inference.py         # classification + detection + segmentation logic
│   ├── rag.py                # BM25 vectorless retrieval (page-level chunks)
│   └── llm.py                # Groq API wrapper
├── templates/index.html
├── static/css/style.css
├── static/js/app.js
├── static/uploads/          # uploaded MRI images
├── static/results/          # overlay images (segmentation visualizations)
└── rag_docs/                 # uploaded PDFs
```

## Setup (on your local machine)

1. Python 3.10+ must be installed.

2. Create a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set your Groq API key in the `.env` file:
   - Create a `.env` file in the project root (it is **not** included in the repo for
     security reasons — never commit real API keys):
     ```
     GROQ_API_KEY=your_groq_api_key_here
     ```
   - The key loads automatically as soon as the app starts (`.env` is excluded via
     `.gitignore`).

5. Run the app:
   ```bash
   python app.py
   ```

6. Open in your browser: **http://localhost:5000**

## What's Inside

### 1. Scan tab
- Upload an MRI image (drag & drop or browse)
- Click "Analyze scan"
- **Stage 1 — Classification**: `brain_tumor_classifier.onnx` determines whether there is a tumor
  or not, and its type (glioma/meningioma/pituitary/notumor)
- If the result is tumor-positive:
  - **Stage 2 — Detection**: `brain_tumor_yolov8s_best.onnx` shows the tumor location with a
    bounding box
  - **Stage 3 — Segmentation**: `brain_tumor_seg_yolov8n_best.onnx` shows the exact mask + area
    (in pixels and % of image)
- The overlay image (mask + box highlighted) is displayed on screen

### 2. Models tab
- Details of all three models: file path, size (MB), input/output shape

### 3. Document Chat tab
- Upload a PDF
- Ask questions — the answer comes back with a **page number reference**
- Retrieval is done via **BM25 (lexical/keyword)** — no vector database (this approach is
  free of FAISS/Chroma)
- LLM: **Groq `openai/gpt-oss-20b`** for text chat, **Groq `qwen/qwen3.6-27b`** for
  vision-based tasks (region VQA, image-based advisory)

## Notes / Limitations

- The classifier label order is assumed to be alphabetical: `glioma, meningioma, notumor, pituitary`
  (Keras `flow_from_directory`'s default behavior). If your training used a different order,
  update the `CLASSIFIER_LABELS` list in `utils/inference.py`.
- Detection/Segmentation models only run when the classifier predicts "tumor" (not notumor).
- BM25 works even on a small PDF corpus, but retrieval quality improves with more PDFs/pages.
- The app runs with `debug=False` and binds to `0.0.0.0`, ready for a production WSGI
  server (gunicorn/waitress) behind a reverse proxy — do not use Flask's built-in dev
  server directly in production.

## Deployment Notes (Alibaba Cloud)

- Never commit `.env` or any real API key to the repository. Set `GROQ_API_KEY` as an
  environment variable / secret on the cloud instance instead.
- Run behind gunicorn (e.g. `gunicorn -w 2 -b 0.0.0.0:5000 app:app`) rather than
  `python app.py` directly.
- If a Groq key was ever pushed to a public GitHub repo, treat it as compromised —
  revoke and regenerate it in the Groq console, regardless of later removing it from
  the code.
