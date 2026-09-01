"""Official PDF clinical report export (Upgrade 5).

Builds a single-click downloadable PDF containing patient details, the
uploaded scan (and overlay if a tumor was found), AI measurements, and a
doctor signature line — for attaching to a patient's hospital record.
"""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

ACCENT = colors.HexColor("#7A1F2B")
MUTED = colors.HexColor("#8A6B5A")
BORDER = colors.HexColor("#E8DDD3")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", fontSize=15, leading=18, textColor=ACCENT, spaceAfter=1))
    styles.add(ParagraphStyle(name="ReportSub", fontSize=8.5, textColor=MUTED, spaceAfter=6))
    styles.add(ParagraphStyle(name="SectionHead", fontSize=10.5, leading=13, textColor=ACCENT, spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="Body", fontSize=9, leading=12.5))
    styles.add(ParagraphStyle(name="Small", fontSize=7.5, textColor=MUTED, leading=10))
    styles.add(ParagraphStyle(name="Centered", parent=styles["Body"], alignment=TA_CENTER, fontSize=8))
    return styles


def generate_pdf_report(patient, analysis, image_path=None, overlay_path=None, notes=None):
    """Build the PDF and return raw bytes — laid out to fit a single A4 page.

    patient: dict with name, patient_id, age, referring_doctor (any may be blank)
    analysis: the same-shaped dict /api/analyze / run_full_analysis returns
    image_path / overlay_path: local filesystem paths to embed (optional)
    notes: optional free-text clinical notes to include
    """
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=13 * mm, bottomMargin=12 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
    )
    story = []

    # ---- Header ----
    story.append(Paragraph("NeuroScan Clinical Suite — Clinical Report", styles["ReportTitle"]))
    story.append(Paragraph(
        f"Generated {datetime.now().strftime('%d/%m/%Y %H:%M')} · AI-assisted analysis for physician review",
        styles["ReportSub"],
    ))
    story.append(HRFlowable(width="100%", color=BORDER, thickness=1))
    story.append(Spacer(1, 6))

    # ---- Patient details ----
    story.append(Paragraph("Patient Details", styles["SectionHead"]))
    patient = patient or {}
    p_rows = [
        ["Patient Name", patient.get("name") or "—", "Patient / MRN ID", patient.get("patient_id") or "—"],
        ["Age", patient.get("age") or "—", "Referring Doctor", patient.get("referring_doctor") or "—"],
    ]
    p_table = Table(p_rows, colWidths=[32 * mm, 55 * mm, 38 * mm, 53 * mm])
    p_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(p_table)

    # ---- Scan images (side by side, compact) ----
    cls = (analysis or {}).get("classification") or {}
    story.append(Paragraph("Scan Images", styles["SectionHead"]))
    img_row = []
    if image_path:
        img_row.append(RLImage(image_path, width=52 * mm, height=52 * mm, kind="proportional"))
    if overlay_path:
        img_row.append(RLImage(overlay_path, width=52 * mm, height=52 * mm, kind="proportional"))
    if img_row:
        cap_row = [Paragraph("Uploaded scan", styles["Centered"])]
        if overlay_path:
            cap_row.append(Paragraph("AI overlay (detection + segmentation)", styles["Centered"]))
        col_w = 178 / max(len(img_row), 1) * mm
        img_table = Table([img_row, cap_row], colWidths=[col_w] * len(img_row))
        img_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(img_table)
    else:
        story.append(Paragraph("No scan image available.", styles["Body"]))

    # ---- Classification (compact — headline + one-line breakdown, no big table) ----
    story.append(Paragraph("AI Findings — Classification", styles["SectionHead"]))
    verdict = cls.get("label", "unknown")
    conf = cls.get("confidence")
    conf_txt = f"{conf * 100:.1f}%" if conf is not None else "—"
    story.append(Paragraph(
        f"<b>Result:</b> {'No tumor detected' if not cls.get('is_tumor') else verdict.title()} "
        f"&nbsp;&nbsp;<b>Confidence:</b> {conf_txt}",
        styles["Body"],
    ))
    scores = cls.get("all_scores") or {}
    if scores:
        ordered = sorted(scores.items(), key=lambda kv: -kv[1])
        breakdown = " · ".join(f"{k.title()}: {v * 100:.1f}%" for k, v in ordered)
        story.append(Paragraph(f"<font color='#8A6B5A'>{breakdown}</font>", styles["Small"]))

    # ---- Detection + Segmentation (measurements) ----
    seg = (analysis or {}).get("segmentation")
    det = (analysis or {}).get("detection")
    if seg or det:
        story.append(Paragraph("AI Findings — Location &amp; Size", styles["SectionHead"]))
        rows = [["Region", "Confidence", "Area (px)", "Area (% of scan)"]]
        segments = (seg or {}).get("segments") or []
        if segments:
            for s in segments:
                rows.append([
                    s["label"].title(), f"{s['confidence'] * 100:.1f}%",
                    f"{s['area_px']:,}", f"{s['area_pct']}%",
                ])
        else:
            rows.append(["—", "—", "—", "—"])
        t = Table(rows, colWidths=[45 * mm, 35 * mm, 35 * mm, 43 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(t)

    # ---- Clinical notes ----
    if notes:
        story.append(Paragraph("Additional Notes", styles["SectionHead"]))
        story.append(Paragraph(notes.replace("\n", "<br/>"), styles["Body"]))

    # ---- Disclaimer ----
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report was generated by an AI decision-support system and is intended to assist, "
        "not replace, clinical judgment. All findings must be reviewed and confirmed by a "
        "qualified physician before any diagnostic or treatment decision.",
        styles["Small"],
    ))

    # ---- Signature line ----
    story.append(Spacer(1, 14))
    sig_table = Table(
        [["_" * 34, "_" * 34], ["Reviewing Physician Signature", "Date"]],
        colWidths=[80 * mm, 80 * mm],
    )
    sig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 1), (-1, 1), MUTED),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
    ]))
    story.append(sig_table)

    doc.build(story)
    return buf.getvalue()
