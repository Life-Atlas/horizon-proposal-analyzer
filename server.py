"""
CRUCIBLE API Server — FastAPI wrapper around crucible.py

Run: uvicorn server:app --host 0.0.0.0 --port 8000
"""

import tempfile
import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from crucible import run_analysis, estimate_scores, __version__

app = FastAPI(
    title="CRUCIBLE API",
    version=__version__,
    description="Horizon Europe proposal analyzer — 48+ anti-pattern detectors",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://crucible.winniio.io"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 25 * 1024 * 1024


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@app.post("/analyze")
async def analyze(
    pdf: UploadFile = File(...),
    call_text: str = Form(default=""),
    tier: str = Form(default="free"),
    budget_mode: bool = Form(default=False),
    eic_pathfinder: bool = Form(default=False),
):
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files accepted")

    content = await pdf.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Max {MAX_FILE_SIZE // (1024*1024)}MB")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    call_path = None
    if call_text.strip():
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as ctmp:
            ctmp.write(call_text)
            call_path = ctmp.name

    try:
        output = run_analysis(
            tmp_path, call_path, verbose=False,
            budget_mode=budget_mode, eic_pathfinder=eic_pathfinder,
        )
        result, model, smile_scores, pf_results = output[0], output[1], output[2], output[3]
        eic_scores, strategic_scores, future_scores = output[4], output[5], output[6]
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")
    finally:
        os.unlink(tmp_path)
        if call_path:
            os.unlink(call_path)

    scores = estimate_scores(result, model)

    findings_data = [
        {
            "pattern": f.pattern,
            "severity": f.severity,
            "page": f.page,
            "text": f.text,
            "suggestion": f.suggestion,
            "category": f.category,
            "layer": f.layer,
        }
        for f in result.findings
    ]

    if tier == "free":
        findings_data = [f for f in findings_data if f["layer"] == 4][:10]
        smile_scores = None
        eic_scores = None
        strategic_scores = None
        future_scores = None

    return {
        "tool": "CRUCIBLE",
        "version": __version__,
        "file": pdf.filename,
        "tier": tier,
        "call_provided": bool(call_text.strip()),
        "pages": model.total_pages,
        "model": {
            "acronym": model.acronym,
            "title": model.title,
            "duration_months": model.duration_months,
            "call_id": model.call_id,
            "action_type": model.action_type,
            "partner_count": len(model.partners),
            "wp_count": len(model.work_packages),
            "deliverable_count": len(model.deliverables),
            "milestone_count": len(model.milestones),
            "citation_count": len(model.citations_found),
            "kpi_count": len(model.kpis_found),
            "budget_total": model.budget_total,
            "budget_eu": model.budget_eu,
        },
        "scores": scores,
        "total": round(sum(scores.values()), 1),
        "smile_coverage": smile_scores,
        "eic_pathfinder_scores": eic_scores,
        "strategic_dimensions": strategic_scores,
        "pre_flight": [
            {"id": q["id"], "question": q["question"], "weight": q["weight"], "result": r}
            for q, r in (pf_results or [])
        ],
        "findings": findings_data,
        "finding_count": len(result.findings),
    }
