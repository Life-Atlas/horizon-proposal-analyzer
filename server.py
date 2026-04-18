"""
CRUCIBLE API Server — FastAPI wrapper around crucible.py

Run: uvicorn server:app --host 0.0.0.0 --port 8000
Env: CRUCIBLE_CORS_ORIGINS (comma-separated), CRUCIBLE_MAX_MB
"""

import asyncio
import hashlib
import os
import tempfile
import time
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from crucible import (
    run_analysis, estimate_scores, format_report, __version__,
)

CORS_ORIGINS = os.getenv(
    "CRUCIBLE_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://crucible.winniio.io,https://crucible-app-phi.vercel.app"
).split(",")

MAX_FILE_SIZE = int(os.getenv("CRUCIBLE_MAX_MB", "25")) * 1024 * 1024

app = FastAPI(
    title="CRUCIBLE API",
    version=__version__,
    description="Horizon Europe proposal analyzer — 48+ anti-pattern detectors, "
                "PESTELED, EU Interop, Concept/Context/Crisis stress test",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# --- Rate limiting (in-memory, per-IP) ---
_rate_limits: dict[str, list[float]] = defaultdict(list)
RATE_WINDOWS = {
    "free": (3, 30 * 86400),      # 3 per 30 days
    "single": (10, 86400),         # 10 per day
    "pro": (100, 86400),           # 100 per day
    "enterprise": (1000, 86400),   # 1000 per day
}


def _check_rate_limit(client_ip: str, tier: str):
    max_requests, window = RATE_WINDOWS.get(tier, (3, 30 * 86400))
    now = time.time()
    key = f"{client_ip}:{tier}"
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]
    if len(_rate_limits[key]) >= max_requests:
        raise HTTPException(429, f"Rate limit exceeded for {tier} tier: {max_requests} per {window // 86400}d")
    _rate_limits[key].append(now)


# --- Result cache (by PDF hash) ---
_cache: dict[str, dict] = {}


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@app.post("/analyze")
async def analyze(
    request: Request,
    pdf: UploadFile = File(...),
    call_text: str = Form(default=""),
    tier: str = Form(default="free"),
    budget_mode: bool = Form(default=False),
    eic_pathfinder: bool = Form(default=False),
):
    if tier not in RATE_WINDOWS:
        raise HTTPException(400, f"Invalid tier: {tier}. Use: free, single, pro, enterprise")

    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files accepted")

    content = await pdf.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Max {MAX_FILE_SIZE // (1024 * 1024)}MB")

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip, tier)

    pdf_hash = hashlib.sha256(content).hexdigest()[:16]
    cache_key = f"{pdf_hash}:{bool(call_text.strip())}:{budget_mode}:{eic_pathfinder}"
    if cache_key in _cache:
        return _gate_response(_cache[cache_key], tier)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    call_path = None
    if call_text.strip():
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as ctmp:
            ctmp.write(call_text)
            call_path = ctmp.name

    try:
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(
            None, lambda: run_analysis(
                tmp_path, call_path, verbose=False,
                budget_mode=budget_mode, eic_pathfinder=eic_pathfinder,
            )
        )
        (result, model, smile_scores, pf_results, eic_scores,
         strategic_scores, future_scores, pestled_scores,
         interop_scores, stress_scores) = output
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

    composite = None
    if eic_scores and strategic_scores and future_scores and pestled_scores and interop_scores and stress_scores:
        eic_avg = eic_scores.get("_weighted_total", 0)
        strat_avg = strategic_scores.get("_weighted_avg", 0)
        future_avg = future_scores.get("_weighted_avg", 0)
        pestled_avg = pestled_scores.get("_weighted_avg", 0)
        interop_avg = interop_scores.get("_weighted_avg", 0)
        stress_avg = stress_scores.get("_overall", 0)
        composite_score = (eic_avg * 0.35 + strat_avg * 0.15 + future_avg * 0.10 +
                           pestled_avg * 0.15 + interop_avg * 0.15 + stress_avg * 0.10)
        composite = {
            "score": round(composite_score, 2),
            "grade": ("S" if composite_score >= 4.5 else "A" if composite_score >= 4.0 else
                      "B" if composite_score >= 3.5 else "C" if composite_score >= 3.0 else "D"),
            "components": {
                "eic_criteria": {"weight": 0.35, "score": round(eic_avg, 2)},
                "strategic": {"weight": 0.15, "score": round(strat_avg, 2)},
                "future_readiness": {"weight": 0.10, "score": round(future_avg, 2)},
                "pestled": {"weight": 0.15, "score": round(pestled_avg, 2)},
                "eu_interop": {"weight": 0.15, "score": round(interop_avg, 2)},
                "stress_test": {"weight": 0.10, "score": round(stress_avg, 2)},
            },
        }

    full_response = {
        "tool": "CRUCIBLE",
        "version": __version__,
        "file": pdf.filename,
        "tier": "enterprise",
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
        "composite": composite,
        "smile_coverage": smile_scores,
        "eic_pathfinder_scores": eic_scores,
        "strategic_dimensions": strategic_scores,
        "future_tech_radar": future_scores,
        "pestled_scores": pestled_scores,
        "eu_interop_scores": interop_scores,
        "stress_test_scores": stress_scores,
        "pre_flight": [
            {"id": q["id"], "question": q["question"], "weight": q["weight"], "result": r}
            for q, r in (pf_results or [])
        ],
        "findings": findings_data,
        "finding_count": len(result.findings),
    }

    _cache[cache_key] = full_response

    return _gate_response(full_response, tier)


def _gate_response(full: dict, tier: str) -> dict:
    """Apply tier gating to a full analysis response."""
    resp = {**full, "tier": tier}

    if tier == "free":
        resp["findings"] = [f for f in full["findings"] if f["layer"] == 4][:5]
        resp["scores"] = None
        resp["total"] = None
        resp["smile_coverage"] = None
        resp["eic_pathfinder_scores"] = None
        resp["strategic_dimensions"] = None
        resp["future_tech_radar"] = None
        resp["pestled_scores"] = None
        resp["eu_interop_scores"] = None
        resp["stress_test_scores"] = None
        resp["composite"] = None
    elif tier == "single":
        resp["findings"] = full["findings"][:25]
        resp["eic_pathfinder_scores"] = None
        resp["strategic_dimensions"] = None
        resp["future_tech_radar"] = None
        resp["pestled_scores"] = None
        resp["eu_interop_scores"] = None
        resp["stress_test_scores"] = None
        resp["composite"] = None

    return resp
