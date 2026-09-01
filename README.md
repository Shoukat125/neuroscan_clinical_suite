# NeuroScan Clinical Suite — Brain Tumor Analysis Web App

Flask app jo teen fine-tuned models ko chain karta hai (classification → detection → segmentation),
aur saath mein ek vectorless PDF RAG chatbot (Groq Llama 3.1 8B) bhi shamil hai.

## Folder Structure

```
braincare/
├── app.py                  # Flask routes
├── requirements.txt
├── models/                 # aapke 3 .onnx files yahan hain
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

## Setup (local machine par)

1. Python 3.10+ install hona chahiye.

2. Virtual environment banayein (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

3. Dependencies install karein:
   ```bash
   pip install -r requirements.txt
   ```

4. Apni Groq API key `.env` file mein set karein:
   - `.env` file project ke root mein already maujood hai, bas usme apni key daal dein:
     ```
     GROQ_API_KEY=your_groq_api_key_here
     ```
   - App start hote hi yeh key automatically load ho jayegi (`.env` git mein commit nahi hoti — `.gitignore` mein hai).

5. App run karein:
   ```bash
   python app.py
   ```

6. Browser mein open karein: **http://localhost:5000**

## Kya hai isme

### 1. Scan tab
- MRI image upload karein (drag & drop ya browse)
- "Analyze scan" dabayein
- **Stage 1 — Classification**: `brain_tumor_classifier.onnx` batata hai tumor hai ya nahi, aur type (glioma/meningioma/pituitary/notumor)
- Agar tumor positive aaye:
  - **Stage 2 — Detection**: `brain_tumor_yolov8s_best.onnx` bounding box ke saath dikhata hai tumor kahan hai
  - **Stage 3 — Segmentation**: `brain_tumor_seg_yolov8n_best.onnx` exact mask + area (pixels aur % of image) dikhata hai
- Overlay image (mask + box highlighted) screen par dikhti hai

### 2. Models tab
- Teeno models ki detail: file path, size (MB), input/output shape

### 3. Document Chat tab
- PDF upload karein
- Sawal poochein — answer **page number reference** ke saath aayega
- Retrieval **BM25 (lexical/keyword)** se hota hai, koi vector database nahi (FAISS/Chroma free hai is approach mein)
- LLM: **Groq Llama 3.1 8B Instant**

## Notes / Limitations

- Classifier label order assume kiya gaya hai alphabetically: `glioma, meningioma, notumor, pituitary`
  (Keras `flow_from_directory` ka default behaviour). Agar aapke training mein order alag tha,
  to `utils/inference.py` mein `CLASSIFIER_LABELS` list update kar dein.
- Detection/Segmentation models sirf tab chalte hain jab classifier "tumor" predict kare (notumor nahi).
- BM25 chhote PDF corpus par bhi kaam karta hai, lekin jitni zyada PDFs/pages honge utna behtar retrieval hoga.
- Yeh local/dev server hai (`debug=True`). Production deploy ke liye gunicorn/waitress use karein
  aur `debug=False` rakhein.
