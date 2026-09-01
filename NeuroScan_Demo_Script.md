# NeuroScan Clinical Suite — Demo & Pitch Script
*Target: 3–5 minutes, regional round presentation*

---

## 1. The Problem (30 seconds)

> "Brain tumor diagnosis from MRI scans is slow and heavily dependent on radiologist availability — especially outside major cities. A radiologist has to manually classify the tumor type, locate it, measure it, cross-check treatment guidelines, and write up a report — for every single patient. NeuroScan Clinical Suite compresses that entire workflow into minutes, while keeping the doctor fully in control of every decision."

---

## 2. The Solution — 3-Stage AI Pipeline (30 seconds)

> "NeuroScan Clinical Suite runs three fine-tuned ONNX models in sequence on every MRI scan:
> 1. **Classification** — is there a tumor, and what type (glioma, meningioma, pituitary)?
> 2. **Detection** — where exactly is it, with a bounding box?
> 3. **Segmentation** — precise pixel-level area and shape.
>
> On top of that, we layered a multimodal AI assistant — Qwen 3.6-27B — for two things a pure computer-vision model can't do: answering free-form questions about a specific region of the scan, and drafting a structured treatment advisory note grounded in uploaded hospital guidelines."

---

## 3. Live Demo (2–2.5 minutes) — **this is the core of your pitch**

**Do this live, don't just show screenshots — judges want to see it work in real time.**

| Step | What to do | What to say |
|---|---|---|
| 1 | Upload a pre-tested MRI scan (use one of your known-good test images) | "I'll upload a real brain MRI scan now." |
| 2 | Click "Execute AI Analysis" | Let the scan-sweep animation play — pause a beat, let it land. "Watch the pipeline run — classification, then localization, then segmentation." |
| 3 | Point to Classification card | "Glioma, 100% confidence, in about 100 milliseconds." |
| 4 | Point to detection + segmentation overlay | "Here's exactly where it is, and its precise area — 1.5% of the scan, measured to the pixel." |
| 5 | Draw a crop box on the tumor region, ask a question (e.g. "tell me about this area") | "Now the doctor can interrogate any specific region directly — this goes to a vision-language model, not just the pixel data." Read the answer out loud briefly. |
| 6 | Click "Generate Treatment Advisory" | "And here's the part that saves the most time — a structured advisory note combining the scan findings with any hospital protocol PDFs we've uploaded, in under 15 seconds." |
| 7 | Click "Download PDF Report" | "One click, and this becomes an official one-page clinical report ready for the patient's file." |

**If something is slow or fails live:** stay calm, say "let me show you the version I ran earlier" and have a backup screen-recording ready. Judges respect composure over panic far more than a perfect run.

---

## 4. The Responsible-AI Message (20 seconds) — judges specifically look for this

> "Every single output in this system — the classification, the region answer, the treatment note — ends with the same reminder: this is AI-assisted support, and the physician makes the final call. We're not trying to replace the radiologist. We're trying to give them a second pair of eyes that never gets tired."

---

## 5. What's Next / Roadmap (20 seconds)

> "Right now this is a validated proof-of-concept running on Groq's Qwen 3.6-27B. The roadmap to a real clinical product includes DICOM support, regulatory clearance through DRAP, and clinical validation studies with a partner hospital — we see this starting as a pilot with 1–2 diagnostic centers before wider rollout."

---

## Anticipated Judge Questions — Prepared Answers

**Q: "What's the accuracy of your models?"**
> "The classifier is running at very high confidence on our test set — but to be transparent, this hasn't gone through a formal clinical validation study yet. That's explicitly the next step before any real deployment."

**Q: "Have you tested this on real hospital data?"**
> "Not yet — we've used a public brain MRI dataset for training and testing. Getting a data-sharing agreement with a hospital for real validation is part of our next-phase roadmap."

**Q: "What's your regulatory path?"**
> "In Pakistan that would be DRAP registration as clinical decision-support software. We're positioning this explicitly as decision-support, not autonomous diagnosis, which is a lighter regulatory category than a standalone diagnostic device."

**Q: "Why Qwen instead of [X model]?"**
> "We evaluated a few options. Qwen 3.6-27B is publicly available on Groq without enterprise gating, genuinely multimodal, and gave us reliable structured output for both the region Q&A and the treatment advisory — and it's aligned with this hackathon's Alibaba Cloud ecosystem."

**Q: "What happens if the AI is wrong?"**
> "Every output carries an explicit disclaimer, and nothing in the system writes a diagnosis — it writes considerations for the doctor to review. The doctor's signature line is a required part of the PDF report before it becomes an official document."

**Q: "Is patient data secure?"**
> "In this prototype, data stays local to wherever the app is hosted — no third-party storage beyond the AI API calls for text/vision reasoning. A production version would need HIPAA/DRAP-equivalent encryption, access controls, and audit logging, which is on the roadmap."

---

## Pre-Demo Checklist

- [ ] Test the full flow end-to-end on the actual machine/network you'll demo on, same day
- [ ] Check Groq quota/usage on console.groq.com before going on stage
- [ ] Have 2–3 known-good test MRI images ready (don't hunt for a file live)
- [ ] Have a backup screen-recording in case of live network issues
- [ ] Confirm the GitHub repo is public and the link works
- [ ] Time yourself once — aim to land under 5 minutes with room for Q&A
