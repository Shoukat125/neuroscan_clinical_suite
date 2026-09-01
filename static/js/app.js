// ===== Theme =====
const root = document.documentElement;
const themeToggle = document.getElementById('themeToggle');
const savedTheme = localStorage.getItem('theme') || 'dark';
root.setAttribute('data-theme', savedTheme);
if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
  });
}

// ===== Tabs =====
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-selected', 'false');
    });
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true');
    const targetPanel = document.getElementById('tab-' + btn.dataset.tab);
    if (targetPanel) targetPanel.classList.add('active');
    if (btn.dataset.tab === 'models') loadModelInfo();
    if (btn.dataset.tab === 'chat') loadDocuments();
  });
});

// ===== Scan Upload & Workstation Viewport =====
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const previewWrap = document.getElementById('previewWrap');
const previewImg = document.getElementById('previewImg');
const analyzeBtn = document.getElementById('analyzeBtn');
const pipeline = document.getElementById('pipeline');
const resultContent = document.getElementById('resultContent');
const resultsStandby = document.getElementById('resultsStandby');

const viewerContainer = document.getElementById('viewerContainer');
const viewerEmpty = document.getElementById('viewerEmpty');
const viewerStage = document.getElementById('viewerStage');
const overlayWrap = document.getElementById('overlayWrap');
const viewerStatusText = document.getElementById('viewerStatusText');

let currentFile = null;
let lastAnalysis = null; // holds the full /api/analyze response for the PDF report + region VQA

if (dropzone && fileInput) {
  dropzone.addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', e => { if (e.target.files.length) handleFile(e.target.files[0]); });
}

function handleFile(file) {
  currentFile = file;
  const reader = new FileReader();
  reader.onload = e => {
    if (previewImg) previewImg.src = e.target.result;
    if (previewWrap) previewWrap.classList.remove('hidden');
    if (pipeline) pipeline.classList.add('hidden');
    if (resultContent) resultContent.classList.add('hidden');
    if (resultsStandby) resultsStandby.classList.remove('hidden');
    if (viewerEmpty) viewerEmpty.classList.add('hidden');
    if (viewerStage) viewerStage.classList.remove('hidden');
    if (overlayWrap) overlayWrap.classList.add('hidden');
    if (viewerContainer) viewerContainer.classList.remove('scanning');
    if (viewerStatusText) viewerStatusText.textContent = 'SCAN LOADED · READY FOR INFERENCE';
  };
  reader.readAsDataURL(file);
}

function setStep(name, state) {
  if (!pipeline) return;
  const el = pipeline.querySelector(`.step[data-step="${name}"]`);
  if (!el) return;
  el.classList.remove('active', 'done');
  if (state) el.classList.add(state);
}

if (analyzeBtn) {
  analyzeBtn.addEventListener('click', async () => {
    if (!currentFile) return;
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = 'Analyzing…';
    if (pipeline) pipeline.classList.remove('hidden');
    setStep('classify', 'active'); setStep('detect', null); setStep('segment', null);
    if (resultContent) resultContent.classList.add('hidden');
    if (resultsStandby) resultsStandby.classList.remove('hidden');

    // Activate PACS MRI Scan Sweep Animation over the image container
    if (viewerContainer) viewerContainer.classList.add('scanning');
    if (viewerStatusText) viewerStatusText.textContent = 'INFERENCE IN FLIGHT · MRI SWEEP';

    const formData = new FormData();
    formData.append('image', currentFile);

    try {
      const res = await fetch('/api/analyze', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.error) { alert(data.error); return; }
      lastAnalysis = data;
      renderResults(data);
    } catch (err) {
      alert('Analysis failed: ' + err.message);
    } finally {
      analyzeBtn.disabled = false;
      analyzeBtn.innerHTML = '<span class="btn-text">Execute AI Analysis</span><span class="btn-arrow">→</span>';
      if (viewerContainer) viewerContainer.classList.remove('scanning');
    }
  });
}

const CLASS_COLORS = { 
  glioma: '#B3261E', 
  meningioma: '#3b5fa8', 
  pituitary: '#7E4B9C', 
  notumor: '#3FB950' 
};

function renderResults(data) {
  setStep('classify', 'done');
  if (viewerContainer) viewerContainer.classList.remove('scanning');

  // Classification card
  const cls = data.classification;
  const clsLatencyEl = document.getElementById('clsLatency');
  if (clsLatencyEl) clsLatencyEl.textContent = cls.latency_ms + ' ms';
  
  const verdict = document.getElementById('clsVerdict');
  if (verdict) {
    verdict.className = 'verdict ' + (cls.is_tumor ? 'tumor' : 'clear');
    verdict.innerHTML = `
      <span class="verdict-label">${cls.is_tumor ? cls.label : 'No tumor detected'}</span>
      <span class="verdict-conf">${(cls.confidence * 100).toFixed(1)}% confidence</span>
    `;
  }

  const scoresEl = document.getElementById('clsScores');
  if (scoresEl) {
    scoresEl.innerHTML = '';
    Object.entries(cls.all_scores).sort((a,b) => b[1]-a[1]).forEach(([label, score]) => {
      const row = document.createElement('div');
      row.className = 'score-row';
      row.innerHTML = `
        <span class="label">${label}</span>
        <span class="score-track"><span class="score-fill" style="width:${(score*100).toFixed(1)}%; background:${CLASS_COLORS[label]||'#22D3C8'}"></span></span>
        <span class="score-val">${(score*100).toFixed(1)}%</span>
      `;
      scoresEl.appendChild(row);
    });
  }

  const locationCard = document.getElementById('locationCard');
  const sizeCard = document.getElementById('sizeCard');
  const regionQaCard = document.getElementById('regionQaCard');
  const advisoryCard = document.getElementById('advisoryCard');

  if (cls.is_tumor && data.detection) {
    setStep('detect', 'done');
    setStep('segment', 'done');

    if (locationCard) locationCard.classList.remove('hidden');
    const detLatencyEl = document.getElementById('detLatency');
    if (detLatencyEl) detLatencyEl.textContent = data.detection.latency_ms + ' ms';

    // Show overlay in center viewer
    if (overlayWrap) overlayWrap.classList.remove('hidden');
    const overlayImgEl = document.getElementById('overlayImg');
    if (overlayImgEl) {
      overlayImgEl.src = data.overlay_image;
      overlayImgEl.onload = () => setupCropCanvas(overlayImgEl);
    }

    if (viewerStatusText) viewerStatusText.textContent = `ANOMALY DETECTED · ${cls.label.toUpperCase()} OVERLAY ACTIVE`;

    if (regionQaCard) regionQaCard.classList.remove('hidden');
    if (advisoryCard) advisoryCard.classList.remove('hidden');
    const advisoryResult = document.getElementById('advisoryResult');
    if (advisoryResult) advisoryResult.classList.add('hidden');
    const regionQaAnswer = document.getElementById('regionQaAnswer');
    if (regionQaAnswer) regionQaAnswer.classList.add('hidden');
    cropBox = null;

    const detList = document.getElementById('detList');
    if (detList) {
      detList.innerHTML = '';
      if (data.detection.boxes.length === 0) {
        detList.innerHTML = '<p style="color:var(--text-secondary);font-size:12px;">No precise bounding box found, but classifier flagged abnormal tissue — recommend manual review.</p>';
      }
      data.detection.boxes.forEach(b => {
        const div = document.createElement('div');
        div.className = 'detect-item';
        div.innerHTML = `
          <span class="tag"><span class="tag-dot" style="background:${CLASS_COLORS[b.label]||'#22D3C8'}"></span>${b.label}</span>
          <span class="metric">conf ${(b.confidence*100).toFixed(1)}% · box [${b.box.join(', ')}]</span>
        `;
        detList.appendChild(div);
      });
    }

    if (sizeCard) sizeCard.classList.remove('hidden');
    const segLatencyEl = document.getElementById('segLatency');
    if (segLatencyEl) segLatencyEl.textContent = data.segmentation.latency_ms + ' ms';
    const segList = document.getElementById('segList');
    if (segList) {
      segList.innerHTML = '';
      if (data.segmentation.segments.length === 0) {
        segList.innerHTML = '<p style="color:var(--text-secondary);font-size:12px;">Segmentation model found no precise mask for this case.</p>';
      }
      data.segmentation.segments.forEach(s => {
        const div = document.createElement('div');
        div.className = 'segment-item';
        div.innerHTML = `
          <span class="tag"><span class="tag-dot" style="background:${CLASS_COLORS[s.label]||'#22D3C8'}"></span>${s.label}</span>
          <span class="metric">${s.area_px.toLocaleString()} px · ${s.area_pct}% area</span>
        `;
        segList.appendChild(div);
      });
    }
  } else {
    if (locationCard) locationCard.classList.add('hidden');
    if (sizeCard) sizeCard.classList.add('hidden');
    if (regionQaCard) regionQaCard.classList.add('hidden');
    if (advisoryCard) advisoryCard.classList.add('hidden');
    if (overlayWrap) overlayWrap.classList.add('hidden');
    if (viewerStatusText) viewerStatusText.textContent = 'NORMAL SCAN · NO LESIONS IDENTIFIED';
  }

  if (resultsStandby) resultsStandby.classList.add('hidden');
  if (resultContent) resultContent.classList.remove('hidden');
}

// ===== Region crop VQA (Frontend crop canvas math preserved) =====
let cropCanvasCtx = null;
let cropBox = null; // {x1,y1,x2,y2} in ORIGINAL image pixel coordinates
let cropScale = 1;

function setupCropCanvas(imgEl) {
  const canvas = document.getElementById('cropCanvas');
  if (!canvas || !imgEl) return;
  canvas.width = imgEl.clientWidth;
  canvas.height = imgEl.clientHeight;
  cropScale = imgEl.naturalWidth / imgEl.clientWidth;
  cropCanvasCtx = canvas.getContext('2d');
  cropCanvasCtx.clearRect(0, 0, canvas.width, canvas.height);

  let drawing = false, startX = 0, startY = 0;

  function pos(e) {
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return { x: clientX - rect.left, y: clientY - rect.top };
  }

  function onDown(e) {
    const p = pos(e);
    drawing = true;
    startX = p.x; startY = p.y;
  }
  function onMove(e) {
    if (!drawing) return;
    const p = pos(e);
    cropCanvasCtx.clearRect(0, 0, canvas.width, canvas.height);
    cropCanvasCtx.strokeStyle = '#22D3C8';
    cropCanvasCtx.lineWidth = 2;
    cropCanvasCtx.setLineDash([5, 3]);
    const w = p.x - startX, h = p.y - startY;
    cropCanvasCtx.fillStyle = 'rgba(34, 211, 200, 0.12)';
    cropCanvasCtx.fillRect(startX, startY, w, h);
    cropCanvasCtx.strokeRect(startX, startY, w, h);
  }
  function onUp(e) {
    if (!drawing) return;
    drawing = false;
    const p = pos(e);
    const x1 = Math.min(startX, p.x), x2 = Math.max(startX, p.x);
    const y1 = Math.min(startY, p.y), y2 = Math.max(startY, p.y);
    if (x2 - x1 < 8 || y2 - y1 < 8) { cropBox = null; return; } // ignore accidental clicks
    cropBox = {
      x1: Math.round(x1 * cropScale), y1: Math.round(y1 * cropScale),
      x2: Math.round(x2 * cropScale), y2: Math.round(y2 * cropScale),
    };
  }

  canvas.onmousedown = onDown; canvas.onmousemove = onMove; canvas.onmouseup = onUp; canvas.onmouseleave = onUp;
  canvas.ontouchstart = onDown; canvas.ontouchmove = onMove; canvas.ontouchend = onUp;
}

window.addEventListener('resize', () => {
  const overlayImgEl = document.getElementById('overlayImg');
  if (overlayImgEl && overlayImgEl.src && overlayWrap && !overlayWrap.classList.contains('hidden')) {
    setupCropCanvas(overlayImgEl);
  }
});

const regionQaForm = document.getElementById('regionQaForm');
if (regionQaForm) {
  regionQaForm.addEventListener('submit', async e => {
    e.preventDefault();
    const input = document.getElementById('regionQaInput');
    const question = input.value.trim();
    const answerBox = document.getElementById('regionQaAnswer');
    if (!question) return;
    if (!cropBox) {
      answerBox.classList.remove('hidden');
      answerBox.innerHTML = '<p class="qa-error">Draw a box on the scan above first to select a region, then ask.</p>';
      return;
    }
    if (!lastAnalysis || !lastAnalysis.uid) {
      answerBox.classList.remove('hidden');
      answerBox.innerHTML = '<p class="qa-error">Please analyze a scan first.</p>';
      return;
    }

    answerBox.classList.remove('hidden');
    answerBox.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';

    try {
      const res = await fetch('/api/region-vqa', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          uid: lastAnalysis.uid,
          box: [cropBox.x1, cropBox.y1, cropBox.x2, cropBox.y2],
          question,
          known_classification: lastAnalysis.classification ? lastAnalysis.classification.label : null,
        }),
      });
      const data = await res.json();
      if (data.error) {
        answerBox.innerHTML = `<p class="qa-error">${data.error}</p>`;
        return;
      }
      answerBox.innerHTML = `
        <img class="crop-preview" src="${data.crop_image}" alt="Selected region">
        <p class="qa-answer-text">${data.answer}</p>
      `;
    } catch (err) {
      answerBox.innerHTML = `<p class="qa-error">Something went wrong: ${err.message}</p>`;
    }
  });
}

// ===== Treatment Advisory =====
const generateAdvisoryBtn = document.getElementById('generateAdvisoryBtn');
if (generateAdvisoryBtn) {
  generateAdvisoryBtn.addEventListener('click', async () => {
    if (!lastAnalysis || !lastAnalysis.uid) {
      alert('Please analyze a scan first.');
      return;
    }
    const btn = document.getElementById('generateAdvisoryBtn');
    const resultBox = document.getElementById('advisoryResult');
    btn.disabled = true;
    btn.textContent = 'Generating…';
    resultBox.classList.remove('hidden');
    resultBox.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';

    const patient = {
      name: document.getElementById('patientName') ? document.getElementById('patientName').value.trim() : '',
      patient_id: document.getElementById('patientId') ? document.getElementById('patientId').value.trim() : '',
      age: document.getElementById('patientAge') ? document.getElementById('patientAge').value.trim() : '',
      referring_doctor: document.getElementById('referringDoctor') ? document.getElementById('referringDoctor').value.trim() : '',
    };

    try {
      const res = await fetch('/api/treatment-advisory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid: lastAnalysis.uid, analysis: lastAnalysis, patient }),
      });
      const data = await res.json();
      if (data.error) {
        resultBox.innerHTML = `<p class="qa-error">${data.error}</p>`;
        return;
      }
      let sourcesHtml = '';
      if (data.guideline_sources && data.guideline_sources.length) {
        const uniq = [...new Set(data.guideline_sources.map(s => `${s.source} (p.${s.page})`))];
        sourcesHtml = `<p class="advisory-sources">Guideline sources used: ${uniq.join(', ')}</p>`;
      } else {
        sourcesHtml = '<p class="advisory-sources">No hospital protocol PDFs were uploaded — note is based on general principles only. Upload guideline PDFs in the Document Chat tab for institution-specific guidance.</p>';
      }
      resultBox.innerHTML = `<div class="advisory-note">${data.note.replace(/\n/g, '<br>')}</div>${sourcesHtml}`;
    } catch (err) {
      resultBox.innerHTML = `<p class="qa-error">Something went wrong: ${err.message}</p>`;
    } finally {
      btn.disabled = false;
      btn.textContent = 'Generate Treatment Advisory';
    }
  });
}

// ===== PDF report export =====
const downloadReportBtn = document.getElementById('downloadReportBtn');
if (downloadReportBtn) {
  downloadReportBtn.addEventListener('click', async () => {
    if (!lastAnalysis || !lastAnalysis.uid) {
      alert('Please analyze a scan first.');
      return;
    }
    const btn = document.getElementById('downloadReportBtn');
    btn.disabled = true;
    btn.textContent = 'Generating…';

    const patient = {
      name: document.getElementById('patientName') ? document.getElementById('patientName').value.trim() : '',
      patient_id: document.getElementById('patientId') ? document.getElementById('patientId').value.trim() : '',
      age: document.getElementById('patientAge') ? document.getElementById('patientAge').value.trim() : '',
      referring_doctor: document.getElementById('referringDoctor') ? document.getElementById('referringDoctor').value.trim() : '',
    };

    try {
      const res = await fetch('/api/report/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid: lastAnalysis.uid, analysis: lastAnalysis, patient }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.error || 'Could not generate the report.');
        return;
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `neuroscan_report_${lastAnalysis.uid}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Report download failed: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = '⬇ Download PDF Report';
    }
  });
}

// ===== Compare Scans tab =====
let oldFile = null, newFile = null;

function wireCompareDropzone(zoneId, inputId, previewId, onSet) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);
  if (!zone || !input || !preview) return;

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleCompareFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', e => { if (e.target.files.length) handleCompareFile(e.target.files[0]); });

  function handleCompareFile(file) {
    onSet(file);
    const reader = new FileReader();
    reader.onload = e => {
      preview.src = e.target.result;
      preview.classList.remove('hidden');
    };
    reader.readAsDataURL(file);
    maybeEnableCompare();
  }
}

function maybeEnableCompare() {
  const btn = document.getElementById('compareBtn');
  if (btn) btn.disabled = !(oldFile && newFile);
}

wireCompareDropzone('oldDropzone', 'oldFileInput', 'oldPreview', f => { oldFile = f; });
wireCompareDropzone('newDropzone', 'newFileInput', 'newPreview', f => { newFile = f; });

const compareBtn = document.getElementById('compareBtn');
if (compareBtn) {
  compareBtn.addEventListener('click', async () => {
    if (!oldFile || !newFile) return;
    const btn = document.getElementById('compareBtn');
    btn.disabled = true;
    btn.textContent = 'Comparing…';

    const formData = new FormData();
    formData.append('old_image', oldFile);
    formData.append('new_image', newFile);

    try {
      const res = await fetch('/api/compare', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.error) { alert(data.error); return; }
      renderCompareResult(data);
    } catch (err) {
      alert('Comparison failed: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Compare scans';
    }
  });
}

function renderCompareResult(data) {
  const wrap = document.getElementById('compareResult');
  if (!wrap) return;
  wrap.classList.remove('hidden');

  const oldResultImg = document.getElementById('oldResultImg');
  const newResultImg = document.getElementById('newResultImg');
  if (oldResultImg) oldResultImg.src = data.old.overlay_image || data.old.uploaded_image;
  if (newResultImg) newResultImg.src = data.new.overlay_image || data.new.uploaded_image;

  const oldAreaLabel = document.getElementById('oldAreaLabel');
  const newAreaLabel = document.getElementById('newAreaLabel');
  if (oldAreaLabel) oldAreaLabel.textContent = `Baseline Scan · ${data.comparison.old_area_pct}% tumor area`;
  if (newAreaLabel) newAreaLabel.textContent = `Follow-up Scan · ${data.comparison.new_area_pct}% tumor area`;

  const c = data.comparison;
  const verdictEl = document.getElementById('compareVerdict');
  if (verdictEl) {
    verdictEl.className = 'compare-verdict ' + c.verdict;

    const pctTxt = c.percent_change !== null
      ? `${c.percent_change > 0 ? '+' : ''}${c.percent_change}% relative change`
      : 'no baseline tumor area to compare against';

    const labels = {
      growing: `⚠ Longitudinal Analysis: Tumor area increased by ${Math.abs(c.point_change_pct)} percentage points (${pctTxt}).`,
      shrinking: `✓ Longitudinal Analysis: Tumor area decreased by ${Math.abs(c.point_change_pct)} percentage points (${pctTxt}).`,
      stable: `— Longitudinal Analysis: Tumor area is essentially stable (${pctTxt}).`,
      no_tumor: 'No tumor detected in either scan.',
    };
    verdictEl.textContent = labels[c.verdict] || '';
  }
}

// ===== Models Tab =====
let modelsLoaded = false;
async function loadModelInfo() {
  if (modelsLoaded) return;
  try {
    const res = await fetch('/api/model-info');
    const data = await res.json();
    const grid = document.getElementById('modelGrid');
    if (!grid) return;
    const meta = {
      classifier: { title: 'Classifier (ResNet)', role: 'Stage 1 · Always runs', icon: '🧪' },
      detector: { title: 'Detector (YOLOv8s)', role: 'Stage 2 · Runs if tumor found', icon: '🎯' },
      segmenter: { title: 'Segmenter (YOLOv8n-seg)', role: 'Stage 3 · Runs if tumor found', icon: '🩻' },
    };
    grid.innerHTML = '';
    Object.entries(data).forEach(([key, info]) => {
      const m = meta[key] || { title: key, role: 'Model', icon: '⚙' };
      const card = document.createElement('div');
      card.className = 'model-card';
      card.innerHTML = `
        <span class="role">${m.role}</span>
        <h3>${m.icon} ${m.title}</h3>
        <div class="model-row"><span class="k">File</span><span class="v">${info.filename}</span></div>
        <div class="model-row"><span class="k">Size on disk</span><span class="v">${info.size_mb} MB</span></div>
        <div class="model-row"><span class="k">Input</span><span class="v">${info.inputs.map(i => i[0]+' '+JSON.stringify(i[1])).join(', ')}</span></div>
        <div class="model-row"><span class="k">Output</span><span class="v">${info.outputs.map(o => o[0]+' '+JSON.stringify(o[1])).join(', ')}</span></div>
        <div class="model-runtime">⚡ ONNX Runtime · ${info.runtime}</div>
      `;
      grid.appendChild(card);
    });
    modelsLoaded = true;
  } catch (e) {
    console.error('Failed to load model info', e);
  }
}

// ===== Document Chat tab =====
const pdfDropzone = document.getElementById('pdfDropzone');
const pdfInput = document.getElementById('pdfInput');
const docList = document.getElementById('docList');
const chatLog = document.getElementById('chatLog');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');

if (pdfDropzone && pdfInput) {
  pdfDropzone.addEventListener('click', () => pdfInput.click());
  pdfDropzone.addEventListener('dragover', e => { e.preventDefault(); pdfDropzone.classList.add('dragover'); });
  pdfDropzone.addEventListener('dragleave', () => pdfDropzone.classList.remove('dragover'));
  pdfDropzone.addEventListener('drop', e => {
    e.preventDefault();
    pdfDropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length) uploadPdf(e.dataTransfer.files[0]);
  });
  pdfInput.addEventListener('change', e => { if (e.target.files.length) uploadPdf(e.target.files[0]); });
}

async function uploadPdf(file) {
  const formData = new FormData();
  formData.append('pdf', file);
  const item = document.createElement('div');
  item.className = 'doc-item';
  item.innerHTML = `<span>${file.name}</span><span class="pages">uploading…</span>`;
  if (docList) docList.appendChild(item);
  try {
    const res = await fetch('/api/rag/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.error) { item.querySelector('.pages').textContent = 'error'; return; }
    item.querySelector('.pages').textContent = data.pages + ' pages';
    addBotMessage(`Indexed **${data.source}** (${data.pages} pages, ${data.chunks_added} chunks). Ready for questions.`, []);
  } catch (err) {
    if (item.querySelector('.pages')) item.querySelector('.pages').textContent = 'failed';
  }
}

async function loadDocuments() {
  if (!docList) return;
  try {
    const res = await fetch('/api/rag/documents');
    const docs = await res.json();
    docList.innerHTML = '';
    docs.forEach(d => {
      const item = document.createElement('div');
      item.className = 'doc-item';
      item.innerHTML = `<span>${d.source}</span><span class="pages">${d.pages} pages</span>`;
      docList.appendChild(item);
    });
  } catch (e) {
    console.error('Failed to load documents', e);
  }
}

function addUserMessage(text) {
  if (!chatLog) return;
  const div = document.createElement('div');
  div.className = 'chat-msg user';
  div.innerHTML = `<p></p>`;
  div.querySelector('p').textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function addBotMessage(text, sources) {
  if (!chatLog) return;
  const div = document.createElement('div');
  div.className = 'chat-msg bot';
  const p = document.createElement('p');
  p.textContent = text;
  div.appendChild(p);
  if (sources && sources.length) {
    const srcWrap = document.createElement('div');
    srcWrap.className = 'sources';
    const seen = new Set();
    sources.forEach(s => {
      const key = s.source + s.page;
      if (seen.has(key)) return;
      seen.add(key);
      const chip = document.createElement('span');
      chip.className = 'src-chip';
      chip.textContent = `${s.source} · p.${s.page}`;
      srcWrap.appendChild(chip);
    });
    div.appendChild(srcWrap);
  }
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

function addTypingIndicator() {
  if (!chatLog) return;
  const div = document.createElement('div');
  div.className = 'chat-msg bot';
  div.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

if (chatForm && chatInput) {
  chatForm.addEventListener('submit', async e => {
    e.preventDefault();
    const question = chatInput.value.trim();
    if (!question) return;
    addUserMessage(question);
    chatInput.value = '';
    const typing = addTypingIndicator();

    try {
      const res = await fetch('/api/rag/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      if (typing) typing.remove();
      if (data.error) {
        addBotMessage(data.error, []);
        return;
      }
      addBotMessage(data.answer, data.sources);
    } catch (err) {
      if (typing) typing.remove();
      addBotMessage('Something went wrong: ' + err.message, []);
    }
  });
}
