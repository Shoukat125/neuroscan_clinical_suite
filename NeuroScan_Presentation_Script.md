# NeuroScan — Presentation Script (Cue Cards)
*Target: 3–5 minutes total. This is YOUR speaking script — not for the judges.*

---

### Slide 1 — Title
*(5 sec, just land on stage)*
> "NeuroScan Clinical Suite — AI-assisted brain tumor analysis, from MRI to report in minutes."

---

### Slide 2 — The Problem *(30 sec)*
> "Brain tumor diagnosis is slow and heavily dependent on radiologist availability — especially outside major cities. Every scan means manually classifying the tumor, locating it, measuring it, cross-checking guidelines, and writing a report. NeuroScan compresses that into minutes, while the doctor stays fully in control."

---

### Slide 3 — 3-Stage Pipeline *(30 sec)*
> "Three fine-tuned models run on every scan: Classification — is there a tumor, and what type. Detection — exactly where it is. Segmentation — precise pixel-level area. On top of that, a multimodal AI assistant, Qwen 3.6-27B, answers free-form questions about any region and drafts a treatment advisory grounded in uploaded hospital guidelines."

---

### Slide 4 — Live Demo *(2–2.5 min — the core of the pitch)*
**Do this live. Don't just show screenshots.**

| # | Action | Say |
|---|--------|-----|
| 1 | Upload a pre-tested MRI scan | "I'll upload a real brain MRI scan now." |
| 2 | Click Analyze, let animation play | "Watch the pipeline run — classification, then localization, then segmentation." |
| 3 | Point to classification result | "Glioma, ~100% confidence, in about 100 milliseconds." |
| 4 | Point to detection + segmentation overlay | "Here's exactly where it is, and its precise area — measured to the pixel." |
| 5 | Draw a region box, ask a question | "The doctor can interrogate any specific region directly — this goes to a vision-language model." |
| 6 | Click Treatment Advisory | "A structured advisory note combining scan findings with hospital protocol PDFs, in under 15 seconds." |
| 7 | Download PDF Report | "One click, and this becomes an official clinical report for the patient's file." |

**If something fails live:** stay calm — "Let me show you the version I ran earlier," switch to backup recording.

---

### Slide 5 — Responsible AI *(20 sec)*
> "Every output — classification, region answer, treatment note — ends with the same reminder: this is AI-assisted support, and the physician makes the final call. We're giving them a second pair of eyes that never gets tired."

---

### Slide 6 — Built On *(15 sec)*
> "Flask backend, three ONNX models, Groq's Qwen 3.6-27B for reasoning, containerized with Docker, deployed on Alibaba Cloud."

---

### Slide 7 — Roadmap *(20 sec)*
> "This is a validated proof-of-concept. Next: DICOM support, DRAP regulatory clearance, clinical validation with a partner hospital, then a pilot with 1–2 diagnostic centers."

---

### Slide 8 — Thank You *(land it, open floor)*
> "Thank you — happy to take questions."

---

## Backup: Anticipated Judge Questions

**Accuracy?** → "Very high confidence on our test set — but no formal clinical validation yet. That's the explicit next step."

**Real hospital data?** → "Not yet — public MRI dataset for now. A hospital data-sharing agreement is next-phase."

**Regulatory path?** → "DRAP registration as clinical decision-support software — a lighter category than a standalone diagnostic device."

**Why Qwen?** → "Publicly available on Groq, genuinely multimodal, reliable structured output, and aligned with this hackathon's Alibaba Cloud ecosystem."

**If the AI is wrong?** → "Every output carries a disclaimer. Nothing writes a diagnosis — only considerations for the doctor. The signature line is mandatory before the PDF is official."

**Patient data security?** → "Stays local to the host in this prototype — no third-party storage beyond the AI API calls. Production would need HIPAA/DRAP-equivalent encryption, access control, and audit logging."

---

## Pre-Demo Checklist
- [ ] Test full flow end-to-end on the actual demo machine/network, same day
- [ ] Check Groq quota on console.groq.com before going on stage
- [ ] 2–3 known-good test MRI images ready (don't hunt for a file live)
- [ ] Backup screen-recording ready
- [ ] Time yourself once — land under 5 minutes with room for Q&A
