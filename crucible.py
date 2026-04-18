#!/usr/bin/env python3
"""
C.R.U.C.I.B.L.E. v4.0.0
Consortia Review Under Controlled Interrogation — Before Live Evaluation

Two-pass full-proposal analyzer for Horizon Europe.
Now with EIC Pathfinder Open call-specific evaluation and pre-flight checklist.

Pass 0: PRE-FLIGHT — 10 gatekeeper questions before analysis runs
Pass 1: EXTRACTION — build a structured ProposalModel from the entire PDF
Pass 2: ANALYSIS — four layers
  Layer 1: STRUCTURAL INTEGRITY  — cross-document consistency
  Layer 2: CALL ALIGNMENT        — proposal vs call requirements
  Layer 3: FIELD & SMILE         — field awareness + SMILE methodology
  Layer 4: ANTI-PATTERNS         — 45+ mechanical checks
Pass 3: STRATEGIC SCORING — time to market, innovation depth, partnerships, etc.

Usage:
  python crucible.py proposal.pdf
  python crucible.py proposal.pdf --call call_text.txt
  python crucible.py proposal.pdf --call call_text.txt --verbose
  python crucible.py proposal.pdf --call call_text.txt --json results.json
  python crucible.py proposal.pdf --budget
  python crucible.py proposal.pdf --eic-pathfinder  # EIC Pathfinder Open mode

License: MIT — WINNIIO AB / Life Atlas
"""

import sys
import re
import json
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

try:
    import fitz
except ImportError:
    print("ERROR: pymupdf required. Install with: pip install pymupdf")
    sys.exit(1)

__version__ = "4.0.0"


# ============================================================
# PRE-FLIGHT CHECKLIST — 10 gatekeeper questions
# ============================================================

PRE_FLIGHT_CHECKLIST = [
    {
        "id": 1,
        "question": "Do you have the CALL TEXT loaded?",
        "why": "Without the call text, CRUCIBLE cannot verify terminology alignment, expected outcome coverage, or TRL match. You're grading an exam without the answer key.",
        "weight": "BLOCKER",
        "check": lambda model, call_text: call_text is not None,
    },
    {
        "id": 2,
        "question": "Is the PAGE COUNT within the call limit?",
        "why": "Pages beyond the limit are REMOVED by the system — evaluators never see them. EIC Pathfinder Open: 22 pages for Part B.",
        "weight": "BLOCKER",
        "check": lambda model, call_text: (
            model.part_b_pages <= 22 if model.part_b_pages > 0 else None
        ),
    },
    {
        "id": 3,
        "question": "Does the proposal pass all 3 GATEKEEPERS?",
        "why": "EIC Pathfinder rejects outright if missing: (1) convincing long-term vision of radically new technology, (2) concrete novel science-towards-technology breakthrough, (3) high-risk/high-gain research approach.",
        "weight": "BLOCKER",
        "check": lambda model, call_text: None,  # manual check
    },
    {
        "id": 4,
        "question": "Are TRL targets aligned with call specification?",
        "why": "EIC Pathfinder Open: starting TRL 2, exit TRL 3-4. Claiming TRL 5+ exits signals wrong call.",
        "weight": "CRITICAL",
        "check": lambda model, call_text: None,  # checked in Layer 2
    },
    {
        "id": 5,
        "question": "Is there a COORDINATOR with institutional credibility?",
        "why": "A 1-person startup coordinating EUR 3-4M is a near-fatal evaluator red flag. Universities or large companies coordinate.",
        "weight": "CRITICAL",
        "check": lambda model, call_text: None,  # checked in structural
    },
    {
        "id": 6,
        "question": "Does the consortium have >=3 partners from >=3 eligible countries?",
        "why": "Horizon Europe minimum eligibility requirement. Fail = desk rejection.",
        "weight": "BLOCKER",
        "check": lambda model, call_text: (
            len(model.partners) >= 3 and
            len(set(p.country for p in model.partners if p.country)) >= 3
            if model.partners else None
        ),
    },
    {
        "id": 7,
        "question": "Is the budget within call limits (EUR 1-4M for Pathfinder Open)?",
        "why": "Over EUR 4M = automatic rejection. Under EUR 1M signals insufficient ambition.",
        "weight": "CRITICAL",
        "check": lambda model, call_text: (
            1_000_000 <= model.budget_eu <= 4_000_000
            if model.budget_eu > 0 else None
        ),
    },
    {
        "id": 8,
        "question": "Are there NAMED KEY PERSONNEL with relevant track records?",
        "why": "EIC evaluators check for named researchers with publication records. 'TBD' or 'to be hired' for leads = score penalty.",
        "weight": "HIGH",
        "check": lambda model, call_text: bool(model.researchers),
    },
    {
        "id": 9,
        "question": "Is there a commitment letter from the coordinator?",
        "why": "Large-company coordinators need documented commitment. Without it, evaluators question whether the company actually agreed.",
        "weight": "HIGH",
        "check": lambda model, call_text: None,  # manual check
    },
    {
        "id": 10,
        "question": "Are ALL outputs open-access (Pathfinder Open Science requirement)?",
        "why": "EIC Pathfinder explicitly requires open science practices: pre-prints, open data, open-source code. Proprietary outputs penalised.",
        "weight": "MEDIUM",
        "check": lambda model, call_text: any(
            term in model.full_text.lower()
            for term in ['open access', 'open-access', 'open source', 'open-source',
                         'cc-by', 'apache 2', 'zenodo', 'arxiv']
        ) if model.full_text else None,
    },
]


# ============================================================
# EIC PATHFINDER OPEN — CALL-SPECIFIC EVALUATION
# ============================================================

EIC_PATHFINDER_CRITERIA = {
    "Excellence": {
        "weight": 0.50,
        "threshold": 4.0,
        "sub_criteria": {
            "1a_vision": {
                "name": "Long-term vision",
                "question": "How convincing is the vision of a radically new technology?",
                "markers_positive": [
                    "radically new", "paradigm", "transformative", "foundational",
                    "computational primitive", "new class of", "first-of-its-kind",
                    "no equivalent exists", "game-changing",
                ],
                "markers_negative": [
                    "incremental", "improvement", "extension of", "building on existing",
                    "minor advancement",
                ],
            },
            "1b_breakthrough": {
                "name": "Science-towards-technology breakthrough",
                "question": "How concrete, novel, and ambitious is the proposed breakthrough?",
                "markers_positive": [
                    "first automated", "first validated", "first open-source",
                    "first demonstration", "no prior", "novel contribution",
                    "beyond state of the art", "proof of principle",
                ],
                "markers_negative": [
                    "well-known", "established method", "standard approach",
                ],
            },
            "1c_objectives": {
                "name": "Objectives and methodology",
                "question": "How concrete/plausible are objectives? How sound is methodology?",
                "markers_positive": [
                    "high-risk/high-gain", "proof of principle", "fallback",
                    "alternative direction", "risk mitigation", "validation protocol",
                    "statistical", "cross-validation", "confidence interval",
                    "open science",
                ],
                "markers_negative": [
                    "will develop", "will create", "will implement",  # vague verbs without method
                ],
            },
            "1d_interdisciplinary": {
                "name": "Interdisciplinarity",
                "question": "How relevant is interdisciplinary approach from distant disciplines?",
                "markers_positive": [
                    "interdisciplinary", "cross-disciplinary", "traditionally separate",
                    "computer vision", "materials science", "rf propagation",
                    "privacy engineering", "humanitarian",
                ],
                "markers_negative": [],
            },
        },
    },
    "Impact": {
        "weight": 0.30,
        "threshold": 3.5,
        "sub_criteria": {
            "2a_long_term_impact": {
                "name": "Long-term impact",
                "question": "How significant are potential transformative effects on economy/society?",
                "markers_positive": [
                    "eur", "billion", "trillion", "market",
                    "reconstruction", "5g", "6g", "urban air mobility",
                    "regulatory", "policy", "green deal", "digital decade",
                ],
                "markers_negative": [],
            },
            "2b_innovation_potential": {
                "name": "Innovation potential",
                "question": "Potential for disruptive innovations? IP protection? Key actor involvement?",
                "markers_positive": [
                    "disruptive", "new market", "exploitation", "ip protection",
                    "patent", "license", "spin-off", "letter of intent",
                    "first customer", "revenue", "commercial",
                ],
                "markers_negative": [
                    "results will be", "partners will", "will integrate",  # generic exploitation
                ],
            },
            "2c_communication": {
                "name": "Communication and dissemination",
                "question": "Measures for scientific publications, communication, awareness?",
                "markers_positive": [
                    "publication", "conference", "workshop", "open data",
                    "zenodo", "ieee dataport", "community", "hackathon",
                    "standards contribution", "3gpp", "etsi", "ogc",
                ],
                "markers_negative": [],
            },
        },
    },
    "Implementation": {
        "weight": 0.20,
        "threshold": 3.0,
        "sub_criteria": {
            "3a_work_plan": {
                "name": "Work plan quality",
                "question": "How coherent/effective are WPs, tasks, milestones, risk mitigation?",
                "markers_positive": [
                    "work package", "task", "deliverable", "milestone",
                    "risk", "mitigation", "fallback", "contingency",
                    "phase", "gate",
                ],
                "markers_negative": [
                    "tbd", "to be determined", "to be defined",
                ],
            },
            "3b_resources": {
                "name": "Resource allocation",
                "question": "How appropriate is allocation of person-months and costs?",
                "markers_positive": [
                    "person-month", "pm", "fte", "equipment",
                    "budget", "personnel", "subcontracting",
                ],
                "markers_negative": [],
            },
            "3c_consortium": {
                "name": "Consortium quality",
                "question": "Do all members have necessary capacity and expertise?",
                "markers_positive": [
                    "track record", "prior project", "publication",
                    "experience", "expertise", "key personnel",
                    "named researcher", "deputy", "commitment letter",
                ],
                "markers_negative": [
                    "to be hired", "tbd", "to be recruited",
                ],
            },
        },
    },
}


# ============================================================
# STRATEGIC DIMENSIONS — beyond the call criteria
# ============================================================

STRATEGIC_DIMENSIONS = {
    "time_to_market": {
        "name": "Time to Market",
        "description": "How quickly can results become products/services?",
        "markers": ["m36", "m42", "m48", "first customer", "pilot", "commercial",
                     "revenue", "saas", "licensing", "exploitation"],
        "weight": 15,
    },
    "innovation_depth": {
        "name": "Innovation Depth",
        "description": "How genuinely novel is the core contribution?",
        "markers": ["first", "no prior", "novel", "new computational",
                     "paradigm", "proof of principle", "radically new",
                     "beyond state of the art", "foundational"],
        "weight": 20,
    },
    "partnership_strength": {
        "name": "Partnership Strength",
        "description": "How credible and committed are the partners?",
        "markers": ["commitment letter", "prior collaboration", "track record",
                     "key personnel", "named researcher", "deputy",
                     "commercial engine", "200+ operator"],
        "weight": 15,
    },
    "defensibility": {
        "name": "Defensibility / Moat",
        "description": "What prevents competitors from replicating?",
        "markers": ["network effect", "open-source", "benchmark dataset",
                     "standards contribution", "first-mover",
                     "accumulating", "cross-validated"],
        "weight": 10,
    },
    "market_size": {
        "name": "Market Size & Clarity",
        "description": "Is the addressable market credibly sized?",
        "markers": ["eur", "billion", "trillion", "addressable",
                     "segment", "target", "sub-segment"],
        "weight": 10,
    },
    "team_execution": {
        "name": "Team Execution Capability",
        "description": "Can this team actually deliver?",
        "markers": ["consultant", "fte", "hire", "operational capacity",
                     "prior project", "delivered", "validated",
                     "testbed", "deployed"],
        "weight": 10,
    },
    "policy_alignment": {
        "name": "EU Policy Alignment",
        "description": "How well does this serve EU strategic priorities?",
        "markers": ["green deal", "digital decade", "ukraine",
                     "reconstruction", "sovereignty", "open science",
                     "u-space", "easa", "gdpr", "fair"],
        "weight": 10,
    },
    "wow_factor": {
        "name": "Wow Factor / Memorability",
        "description": "Will an evaluator remember this proposal after reading 50?",
        "markers": ["pagerank for physical space", "computational primitive",
                     "spatial index", "no equivalent exists",
                     "contested environment", "post-conflict"],
        "weight": 10,
    },
}


# ============================================================
# FUTURE TECH RADAR — score against where the world WILL BE, not where it IS
# Three horizons: 3yr (2029), 5yr (2031), 10yr (2036)
# Projects should align with future reality, not current reality.
# x100 thinking: what happens when this tech is 100x cheaper/faster/smaller?
# It is OK to not score high on everything — conscious positioning matters.
# ============================================================

FUTURE_TECH_RADAR = {
    # --- 3-YEAR HORIZON (2029) ---
    "edge_native": {
        "name": "Edge-Native / Local-First",
        "horizon": "3yr",
        "horizon_desc": "2028-2030: Edge AI becomes default. Cloud-first is legacy.",
        "markers": ["edge", "local-first", "on-device", "edge compute", "fog",
                     "sovereignty", "process locally", "sync later", "latency"],
        "weight": 12,
    },
    "physical_ai": {
        "name": "Physical AI / Embodied Intelligence",
        "horizon": "3yr",
        "horizon_desc": "2028-2030: AI moves from digital to physical world (robotics, spatial computing, digital twins).",
        "markers": ["physical", "spatial", "3d reconstruction", "gaussian splat",
                     "digital twin", "drone", "uav", "sensor", "lidar", "photogrammetry",
                     "embodied", "real-world"],
        "weight": 15,
    },
    "small_models_lqm": {
        "name": "Small/Local Models + LQMs",
        "horizon": "3yr",
        "horizon_desc": "2028-2030: Edge-deployable models replace cloud LLMs. Physics-based LQMs outperform statistical models.",
        "markers": ["local model", "small model", "quantitative model", "physics-based",
                     "mechanistic", "simulation", "ray tracing", "not statistical",
                     "physics, not statistics"],
        "weight": 10,
    },
    "hpc_quantum": {
        "name": "HPC + Quantum Enablement",
        "horizon": "3yr",
        "horizon_desc": "2029-2032: Quantum-classical hybrid pipelines for simulation. GPU clusters for 3D reconstruction.",
        "markers": ["hpc", "quantum", "gpu", "parallel", "compute cluster",
                     "high-performance", "accelerat"],
        "weight": 5,
    },
    "agentic_ai": {
        "name": "AI Agentic Stacks",
        "horizon": "3yr",
        "horizon_desc": "2027-2029: Autonomous AI agents orchestrate multi-step workflows. Human-on-the-loop replaces human-in-the-loop.",
        "markers": ["agent", "autonomous", "orchestrat", "pipeline", "automated",
                     "workflow", "multi-step", "self-improving", "feedback loop"],
        "weight": 10,
    },
    "harvest_now_decrypt_later": {
        "name": "Post-Quantum / HNDL Protection",
        "horizon": "3yr",
        "horizon_desc": "2028-2030: HNDL attacks make current encryption vulnerable. Post-quantum crypto becomes mandatory.",
        "markers": ["quantum-secure", "post-quantum", "harvest now decrypt later",
                     "pqc", "kyber", "dilithium", "lattice-based"],
        "weight": 5,
    },
    "explainable_ai": {
        "name": "Explainable + Understandable AI",
        "horizon": "3yr",
        "horizon_desc": "2027-2029: EU AI Act enforces explainability. Black-box models face regulatory barriers.",
        "markers": ["explainable", "interpretable", "transparent", "understandable",
                     "audit trail", "physics-based", "not black box", "white box",
                     "mechanistic", "causal"],
        "weight": 10,
    },
    "actor_network": {
        "name": "Actor-Network / Sociotechnical",
        "horizon": "3yr",
        "horizon_desc": "2027-2030: Systems thinking replaces reductionism. ANT gains traction in EU policy.",
        "markers": ["actor-network", "sociotechnical", "stakeholder", "ecosystem",
                     "boundary object", "translation", "network effect",
                     "interdisciplinary", "cross-disciplinary"],
        "weight": 8,
    },
    "secure_resilient": {
        "name": "Security + Resilience by Design",
        "horizon": "3yr",
        "horizon_desc": "2027-2029: Zero-trust and resilience become architectural requirements, not add-ons.",
        "markers": ["security", "resilience", "gdpr", "privacy", "differential privacy",
                     "zero-trust", "supply chain", "contested", "post-conflict",
                     "threat model", "attack surface"],
        "weight": 8,
    },
    "open_sovereign": {
        "name": "Open + Sovereign Infrastructure",
        "horizon": "3yr",
        "horizon_desc": "2028-2030: EU digital sovereignty mandates open standards, open source, data sovereignty.",
        "markers": ["open source", "open-source", "open data", "sovereign",
                     "apache", "cc-by", "fair", "interoperable", "no lock-in",
                     "modular", "swappable"],
        "weight": 10,
    },
    "spatial_web": {
        "name": "Spatial Web / Web 4.0",
        "horizon": "3yr",
        "horizon_desc": "2028-2032: Physical and digital worlds merge. Spatial indexing becomes infrastructure like DNS.",
        "markers": ["spatial", "3d", "gaussian", "mesh", "point cloud",
                     "citygml", "ifc", "ogc", "geospatial", "bim", "gis",
                     "spatial computing", "spatial index"],
        "weight": 12,
    },
    "drone_uam": {
        "name": "Drone Economy + UAM",
        "horizon": "3yr",
        "horizon_desc": "2028-2030: BVLOS drone operations become routine. UAM moves from prototype to infrastructure.",
        "markers": ["drone", "uav", "bvlos", "urban air mobility", "uam",
                     "u-space", "altitude", "corridor", "autonomous flight",
                     "easa"],
        "weight": 8,
    },
    # --- 5-YEAR HORIZON (2031) ---
    "digital_twin_federation": {
        "name": "Federated Digital Twins",
        "horizon": "5yr",
        "horizon_desc": "2030-2032: Digital twins stop being siloed. Federated twin networks share state across organizations and borders.",
        "markers": ["federated", "interoperable", "cross-organization",
                     "shared state", "digital twin", "citygml", "ifc",
                     "common data environment", "linked data"],
        "weight": 8,
    },
    "synthetic_data_generation": {
        "name": "Synthetic Data + Generative Worlds",
        "horizon": "5yr",
        "horizon_desc": "2030-2032: Synthetic environments replace real data collection for training. World models generate training scenarios.",
        "markers": ["synthetic", "generated", "world model", "simulation",
                     "augmented", "generative", "procedural"],
        "weight": 6,
    },
    "autonomous_infrastructure": {
        "name": "Autonomous Infrastructure Management",
        "horizon": "5yr",
        "horizon_desc": "2030-2032: Infrastructure self-monitors, self-repairs, self-optimizes. Human operators become exception handlers.",
        "markers": ["autonomous", "self-improving", "self-monitoring",
                     "predictive maintenance", "continuous", "prescriptive",
                     "automated decision"],
        "weight": 7,
    },
    "regulation_as_code": {
        "name": "Regulation-as-Code / Machine-Readable Policy",
        "horizon": "5yr",
        "horizon_desc": "2030-2032: EU regulations become machine-executable. Compliance is automated, not manual.",
        "markers": ["compliance", "regulatory", "easa", "gdpr", "ai act",
                     "regulation", "automated compliance", "audit trail",
                     "machine-readable"],
        "weight": 5,
    },
    # --- 10-YEAR HORIZON (2036) ---
    "ambient_intelligence": {
        "name": "Ambient Intelligence / Invisible Computing",
        "horizon": "10yr",
        "horizon_desc": "2033-2036: Computing disappears into the environment. Spatial computing becomes as invisible as WiFi.",
        "markers": ["ambient", "invisible", "ubiquitous", "pervasive",
                     "spatial computing", "environmental intelligence",
                     "context-aware"],
        "weight": 4,
    },
    "biological_digital_convergence": {
        "name": "Biological-Digital Convergence",
        "horizon": "10yr",
        "horizon_desc": "2033-2036: Digital twins merge with biological systems. Material science meets synthetic biology.",
        "markers": ["biological", "bio-digital", "material composition",
                     "dielectric", "material properties", "environmental sensing",
                     "living material"],
        "weight": 4,
    },
    "planetary_digital_twin": {
        "name": "Planetary-Scale Digital Twin",
        "horizon": "10yr",
        "horizon_desc": "2033-2036: City-scale twins merge into national, then planetary infrastructure. The spatial index BECOMES the map.",
        "markers": ["planetary", "global", "city-scale", "country-scale",
                     "infrastructure", "persistent", "universal",
                     "queryable", "spatial index"],
        "weight": 5,
    },
    "post_quantum_native": {
        "name": "Post-Quantum Native Architecture",
        "horizon": "10yr",
        "horizon_desc": "2033-2036: Quantum computers break current encryption. All data collected today is vulnerable. Systems must be quantum-native.",
        "markers": ["quantum", "post-quantum", "quantum-secure",
                     "lattice", "homomorphic", "future-proof encryption"],
        "weight": 3,
    },
}


def score_future_tech_radar(model) -> dict:
    """Score proposal against the Future Tech Radar (2029 landscape)."""
    text = model.full_text.lower() if model.full_text else ""
    scores = {}

    for dim_key, dim in FUTURE_TECH_RADAR.items():
        found = sum(1 for m in dim["markers"] if m in text)
        total = len(dim["markers"])
        raw_pct = (found / total * 100) if total > 0 else 0
        score = round(max(1.0, min(5.0, 1.0 + raw_pct * 0.04)), 1)
        scores[dim_key] = {
            "name": dim["name"],
            "score": score,
            "found": found,
            "total": total,
            "weight": dim["weight"],
            "horizon": dim.get("horizon", "3yr"),
            "horizon_desc": dim.get("horizon_desc", dim.get("horizon", "")),
        }

    weighted_sum = sum(s["score"] * s["weight"] for s in scores.values())
    total_weight = sum(s["weight"] for s in scores.values())
    scores["_weighted_avg"] = round(weighted_sum / total_weight, 2) if total_weight else 0
    scores["_future_readiness"] = (
        "FUTURE-READY" if scores["_weighted_avg"] >= 4.0
        else "PARTIALLY ALIGNED" if scores["_weighted_avg"] >= 3.0
        else "PRESENT-FOCUSED"
    )
    return scores


def format_future_tech_radar(scores: dict) -> list:
    """Format future tech radar as report lines, grouped by horizon."""
    lines = []
    lines.append("  FUTURE TECH RADAR (scoring against where the world WILL BE)")
    lines.append("  " + "-" * 72)
    lines.append("  x100 question: What happens when this is 100x cheaper/faster/smaller?")
    lines.append("")

    horizons = {"3yr": "3-YEAR HORIZON (2029)", "5yr": "5-YEAR HORIZON (2031)",
                "10yr": "10-YEAR HORIZON (2036)"}
    horizon_avgs = {}

    for hz_key, hz_label in horizons.items():
        hz_dims = [(k, v) for k, v in scores.items()
                   if not k.startswith("_") and v.get("horizon") == hz_key]
        if not hz_dims:
            continue

        lines.append(f"  --- {hz_label} ---")
        hz_total_w = 0
        hz_total_s = 0
        for dim_key, dim in sorted(hz_dims, key=lambda x: x[1]["weight"], reverse=True):
            filled = int((dim["score"] - 1.0) / 4.0 * 16)
            bar = "#" * filled + "." * (16 - filled)
            lines.append(f"  {dim['name']:<34} {dim['score']}/5.0  [{bar}]  "
                          f"({dim['found']}/{dim['total']}, w={dim['weight']}%)")
            hz_total_w += dim["weight"]
            hz_total_s += dim["score"] * dim["weight"]
        hz_avg = hz_total_s / hz_total_w if hz_total_w else 0
        horizon_avgs[hz_key] = hz_avg
        lines.append(f"  {hz_label} AVG: {hz_avg:.2f}/5.0")
        lines.append("")

    lines.append(f"  OVERALL FUTURE READINESS:  {scores['_weighted_avg']:.2f} / 5.00  "
                  f"[{scores['_future_readiness']}]")
    if horizon_avgs:
        weakest = min(horizon_avgs, key=horizon_avgs.get)
        lines.append(f"  Weakest horizon: {horizons.get(weakest, weakest)} "
                      f"({horizon_avgs[weakest]:.2f}/5.0)")
    lines.append("")
    return lines


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Partner:
    name: str = ""
    pic: str = ""
    country: str = ""
    is_sme: bool = False
    total_eligible: float = 0.0
    eu_contribution: float = 0.0
    person_months: float = 0.0
    personnel_cost: float = 0.0


@dataclass
class Researcher:
    name: str = ""
    gender: str = ""
    partner: str = ""
    role: str = ""


@dataclass
class WorkPackage:
    number: int = 0
    title: str = ""
    lead: str = ""
    start_month: int = 0
    end_month: int = 0
    person_months: float = 0.0


@dataclass
class Task:
    id: str = ""
    title: str = ""
    lead: str = ""
    start_month: int = 0
    end_month: int = 0
    wp_number: int = 0


@dataclass
class Deliverable:
    id: str = ""
    title: str = ""
    lead: str = ""
    month: int = 0
    dtype: str = ""
    wp_number: int = 0


@dataclass
class Milestone:
    id: str = ""
    title: str = ""
    lead: str = ""
    month: int = 0
    verification: str = ""


@dataclass
class RiskEntry:
    description: str = ""
    likelihood: str = ""
    severity: str = ""
    mitigation: str = ""
    category: str = ""


@dataclass
class ProposalModel:
    # Admin / Part A
    acronym: str = ""
    title: str = ""
    duration_months: int = 0
    call_id: str = ""
    topic: str = ""
    action_type: str = ""          # RIA, IA, CSA, etc.

    partners: list = field(default_factory=list)          # list[Partner]
    researchers: list = field(default_factory=list)       # list[Researcher]

    # Part B structure
    abstract_text: str = ""
    sections_detected: list = field(default_factory=list) # list[str]
    work_packages: list = field(default_factory=list)     # list[WorkPackage]
    tasks: list = field(default_factory=list)             # list[Task]
    deliverables: list = field(default_factory=list)      # list[Deliverable]
    milestones: list = field(default_factory=list)        # list[Milestone]
    risks: list = field(default_factory=list)             # list[RiskEntry]

    kpis_found: list = field(default_factory=list)        # list[str]
    citations_found: list = field(default_factory=list)   # list[tuple(author,year)]
    acronyms_used: set = field(default_factory=set)
    acronyms_defined: set = field(default_factory=set)

    # Budget
    budget_total: float = 0.0
    budget_eu: float = 0.0
    subcontracting_total: float = 0.0
    equipment_total: float = 0.0
    travel_total: float = 0.0
    indirect_total: float = 0.0
    personnel_total: float = 0.0

    # Ethics
    ethics_issues_flagged: list = field(default_factory=list)

    # Raw text stores for analysis
    full_text: str = ""
    part_b_text: str = ""
    part_b_start_page: int = 1
    part_b_pages: int = 0
    total_pages: int = 0

    def summary(self) -> str:
        lines = [
            f"PROPOSAL MODEL",
            f"  Acronym:       {self.acronym or '(not detected)'}",
            f"  Title:         {self.title[:80] or '(not detected)'}",
            f"  Duration:      {self.duration_months}m",
            f"  Call ID:       {self.call_id or '(not detected)'}",
            f"  Action type:   {self.action_type or '(not detected)'}",
            f"  Partners:      {len(self.partners)}",
            f"  Researchers:   {len(self.researchers)}",
            f"  Work packages: {len(self.work_packages)}",
            f"  Tasks:         {len(self.tasks)}",
            f"  Deliverables:  {len(self.deliverables)}",
            f"  Milestones:    {len(self.milestones)}",
            f"  Risks:         {len(self.risks)}",
            f"  KPIs:          {len(self.kpis_found)}",
            f"  Citations:     {len(self.citations_found)}",
            f"  Budget total:  EUR {self.budget_total:,.0f}",
            f"  EU contrib:    EUR {self.budget_eu:,.0f}",
        ]
        return "\n".join(lines)


@dataclass
class Finding:
    pattern: str
    severity: str        # CRITICAL, HIGH, MEDIUM, LOW
    page: int
    text: str
    suggestion: str
    category: str = ""
    layer: int = 4


@dataclass
class AnalysisResult:
    findings: list = field(default_factory=list)

    def add(self, pattern, severity, page, text, suggestion, category="", layer=4):
        self.findings.append(Finding(pattern, severity, page, text, suggestion, category, layer))


# ============================================================
# PASS 1: EXTRACTION
# ============================================================

def extract_text(pdf_path: str) -> tuple[dict, int]:
    doc = fitz.open(pdf_path)
    pages = {}
    for i in range(len(doc)):
        pages[i + 1] = doc[i].get_text()
    return pages, len(doc)


def is_admin_page(text: str) -> bool:
    indicators = [
        'Administrative forms', 'Participant Registry',
        'PIC\n', 'Legal name\n', 'SME Data', 'Gender Equality Plan',
        'Departments carrying out', 'Main contact person',
        'This proposal version was submitted by',
    ]
    return sum(1 for i in indicators if i in text) >= 2


def find_part_b_start(pages: dict) -> int:
    for num in sorted(pages.keys()):
        text = pages[num]
        if "Part B" in text and num > 5:
            lower = text.lower()
            if any(w in lower for w in ['excellence', 'objectives', 'section 1']):
                return num
    for num in sorted(pages.keys()):
        if "Part B" in pages[num] and "Administrative forms" not in pages[num]:
            return num
    return 1


def get_full_text(pages: dict) -> str:
    return " ".join(t for _, t in sorted(pages.items()))


def get_part_b_text(pages: dict, start: int) -> str:
    return " ".join(t for n, t in sorted(pages.items()) if n >= start and not is_admin_page(t))


def load_call_text(call_path: str) -> str:
    if call_path.lower().endswith('.pdf'):
        doc = fitz.open(call_path)
        return " ".join(doc[i].get_text() for i in range(len(doc)))
    return Path(call_path).read_text(encoding='utf-8')


def _parse_money(s: str) -> float:
    """Parse a money string like '1,234,567.89' or '1.234.567' -> float."""
    s = s.replace(',', '').replace(' ', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


def extract_proposal_model(pages: dict, page_count: int) -> ProposalModel:
    model = ProposalModel()
    model.total_pages = page_count
    model.part_b_start_page = find_part_b_start(pages)
    model.part_b_pages = sum(1 for n in pages if n >= model.part_b_start_page and not is_admin_page(pages[n]))
    model.full_text = get_full_text(pages)
    model.part_b_text = get_part_b_text(pages, model.part_b_start_page)

    full = model.full_text
    lower = full.lower()

    # --- Acronym / title ---
    m = re.search(r'(?:Acronym|Short name)[:\s]+([A-Z][A-Z0-9\-]{1,20})', full)
    if m:
        model.acronym = m.group(1).strip()

    m = re.search(r'(?:Full title|Project title|Title of the proposal)[:\s]+([^\n]{10,150})', full)
    if m:
        model.title = m.group(1).strip()

    # --- Duration ---
    m = re.search(r'Duration[:\s]+(\d{2,3})\s*(?:months?|M)', full, re.IGNORECASE)
    if m:
        model.duration_months = int(m.group(1))
    if not model.duration_months:
        m = re.search(r'(\d{2,3})\s*months?\s*(?:project|duration)', lower)
        if m:
            model.duration_months = int(m.group(1))

    # --- Call ID ---
    m = re.search(r'(HORIZON[-\s][A-Z0-9\-]{5,40})', full)
    if m:
        model.call_id = m.group(1).strip()

    # --- Topic ---
    m = re.search(r'(?:Topic[:\s]+|topic identifier[:\s]+)([A-Z0-9\-\.]{5,40})', full, re.IGNORECASE)
    if m:
        model.topic = m.group(1).strip()

    # --- Action type ---
    for at in ['Research and Innovation Action', 'Innovation Action',
               'Coordination and Support Action', 'Marie Sklodowska-Curie',
               'ERC', 'RIA', 'IA', 'CSA']:
        if at in full:
            model.action_type = at
            break

    # --- Partners ---
    partner_blocks = re.findall(
        r'PIC[:\s]+(\d{9})[^\n]*\n([^\n]{5,80})',
        full
    )
    seen_pics = set()
    for pic, name in partner_blocks:
        if pic not in seen_pics:
            seen_pics.add(pic)
            p = Partner(name=name.strip(), pic=pic)
            country_m = re.search(r'\b([A-Z]{2})\b', name)
            if country_m:
                p.country = country_m.group(1)
            if re.search(r'\bSME\b', name, re.IGNORECASE):
                p.is_sme = True
            model.partners.append(p)

    # Fallback: look for participant table rows
    if not model.partners:
        participant_rows = re.findall(
            r'([A-Z][A-Z &\-]{3,50})\s{2,}([A-Z]{2})\s{2,}([A-Z\-]+)\s{2,}(\d{9})',
            full
        )
        seen_pics = set()
        for name, country, role, pic in participant_rows:
            if pic not in seen_pics:
                seen_pics.add(pic)
                p = Partner(name=name.strip(), pic=pic, country=country)
                model.partners.append(p)

    # --- Person months per partner ---
    pm_rows = re.findall(
        r'([A-Z][A-Z0-9\-]{1,15})\s+(\d+(?:\.\d+)?)\s+(?:PM|person[\s-]months?)',
        full, re.IGNORECASE
    )
    pm_lookup = {r[0].upper(): float(r[1]) for r in pm_rows}
    for p in model.partners:
        key = p.name[:10].upper().strip()
        if key in pm_lookup:
            p.person_months = pm_lookup[key]

    # --- Researchers ---
    researcher_rows = re.findall(
        r'([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+([MF]|Male|Female|Other)\s+(\w+)',
        full
    )
    for name, gender, role in researcher_rows[:30]:
        model.researchers.append(Researcher(name=name, gender=gender[0].upper(), role=role))

    # --- Abstract ---
    m = re.search(
        r'Abstract[:\s]*\n(.*?)(?=\n(?:Section|1\.|Excellence|Objectives|Keywords))',
        full, re.DOTALL | re.IGNORECASE
    )
    if m:
        model.abstract_text = m.group(1).strip()[:3000]

    # --- Sections detected ---
    section_patterns = [
        r'^((?:Section\s+)?\d+(?:\.\d+)?\s+[A-Z][^\n]{5,80})$',
        r'^(\d\.\s+[A-Z][^\n]{5,60})$',
    ]
    for pat in section_patterns:
        for line in full.split('\n'):
            if re.match(pat, line.strip()):
                model.sections_detected.append(line.strip())
    model.sections_detected = list(dict.fromkeys(model.sections_detected))[:60]

    # --- Work Packages ---
    wp_patterns = [
        r'WP\s*(\d+)\s*[:\-–]?\s*([^\n]{5,80})\s+(?:Lead|Leader)[:\s]+([A-Z][A-Z\-]{1,20})\s+M(\d+)\s*[-–]\s*M?(\d+)',
        r'Work [Pp]ackage\s+(\d+)[:\s]+([^\n]{5,80})\n.*?([A-Z]{2,15})\s+(\d+)\s+(\d+)',
    ]
    seen_wps = set()
    for pat in wp_patterns:
        for m in re.finditer(pat, full, re.DOTALL):
            num = int(m.group(1))
            if num in seen_wps:
                continue
            seen_wps.add(num)
            wp = WorkPackage(
                number=num,
                title=m.group(2).strip(),
                lead=m.group(3).strip() if len(m.groups()) >= 3 else "",
                start_month=int(m.group(4)) if len(m.groups()) >= 4 else 0,
                end_month=int(m.group(5)) if len(m.groups()) >= 5 else 0,
            )
            model.work_packages.append(wp)

    # Simpler WP detection fallback
    if not model.work_packages:
        for m in re.finditer(r'WP\s*(\d+)[:\s–\-]+([^\n]{5,80})', full):
            num = int(m.group(1))
            if num not in seen_wps:
                seen_wps.add(num)
                model.work_packages.append(WorkPackage(number=num, title=m.group(2).strip()))
    model.work_packages.sort(key=lambda x: x.number)

    # --- Tasks ---
    for m in re.finditer(
        r'T(\d+)\.(\d+)[:\s–\-]+([^\n]{5,100})(?:.*?Lead[:\s]+([A-Z][A-Z\-]{1,15}))?',
        full, re.DOTALL
    ):
        task = Task(
            id=f"T{m.group(1)}.{m.group(2)}",
            title=m.group(3).strip()[:100],
            wp_number=int(m.group(1)),
            lead=m.group(4).strip() if m.group(4) else "",
        )
        start_m = re.search(r'M(\d+)\s*[-–]\s*M?(\d+)', m.group(0))
        if start_m:
            task.start_month = int(start_m.group(1))
            task.end_month = int(start_m.group(2))
        model.tasks.append(task)

    # --- Deliverables ---
    for m in re.finditer(
        r'D(\d+)\.(\d+)[:\s–\-]+([^\n]{5,120})',
        full
    ):
        d = Deliverable(
            id=f"D{m.group(1)}.{m.group(2)}",
            title=m.group(3).strip()[:120],
            wp_number=int(m.group(1)),
        )
        # Try to find month
        month_m = re.search(r'[Mm](\d+)\b', m.group(0)[len(m.group(0))//2:])
        if month_m:
            d.month = int(month_m.group(1))
        model.deliverables.append(d)

    # --- Milestones ---
    for m in re.finditer(
        r'MS\s*(\d+)[:\s–\-]+([^\n]{5,120})',
        full
    ):
        ms = Milestone(
            id=f"MS{m.group(1)}",
            title=m.group(2).strip()[:120],
        )
        month_m = re.search(r'[Mm](\d+)\b', m.group(0))
        if month_m:
            ms.month = int(month_m.group(1))
        model.milestones.append(ms)

    # --- Risks ---
    risk_rows = re.findall(
        r'([^\n]{10,120})\s+(High|Medium|Low)\s+(High|Medium|Low)\s+([^\n]{10,200})',
        full, re.IGNORECASE
    )
    for desc, likelihood, severity, mitigation in risk_rows[:20]:
        model.risks.append(RiskEntry(
            description=desc.strip(),
            likelihood=likelihood.capitalize(),
            severity=severity.capitalize(),
            mitigation=mitigation.strip(),
        ))

    # --- KPIs ---
    kpi_patterns = [
        r'(?:KPI|Key Performance Indicator)[:\s]+([^\n]{10,120})',
        r'(?:target|achieve|reduce|increase)\s+(?:by\s+)?(\d+\s*%[^\n]{0,80})',
        r'(?:>=?|≥|<=?|≤)\s*\d+\s*%[^\n]{0,60}',
    ]
    for pat in kpi_patterns:
        for m in re.finditer(pat, full, re.IGNORECASE):
            model.kpis_found.append(m.group(0)[:120])
    model.kpis_found = list(dict.fromkeys(model.kpis_found))[:30]

    # --- Citations ---
    cit_patterns = [
        r'\(([A-Z][a-zA-Z\-]+(?:\s+et\s+al\.?)?\s*,?\s*(\d{4}))\)',
        r'\[(\d{4})\]',
    ]
    for pat in cit_patterns:
        for m in re.finditer(pat, full):
            year_m = re.search(r'(\d{4})', m.group(1) if len(m.groups()) >= 1 else m.group(0))
            if year_m:
                yr = int(year_m.group(1))
                if 1980 <= yr <= 2027:
                    model.citations_found.append((m.group(1), yr))
    model.citations_found = list(dict.fromkeys(model.citations_found))[:200]

    # --- Acronyms used vs defined ---
    model.acronyms_used = set(re.findall(r'\b([A-Z]{3,6})\b', full))
    defined = re.findall(r'\(([A-Z]{3,6})\)', full)
    defined += re.findall(r'([A-Z]{3,6})\s*[-–:]\s+[A-Z][a-z]', full)
    model.acronyms_defined = set(defined)

    # --- Budget ---
    budget_patterns = [
        r'Total\s+eligible\s+costs?[:\s]+([\d,\.]+)',
        r'Total\s+budget[:\s]+([\d,\.]+)',
        r'Grand\s+total[:\s]+([\d,\.]+)',
    ]
    for pat in budget_patterns:
        m = re.search(pat, full, re.IGNORECASE)
        if m:
            val = _parse_money(m.group(1))
            if val > 100000:
                model.budget_total = val
                break

    eu_patterns = [
        r'(?:EU\s+contribution|EC\s+contribution|Requested\s+EU)[:\s]+([\d,\.]+)',
        r'(?:Total\s+EU|Union\s+contribution)[:\s]+([\d,\.]+)',
    ]
    for pat in eu_patterns:
        m = re.search(pat, full, re.IGNORECASE)
        if m:
            val = _parse_money(m.group(1))
            if val > 100000:
                model.budget_eu = val
                break

    sub_m = re.search(r'[Ss]ubcontracting[:\s]+([\d,\.]+)', full)
    if sub_m:
        model.subcontracting_total = _parse_money(sub_m.group(1))

    eq_m = re.search(r'[Ee]quipment[:\s]+([\d,\.]+)', full)
    if eq_m:
        model.equipment_total = _parse_money(eq_m.group(1))

    tr_m = re.search(r'[Tt]ravel[:\s]+([\d,\.]+)', full)
    if tr_m:
        model.travel_total = _parse_money(tr_m.group(1))

    ind_m = re.search(r'[Ii]ndirect\s+costs?[:\s]+([\d,\.]+)', full)
    if ind_m:
        model.indirect_total = _parse_money(ind_m.group(1))

    pers_m = re.search(r'[Pp]ersonnel\s+costs?[:\s]+([\d,\.]+)', full)
    if pers_m:
        model.personnel_total = _parse_money(pers_m.group(1))

    # --- Ethics ---
    ethics_section = re.search(
        r'[Ee]thics\s+(?:self[\s-]?assessment|issues?|review)[:\s]*(.*?)(?=\n\n|\nSection|\n\d\.)',
        full, re.DOTALL
    )
    if ethics_section:
        flags = re.findall(r'(?:Yes|No)\s*[-–:]\s*([^\n]{10,120})', ethics_section.group(1))
        model.ethics_issues_flagged = [f.strip() for f in flags[:10]]

    return model


# ============================================================
# SMILE METHODOLOGY FRAMEWORK
# ============================================================

SMILE_PHASES = {
    "reality_emulation": {
        "name": "Reality Emulation",
        "key_question": "What is the starting point and boundary of your sociotechnological ecosystem?",
        "proposal_markers": [
            "stakeholder mapping", "stakeholder analysis", "ecosystem boundary",
            "spatial context", "temporal context", "reality canvas",
            "operating context", "sociotechnological", "actor-network",
            "pesteled", "pestle", "5 whys", "root cause",
        ],
        "structural_checks": [
            "stakeholder table", "stakeholder matrix",
            "spatial scope", "temporal scope",
            "system boundary", "context diagram",
        ],
        "what_to_check": "Does the proposal define the reality it operates in? Stakeholders, boundaries, spatial-temporal context?",
    },
    "concurrent_engineering": {
        "name": "Concurrent Engineering",
        "key_question": "What does the Minimal Viable Twin look like?",
        "proposal_markers": [
            "minimal viable", "mvp", "mvt", "as-is", "to-be",
            "hypothesis", "validate", "simulation", "scenario",
            "virtual first", "prototype", "proof of concept",
        ],
        "structural_checks": [
            "validation methodology", "test plan", "acceptance criteria",
            "verification and validation", "proof of concept",
        ],
        "what_to_check": "Does the proposal define what 'good enough' looks like before scaling? Is there a validation step?",
    },
    "collective_intelligence": {
        "name": "Collective Intelligence",
        "key_question": "How does the system connect to physical reality and meet initial KPIs?",
        "proposal_markers": [
            "sensor", "ontology", "kpi", "interoperability",
            "data model", "schema", "metadata", "standards",
            "integration", "connected", "iot",
        ],
        "structural_checks": [
            "iso ", "iec ", "ieee ", "w3c", "oasis", "etsi",
            "ifc", "owl", "rdf", "json-ld", "saref",
        ],
        "what_to_check": "Are specific standards/ontologies NAMED (not just mentioned)?",
    },
    "contextual_intelligence": {
        "name": "Contextual Intelligence",
        "key_question": "Can the system make real-time decisions with context?",
        "proposal_markers": [
            "real-time", "command and control", "predictive",
            "analytics", "root cause", "decision support",
            "dashboard", "monitoring", "alert",
        ],
        "structural_checks": [
            "decision support system", "dashboard specification",
            "alert threshold", "notification", "report format",
        ],
        "what_to_check": "Are specific decision support outputs defined (not just 'a dashboard')?",
    },
    "continuous_intelligence": {
        "name": "Continuous Intelligence",
        "key_question": "Does the system learn and prescribe, not just predict?",
        "proposal_markers": [
            "prescriptive", "ai-driven", "prognostic",
            "machine learning", "model training", "feedback loop",
            "continuous", "autonomous", "self-improving",
        ],
        "structural_checks": [
            "ai maturity", "model update", "retraining",
            "mlops", "drift detection", "model versioning",
        ],
        "what_to_check": "Is there an AI maturity path described (not just 'we will use ML')?",
    },
    "perpetual_wisdom": {
        "name": "Perpetual Wisdom",
        "key_question": "How does impact scale beyond the project?",
        "proposal_markers": [
            "open source", "ecosystem", "replication",
            "transferability", "sustainability", "circular",
            "planetary", "global", "share impact",
        ],
        "structural_checks": [
            "open source repository", "github", "gitlab",
            "sustainability plan", "replication guide",
            "open access", "creative commons",
        ],
        "what_to_check": "Is there a concrete open-source/sustainability/replication plan?",
    },
}

SMILE_PERSPECTIVES = {
    "people": {
        "name": "From People",
        "markers": ["stakeholder", "user", "citizen", "community", "participat", "co-design", "co-creation"],
    },
    "systems": {
        "name": "From Systems",
        "markers": ["ontology", "standard", "interoperab", "metadata", "schema", "protocol", "api"],
    },
    "planet": {
        "name": "From Planet",
        "markers": ["gis", "bim", "cim", "satellite", "spatial", "geospatial", "environmental", "sustainability"],
    },
}

# Country -> rough personnel cost per PM (EUR)
COUNTRY_PM_BENCHMARKS = {
    "SE": (7000, 9000), "NO": (8000, 10000), "DK": (7000, 9000), "FI": (7000, 9000),
    "DE": (6500, 8500), "AT": (6000, 8000), "NL": (6500, 8500), "BE": (6000, 8000),
    "FR": (6000, 8000), "CH": (8000, 11000), "IE": (6000, 8000),
    "IT": (4000, 6000), "ES": (4000, 6000), "PT": (3500, 5500), "GR": (3000, 5000),
    "PL": (3000, 5000), "CZ": (3000, 5000), "RO": (2500, 4500), "HU": (3000, 5000),
    "UA": (2000, 4000), "RS": (2500, 4000),
}


# ============================================================
# LAYER 1: STRUCTURAL INTEGRITY
# ============================================================

def check_structural_integrity(model: ProposalModel, result: AnalysisResult):
    """Cross-document consistency checks."""
    cat = "Structural Integrity"
    layer = 1

    # --- Partner count: ≥3 from ≥3 different EU/Associated countries ---
    if model.partners:
        countries = set(p.country for p in model.partners if p.country)
        if len(model.partners) < 3:
            result.add("Consortium Too Small", "CRITICAL", 0,
                f"Only {len(model.partners)} partners detected. Minimum is 3 for most HE actions.",
                "Horizon Europe RIA/IA requires ≥3 independent legal entities from ≥3 eligible countries.",
                cat, layer)
        elif len(countries) < 3:
            result.add("Country Diversity Insufficient", "CRITICAL", 0,
                f"Partners from only {len(countries)} distinct countries: {', '.join(sorted(countries))}",
                "Must have ≥3 different EU member states or associated countries.",
                cat, layer)
    else:
        result.add("Partners Not Detected", "HIGH", 0,
            "Could not extract partner list from the document.",
            "Ensure Part A administrative forms are included in the submitted PDF.",
            cat, layer)

    # --- WP start/end months within project duration ---
    if model.duration_months > 0:
        for wp in model.work_packages:
            if wp.end_month > model.duration_months:
                result.add("WP Exceeds Duration", "HIGH", 0,
                    f"WP{wp.number} ends M{wp.end_month} but project is {model.duration_months}m",
                    "All WP end months must fall within the project duration.",
                    cat, layer)
            if wp.start_month > wp.end_month and wp.end_month > 0:
                result.add("WP Invalid Dates", "HIGH", 0,
                    f"WP{wp.number} starts M{wp.start_month} but ends M{wp.end_month}",
                    "WP start month cannot exceed end month.",
                    cat, layer)

    # --- Every deliverable ID mentioned in WP descriptions should be in deliverable table ---
    full = model.part_b_text
    del_ids_in_text = set(re.findall(r'\bD(\d+\.\d+)\b', full))
    del_ids_in_table = set(d.id.replace('D', '') for d in model.deliverables)
    orphan_dels = del_ids_in_text - del_ids_in_table
    if len(orphan_dels) > 2:
        sample = ', '.join(f"D{x}" for x in sorted(orphan_dels)[:5])
        result.add("Orphaned Deliverable References", "HIGH", 0,
            f"Deliverables referenced in text but not in deliverable table: {sample}",
            "Every deliverable mentioned in WP descriptions must appear in the deliverable table.",
            cat, layer)

    # --- Milestone quality: meeting milestones ---
    bad_ms_words = ['meeting', 'workshop', 'kickoff', 'kick-off', 'conference',
                    'review meeting', 'webinar', 'seminar']
    for ms in model.milestones:
        title_lower = ms.title.lower()
        if any(w in title_lower for w in bad_ms_words):
            result.add("Meeting Milestone", "HIGH", 0,
                f"Milestone '{ms.id}: {ms.title[:70]}' is a calendar event, not a verifiable achievement.",
                "Milestones must be concrete, independently verifiable outputs (reports, datasets, prototypes).",
                cat, layer)
            break

    # --- No partner has zero PMs but leads tasks ---
    if model.tasks and model.partners:
        task_leads = Counter(t.lead for t in model.tasks if t.lead)
        partner_pms = {p.name[:12].upper(): p.person_months for p in model.partners}
        for lead, count in task_leads.items():
            # Try to match partner name
            for pname, pms in partner_pms.items():
                if lead.upper()[:8] in pname or pname[:8] in lead.upper()[:8]:
                    if pms == 0.0 and count >= 2:
                        result.add("Zero-PM Task Lead", "CRITICAL", 0,
                            f"{lead} leads {count} tasks but has 0 PMs in partner table.",
                            "Cannot lead tasks with no effort allocated — fix PM table.",
                            cat, layer)

    # --- Personnel cost per PM vs country benchmarks ---
    for p in model.partners:
        if p.person_months > 0 and p.personnel_cost > 0 and p.country:
            cost_per_pm = p.personnel_cost / p.person_months
            benchmark = COUNTRY_PM_BENCHMARKS.get(p.country)
            if benchmark:
                lo, hi = benchmark
                if cost_per_pm < lo * 0.5:
                    result.add("Suspiciously Low Personnel Cost", "MEDIUM", 0,
                        f"{p.name}: EUR {cost_per_pm:,.0f}/PM vs benchmark EUR {lo:,}-{hi:,} for {p.country}",
                        "Cost per PM is far below country benchmark — reviewers will question this.",
                        cat, layer)
                elif cost_per_pm > hi * 1.5:
                    result.add("Suspiciously High Personnel Cost", "MEDIUM", 0,
                        f"{p.name}: EUR {cost_per_pm:,.0f}/PM vs benchmark EUR {lo:,}-{hi:,} for {p.country}",
                        "Cost per PM is far above country benchmark — may be challenged in negotiation.",
                        cat, layer)

    # --- Subcontracting ratio ---
    if model.budget_total > 0 and model.subcontracting_total > 0:
        sub_pct = model.subcontracting_total / model.budget_total * 100
        if sub_pct > 30:
            result.add("High Subcontracting Ratio", "HIGH", 0,
                f"Subcontracting is {sub_pct:.1f}% of total budget (>{30}% threshold).",
                "Justify subcontracting explicitly; reviewers scrutinise this. Consider adding subcontractor as partner.",
                cat, layer)

    # --- Equipment cost ratio ---
    if model.personnel_total > 0 and model.equipment_total > 0:
        eq_pct = model.equipment_total / model.personnel_total * 100
        if eq_pct > 15:
            result.add("High Equipment Ratio", "MEDIUM", 0,
                f"Equipment is {eq_pct:.1f}% of personnel costs (>{15}% is unusual).",
                "Justify major equipment purchases; ensure they cannot be substituted by existing infrastructure.",
                cat, layer)

    # --- Management WP effort check ---
    if model.work_packages:
        mgmt_wps = [wp for wp in model.work_packages
                    if wp.number == 1 or 'management' in wp.title.lower()]
        total_pm_in_wps = sum(wp.person_months for wp in model.work_packages if wp.person_months > 0)
        if mgmt_wps and total_pm_in_wps > 0:
            mgmt_pm = sum(wp.person_months for wp in mgmt_wps)
            pct = mgmt_pm / total_pm_in_wps * 100
            if pct > 12:
                result.add("Heavy Management WP", "MEDIUM", 0,
                    f"Management WP is {pct:.0f}% of total WP effort (typical: 5-10%).",
                    "Keep management WP to 5-10% of total effort.",
                    cat, layer)
            elif pct < 3 and len(model.partners) >= 5:
                result.add("Under-Resourced Management", "LOW", 0,
                    f"Management WP is only {pct:.0f}% with {len(model.partners)} partners.",
                    "Complex consortia need ≥5% management effort.",
                    cat, layer)

    # --- Abstract keyword overlap with Part B ---
    if model.abstract_text:
        abstract_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]{5,}\b', model.abstract_text))
        part_b_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]{5,}\b', model.part_b_text))
        if abstract_words:
            overlap_pct = len(abstract_words & part_b_words) / len(abstract_words) * 100
            if overlap_pct < 40:
                result.add("Abstract-Body Disconnect", "MEDIUM", 0,
                    f"Only {overlap_pct:.0f}% of abstract keywords appear in Part B.",
                    "Abstract should summarise what is in the proposal — reviewers read it first.",
                    cat, layer)

        # Abstract quality: length
        abs_len = len(model.abstract_text)
        if abs_len < 800:
            result.add("Abstract Too Short", "MEDIUM", 0,
                f"Abstract is {abs_len} chars (ideal: 1500-2000 chars for a strong summary).",
                "Expand abstract to cover problem / solution / consortium / expected impact.",
                cat, layer)
        elif abs_len > 2500:
            result.add("Abstract Too Long", "LOW", 0,
                f"Abstract is {abs_len} chars (limit is usually 2000 chars in submission system).",
                "Check character limit in the submission system — truncation is automatic.",
                cat, layer)

        # Problem/solution/impact structure
        ab_lower = model.abstract_text.lower()
        has_problem = any(w in ab_lower for w in ['challenge', 'problem', 'gap', 'limitation', 'barrier'])
        has_solution = any(w in ab_lower for w in ['will develop', 'will create', 'will deliver', 'aims to', 'proposes'])
        has_impact = any(w in ab_lower for w in ['impact', 'benefit', 'outcome', 'society', 'market'])
        missing = []
        if not has_problem: missing.append('problem statement')
        if not has_solution: missing.append('solution description')
        if not has_impact: missing.append('impact claim')
        if missing:
            result.add("Abstract Structure Weak", "LOW", 0,
                f"Abstract appears to be missing: {', '.join(missing)}.",
                "Strong abstracts follow: Problem → Solution → Consortium → Impact.",
                cat, layer)

    # --- Gender balance in named researchers ---
    if len(model.researchers) >= 3:
        genders = Counter(r.gender for r in model.researchers if r.gender in ('M', 'F'))
        total_g = sum(genders.values())
        if total_g >= 3:
            male_pct = genders.get('M', 0) / total_g * 100
            if male_pct > 80:
                result.add("Gender Imbalance", "MEDIUM", 0,
                    f"Named researchers: {genders.get('M',0)} male, {genders.get('F',0)} female ({male_pct:.0f}% male).",
                    "HE expects gender balance in teams. ERC/MSCA additionally require GEP.",
                    cat, layer)

    # --- Ethics self-assessment completeness ---
    if not model.ethics_issues_flagged:
        result.add("Ethics Self-Assessment Not Detected", "LOW", 0,
            "Could not find ethics self-assessment flags in Part A.",
            "Ensure ethics self-assessment form is complete; incomplete forms trigger Agency review.",
            cat, layer)

    # --- Page count ---
    part_b_page_count = sum(
        1 for n, t in {}.items()  # filled below
    )
    # Use a simpler heuristic from model
    expected_limit = 40
    if 'csa' in model.action_type.lower() if model.action_type else False:
        expected_limit = 25
    if model.total_pages > 0:
        # Rough: admin pages are roughly 30% of doc
        estimated_part_b = int(model.total_pages * 0.65)
        if estimated_part_b > expected_limit + 5:
            result.add("Page Limit Risk", "HIGH", 0,
                f"Document is {model.total_pages} pages total; Part B estimated ~{estimated_part_b} pages "
                f"(limit is {expected_limit} for {model.action_type or 'RIA/IA'}).",
                "Pages beyond the limit are cut by the submission system — evaluators never see them.",
                cat, layer)

    # --- Action type vs TRL consistency ---
    if model.action_type:
        at_lower = model.action_type.lower()
        trl_nums = [int(x) for x in re.findall(r'TRL\s*(\d)', model.part_b_text, re.IGNORECASE)]
        if 'innovation action' in at_lower and trl_nums:
            low_trls = [t for t in trl_nums if t < 4]
            if low_trls:
                result.add("IA + Low TRL Mismatch", "HIGH", 0,
                    f"Innovation Action targets TRL {sorted(set(low_trls))} — IAs should start at TRL 4+.",
                    "Innovation Actions target TRL 5-8. Move basic research to an RIA.",
                    cat, layer)
        if 'research and innovation' in at_lower and trl_nums:
            high_trls = [t for t in trl_nums if t >= 8]
            if len(high_trls) > len(trl_nums) * 0.6:
                result.add("RIA + High TRL Mismatch", "MEDIUM", 0,
                    f"Research & Innovation Action mostly targets TRL 8-9 — consider submitting as IA.",
                    "RIAs target TRL 1-6. Activities at TRL 7-9 belong in an Innovation Action.",
                    cat, layer)

    # --- Industry PM ratio check for IA ---
    if model.action_type and 'innovation' in model.action_type.lower():
        industry_pms = sum(p.person_months for p in model.partners
                          if not any(kw in p.name.lower() for kw in ['university', 'institute', 'centre', 'research']))
        total_pms = sum(p.person_months for p in model.partners if p.person_months > 0)
        if total_pms > 0:
            industry_ratio = industry_pms / total_pms * 100
            if industry_ratio < 30:
                result.add("Low Industry Ratio for IA", "MEDIUM", 0,
                    f"Innovation Action has only {industry_ratio:.0f}% industry PMs.",
                    "IAs are expected to be industry-driven. Reviewers expect ≥40-50% industry effort.",
                    cat, layer)


# ============================================================
# LAYER 2: CALL ALIGNMENT
# ============================================================

def extract_key_phrases(text: str) -> list:
    stop = {'the', 'a', 'an', 'of', 'to', 'in', 'for', 'and', 'or', 'is', 'are',
            'be', 'with', 'that', 'this', 'by', 'on', 'at', 'as', 'from', 'it',
            'will', 'should', 'must', 'shall', 'their', 'they', 'have', 'has',
            'been', 'were', 'was', 'which', 'such', 'these', 'those', 'can',
            'also', 'may', 'not', 'but', 'into', 'its', 'all', 'more', 'new',
            'between', 'through', 'including', 'both', 'each', 'other', 'about'}
    words = re.findall(r'\b[a-z][\w-]+\b', text)
    bigrams = []
    for i in range(len(words) - 1):
        if (words[i] not in stop and words[i+1] not in stop
                and len(words[i]) > 3 and len(words[i+1]) > 3):
            bigrams.append(f"{words[i]} {words[i+1]}")
    return list(set(bigrams))[:20]


def extract_domain_keywords(text: str) -> set:
    stop = {'the', 'a', 'an', 'of', 'to', 'in', 'for', 'and', 'or', 'is', 'are',
            'be', 'with', 'that', 'this', 'by', 'on', 'at', 'as', 'from', 'will',
            'should', 'must', 'shall', 'their', 'they', 'have', 'has', 'been',
            'were', 'was', 'which', 'such', 'these', 'those', 'can', 'also',
            'may', 'not', 'but', 'into', 'its', 'all', 'more', 'new', 'project',
            'proposal', 'work', 'programme', 'horizon', 'europe', 'call', 'topic',
            'action', 'grant', 'consortium', 'partner', 'result', 'activity',
            'expected', 'outcome', 'impact', 'scope', 'objective', 'deliverable'}
    words = set(re.findall(r'\b[a-z][\w-]{4,}\b', text))
    return words - stop


def check_call_alignment(model: ProposalModel, result: AnalysisResult, call_text: Optional[str]):
    cat = "Call Alignment"
    layer = 2

    if not call_text:
        result.add("No Call Text Provided", "HIGH", 0,
            "Cannot verify call alignment without the call text.",
            "Provide --call <file> with the work programme topic text.",
            cat, layer)
        return

    proposal_text = model.part_b_text.lower()
    call_lower = call_text.lower()

    # --- Expected outcomes extraction ---
    expected_outcomes = re.findall(
        r'expected outcome[s]?\s*[:\-]\s*(.*?)(?=\n\n|\nscope|\nexpected|$)',
        call_lower, re.DOTALL
    )
    if expected_outcomes:
        outcome_text = ' '.join(expected_outcomes)
        key_phrases = extract_key_phrases(outcome_text)
        missing = [p for p in key_phrases if p not in proposal_text]
        if missing:
            sample = ', '.join(missing[:5])
            result.add("Call Outcome Gap", "CRITICAL", 0,
                f"Call expected outcomes mention concepts not in proposal: {sample}",
                "Map every expected outcome bullet to a specific WP/task/deliverable.",
                cat, layer)

        # NEW: every expected outcome bullet -> at least one deliverable
        outcome_bullets = re.findall(r'[-•]\s*(.+?)(?=\n[-•]|\n\n|$)', outcome_text)
        deliverable_titles = ' '.join(d.title.lower() for d in model.deliverables)
        unmapped_bullets = []
        for bullet in outcome_bullets[:10]:
            words = [w for w in bullet.lower().split() if len(w) > 5][:3]
            if words and not any(w in deliverable_titles for w in words):
                unmapped_bullets.append(bullet[:60])
        if len(unmapped_bullets) >= 2:
            result.add("Outcomes Without Deliverables", "HIGH", 0,
                f"{len(unmapped_bullets)} expected outcome bullets have no matching deliverable: "
                f"e.g. '{unmapped_bullets[0]}'",
                "Trace each expected outcome to ≥1 deliverable ID in the deliverable table.",
                cat, layer)

    # --- Terminology gap ---
    call_keywords = extract_domain_keywords(call_lower)
    proposal_keywords = extract_domain_keywords(proposal_text)
    call_only = call_keywords - proposal_keywords
    if len(call_only) > 5:
        sample = ', '.join(sorted(call_only)[:8])
        result.add("Call Terminology Gap", "HIGH", 0,
            f"Call uses {len(call_only)} domain terms not in proposal: {sample}",
            "Mirror the call's language — evaluators match your text to call requirements.",
            cat, layer)

    # --- WP parroting ---
    call_sentences = [s.strip() for s in call_lower.split('.') if len(s.strip()) > 40]
    verbatim_count = 0
    for sent in call_sentences[:30]:
        words = sent.split()
        if len(words) >= 8:
            phrase = ' '.join(words[:8])
            if phrase in proposal_text:
                verbatim_count += 1
    if verbatim_count > 3:
        result.add("Work Programme Parrot", "MEDIUM", 0,
            f"{verbatim_count} call sentences appear verbatim in proposal.",
            "Translate the WP into YOUR project's context — don't parrot it.",
            cat, layer)

    # --- TRL alignment ---
    call_trl = re.findall(r'TRL\s*(\d)', call_lower)
    proposal_trl = re.findall(r'TRL\s*(\d)', proposal_text)
    if call_trl and proposal_trl:
        if not set(call_trl) & set(proposal_trl):
            result.add("TRL Mismatch", "CRITICAL", 0,
                f"Call TRL {','.join(sorted(set(call_trl)))} vs proposal TRL {','.join(sorted(set(proposal_trl)))}.",
                "Align your TRL targets with what the call specifies.",
                cat, layer)

    # --- Action type alignment ---
    if 'innovation action' in call_lower or 'horizon-ia' in call_lower:
        low_trl = re.findall(r'TRL\s*[12]', proposal_text, re.IGNORECASE)
        if low_trl:
            result.add("Action Type Mismatch", "HIGH", 0,
                "Innovation Action call but proposal targets TRL 1-2 (basic research).",
                "IAs target TRL 5-7+. Adjust scope or submit as RIA.",
                cat, layer)

    # --- EU policy alignment ---
    eu_policies = {
        'green deal': 'European Green Deal',
        'digital decade': 'Digital Decade',
        'fit for 55': 'Fit for 55',
        'ai act': 'AI Act',
        'data act': 'Data Act',
        'chips act': 'Chips Act',
        'industrial strategy': 'Industrial Strategy',
        'twin transition': 'Twin Transition',
    }
    call_policies = [name for key, name in eu_policies.items() if key in call_lower]
    if call_policies:
        missing_policies = [p for p in call_policies if p.lower() not in proposal_text]
        if missing_policies:
            result.add("Policy Alignment Gap", "MEDIUM", 0,
                f"Call references {', '.join(call_policies)} but proposal misses: {', '.join(missing_policies)}.",
                "Reference the same EU policies the call mentions — evaluators check for this.",
                cat, layer)


# ============================================================
# LAYER 3: FIELD & SMILE
# ============================================================

def check_field_awareness(model: ProposalModel, result: AnalysisResult):
    cat = "Field Awareness"
    layer = 3
    proposal_text = model.part_b_text
    lower = proposal_text.lower()

    # --- Citation recency ---
    years = [yr for _, yr in model.citations_found]
    if years:
        recent = [y for y in years if y >= 2024]
        old = [y for y in years if y < 2020]
        pct_recent = len(recent) / len(years) * 100
        if pct_recent < 20:
            result.add("Stale References", "HIGH", 0,
                f"Only {pct_recent:.0f}% of {len(years)} citations are from 2024+.",
                "At least 30% of references should be from the last 2 years.",
                cat, layer)
        if not old:
            result.add("No Foundational Citations", "MEDIUM", 0,
                "No references older than 2020 — missing seminal/foundational work.",
                "Include foundational papers that established the field.",
                cat, layer)
    else:
        result.add("No Detectable Citations", "HIGH", 0,
            "Could not detect any year-based citations in the proposal.",
            "Include properly formatted citations with years.",
            cat, layer)

    # --- Self-citation ratio ---
    if len(model.citations_found) > 5:
        author_counts = Counter()
        for cite, _ in model.citations_found:
            author = cite.split(',')[0].strip().split()[-1] if ',' in cite else cite.split()[0]
            author_counts[author] += 1
        top_author, top_count = author_counts.most_common(1)[0]
        if top_count > len(model.citations_found) * 0.4:
            result.add("Self-Citation Overload", "MEDIUM", 0,
                f"'{top_author}' appears in {top_count}/{len(model.citations_found)} citations "
                f"({top_count/len(model.citations_found)*100:.0f}%).",
                "Balance self-citations with external validation. >40% self-citation signals arrogance.",
                cat, layer)

    # --- Prior EU projects ---
    project_indicators = ['h2020', 'fp7', 'horizon 2020', 'horizon europe',
                          'project', 'funded by', 'grant agreement']
    prior_projects = sum(1 for p in project_indicators if p in lower)
    if prior_projects < 2:
        result.add("Prior Art Blindness", "HIGH", 0,
            "No references to prior EU-funded projects in the same domain.",
            "Show awareness of what's been funded before and what gap remains.",
            cat, layer)

    # --- Standards bodies ---
    standards_indicators = ['iso ', 'iec ', 'ieee ', 'w3c', 'oasis', 'etsi',
                            'buildingsmart', 'ogc', 'ietf', 'ecma']
    standards_found = [s for s in standards_indicators if s in lower]
    if not standards_found:
        result.add("Standards Blindness", "MEDIUM", 0,
            "No reference to relevant standards bodies (ISO, IEEE, W3C, ETSI, etc.).",
            "Reference applicable standards — evaluators check for standardization awareness.",
            cat, layer)

    # --- Forward vision ---
    future_markers = ['roadmap', 'future work', 'emerging', 'next generation',
                      'post-project', 'beyond the project', '2030', '2035',
                      'long-term', 'vision', 'evolution']
    future_found = [m for m in future_markers if m in lower]
    if len(future_found) < 2:
        result.add("No Forward Vision", "MEDIUM", 0,
            "Proposal lacks forward-looking positioning (roadmap, post-project evolution).",
            "Show where the field is heading and how this project positions for it.",
            cat, layer)


def check_smile_alignment(model: ProposalModel, result: AnalysisResult) -> dict:
    cat = "SMILE Methodology"
    layer = 3
    proposal_text = model.part_b_text.lower()
    phase_scores = {}

    for phase_id, phase in SMILE_PHASES.items():
        # Keyword coverage (max 50% of score)
        markers_found = [m for m in phase["proposal_markers"] if m in proposal_text]
        keyword_coverage = len(markers_found) / len(phase["proposal_markers"]) * 100

        # Structural evidence (max 50% of score)
        structural_found = [s for s in phase["structural_checks"] if s in proposal_text]
        structural_coverage = len(structural_found) / len(phase["structural_checks"]) * 100

        combined = (keyword_coverage + structural_coverage) / 2
        phase_scores[phase["name"]] = combined

        if combined < 15:
            result.add(f"SMILE Gap: {phase['name']}", "MEDIUM", 0,
                f"Phase '{phase['name']}' coverage: {combined:.0f}% (keyword: {keyword_coverage:.0f}%, "
                f"structural: {structural_coverage:.0f}%). {phase['what_to_check']}",
                f"Key question: {phase['key_question']}",
                cat, layer)
        elif combined < 30:
            result.add(f"SMILE Weak: {phase['name']}", "LOW", 0,
                f"Phase '{phase['name']}' only {combined:.0f}% covered — present but shallow.",
                f"Strengthen with: {phase['key_question']}",
                cat, layer)

    # --- Impact-first principle ---
    part_b_pages_text = model.part_b_text[:2000]
    part_b_lower = part_b_pages_text.lower()
    data_first_words = ['data', 'sensor', 'algorithm', 'platform', 'technology',
                        'system', 'framework', 'architecture', 'infrastructure']
    impact_first_words = ['impact', 'outcome', 'benefit', 'challenge', 'problem',
                          'need', 'gap', 'opportunity', 'society', 'citizen']
    data_count = sum(1 for w in data_first_words if w in part_b_lower)
    impact_count = sum(1 for w in impact_first_words if w in part_b_lower)
    if data_count > impact_count * 2:
        result.add("SMILE Violation: Data First", "HIGH", model.part_b_start_page,
            f"Opening text is technology-first ({data_count} tech terms vs {impact_count} impact terms).",
            "SMILE principle: Impact first, data last. Lead with the problem, not the solution.",
            cat, layer)

    # --- Three perspectives ---
    for persp_id, persp in SMILE_PERSPECTIVES.items():
        markers_found = [m for m in persp["markers"] if m in proposal_text]
        if len(markers_found) < 2:
            result.add(f"SMILE Perspective Gap: {persp['name']}", "LOW", 0,
                f"Weak coverage of '{persp['name']}' perspective ({len(markers_found)}/{len(persp['markers'])} markers).",
                "SMILE requires People + Systems + Planet perspectives.",
                cat, layer)

    return phase_scores


# ============================================================
# LAYER 4: ANTI-PATTERNS
# ============================================================

def check_unfilled_placeholders(pages: dict, result: AnalysisResult, start: int):
    placeholders = [
        (r'\[Page limit\]', '[Page limit]'),
        (r'\[insert\s+\w+', '[insert ...]'),
        (r'\[TBD\]', '[TBD]'),
        (r'\[TODO\]', '[TODO]'),
        (r'\[XX+\]', '[XX]'),
        (r'\[fill\s+in\]', '[fill in]'),
        (r'\[placeholder\]', '[placeholder]'),
        (r'\[to be completed\]', '[to be completed]'),
        (r'\[PARTNER NAME\]', '[PARTNER NAME]'),
    ]
    seen = set()
    for num, text in pages.items():
        if num < start:
            continue
        for pattern, label in placeholders:
            if re.search(pattern, text, re.IGNORECASE):
                key = (label, num)
                if key not in seen:
                    seen.add(key)
                    result.add("Unfinished Template", "CRITICAL", num,
                        f"Placeholder found: {label}",
                        "Search for '[', 'insert', 'TBD' before submission.",
                        "Anti-Pattern", 4)


def check_buzzwords(pages: dict, result: AnalysisResult, start: int):
    buzzwords = {
        'human-centric', 'human-centred', 'socio-technical', 'trustworthy',
        'interoperable', 'scalable', 'holistic', 'synergy', 'paradigm',
        'ecosystem', 'cutting-edge', 'novel', 'innovative', 'groundbreaking',
        'transformative', 'disruptive', 'seamless', 'robust', 'comprehensive',
        'unprecedented', 'game-changing', 'next-generation', 'leveraging',
        'world-class', 'state-of-the-art', 'beyond state-of-the-art',
    }
    flagged = 0
    for num, text in pages.items():
        if num < start or is_admin_page(text) or flagged >= 5:
            continue
        words = text.lower().split()
        if len(words) < 50:
            continue
        count = sum(1 for w in words if any(b in w for b in buzzwords))
        density = count / len(words) * 100
        if density > 4:
            flagged += 1
            sev = "HIGH" if density > 6 else "MEDIUM"
            result.add("Buzzword Overload", sev, num,
                f"Density {density:.1f}% ({count}/{len(words)} words are buzzwords).",
                "For every buzzword, add one concrete technical specification.",
                "Anti-Pattern", 4)


def check_opening(pages: dict, result: AnalysisResult, start: int):
    for num in range(start, min(start + 5, max(pages.keys()) + 1)):
        text = pages.get(num, "")
        if 'excellence' not in text.lower():
            continue
        lines = [l.strip() for l in text.split('\n')
                 if len(l.strip()) > 30 and not any(
                     s in l.lower() for s in ['call:', 'horizon', 'eu grants', 'part b'])]
        if lines and len(lines[0]) > 250:
            result.add("Philosophy Lecture Opening", "HIGH", num,
                f"Opening paragraph is {len(lines[0])} chars before specifics.",
                "Project name + problem + solution in ≤100 words.",
                "Anti-Pattern", 4)
        break


def check_baselines(pages: dict, result: AnalysisResult, start: int):
    found = 0
    for num, text in pages.items():
        if num < start or is_admin_page(text) or found >= 8:
            continue
        matches = re.findall(r'>=?\s*\d+\s*%|≥\s*\d+\s*%|<=?\s*\d+\s*%|≤\s*\d+\s*%', text)
        if matches:
            lower = text.lower()
            has_ref = any(b in lower for b in ['baseline', 'compared to', 'current state-of', 'measured against'])
            has_cite = bool(re.search(r'\(\w+[\s,]+\d{4}\)|\[\d+\]', text))
            if not has_ref and not has_cite:
                found += 1
                result.add("Phantom Baseline", "HIGH", num,
                    f"KPI '{matches[0]}' stated without a cited baseline.",
                    "Every KPI: metric + SotA value (cited) + target + measurement method.",
                    "Anti-Pattern", 4)


def check_ghost_partners(pages: dict, result: AnalysisResult, start: int):
    for num, text in pages.items():
        if num < start:
            continue
        if ('capacity of participant' not in text.lower()
                and 'consortium as a whole' not in text.lower()):
            continue
        for line in text.split('\n'):
            stripped = line.strip()
            if 20 < len(stripped) < 130:
                if re.match(r'^[A-Z]{2,10}\s+(contributes?|supports?|leads?|is supporting|provides?)\b', stripped):
                    result.add("Ghost Partner", "HIGH", num,
                        f"Thin description ({len(stripped)} chars): '{stripped[:100]}'",
                        "Each partner: org profile + prior projects + named personnel.",
                        "Anti-Pattern", 4)


def check_copy_paste_ssh(pages: dict, result: AnalysisResult, start: int):
    blocks = []
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        for m in re.findall(
            r'(?:SSH|Human.centric|[Ss]ociet\w+)\s*(?:dimension|relevance)[:\s]+(.*?)(?:\n\n|\n[A-Z])',
            text, re.DOTALL
        ):
            clean = ' '.join(m.split())[:300]
            if len(clean) > 60:
                blocks.append((num, clean))
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            if blocks[i][0] == blocks[j][0]:
                continue
            wa = set(blocks[i][1].lower().split())
            wb = set(blocks[j][1].lower().split())
            if wa and wb and len(wa & wb) / max(len(wa), len(wb)) > 0.55:
                result.add("Copy-Paste SSH Section", "CRITICAL", blocks[j][0],
                    f"SSH text on p.{blocks[j][0]} is ~{int(len(wa&wb)/max(len(wa),len(wb))*100)}% identical to p.{blocks[i][0]}.",
                    "Each section/pilot needs unique SSH analysis.",
                    "Anti-Pattern", 4)


def check_risks(pages: dict, result: AnalysisResult, start: int, model: ProposalModel):
    all_lower = model.part_b_text.lower()
    has_conflict = any(w in all_lower for w in ['post-conflict', 'war zone', 'kharkiv', 'reconstruction', 'conflict zone'])

    for num, text in pages.items():
        if num < start:
            continue
        lower = text.lower()
        if 'risk' not in lower or ('likelihood' not in lower and 'severity' not in lower
                                   and 'probability' not in lower):
            continue

        medium = len(re.findall(r'\bmedium\b', lower))
        low_count = len(re.findall(r'\blow\b', lower))
        if medium >= 4 and low_count == 0:
            result.add("All-Medium Risk Table", "MEDIUM", num,
                f"All {medium} risks rated Medium — no Low or High ratings visible.",
                "Vary ratings. Add management + market + regulatory risks.",
                "Anti-Pattern", 4)

        tech_risk_words = ['technical', 'performance', 'integration', 'data', 'system']
        mgmt_risk_words = ['personnel', 'partner', 'management', 'coordination', 'key person']
        market_risk_words = ['market', 'regulatory', 'competition', 'adoption', 'commercial']
        has_tech = any(w in lower for w in tech_risk_words)
        has_mgmt = any(w in lower for w in mgmt_risk_words)
        has_market = any(w in lower for w in market_risk_words)
        if has_tech and not has_mgmt and not has_market:
            result.add("Technical-Only Risks", "MEDIUM", num,
                "Risk register only covers technical risks.",
                "Add management risks (personnel, coordination) and market/regulatory risks.",
                "Anti-Pattern", 4)

        if has_conflict and 'conflict' not in lower and 'security' not in lower:
            result.add("Unaddressed Conflict-Zone Risk", "CRITICAL", num,
                "Proposal involves conflict-zone activities but risk table has no conflict/security risk.",
                "Add a dedicated risk entry for conflict-zone operations.",
                "Anti-Pattern", 4)
        break


def check_timeline(pages: dict, result: AnalysisResult, start: int):
    wp_timing = {}
    for num, text in pages.items():
        if num < start:
            continue
        for wp, s, e in re.findall(
            r'Work package (?:number\s+)?(\d+).*?M(\d+)\s*[-–]\s*M?(\d+)',
            text, re.DOTALL
        ):
            wp_timing[int(wp)] = (int(s), int(e))
    for pilot_wp in [w for w in wp_timing if w >= 7]:
        for comp_wp in [w for w in wp_timing if 3 <= w <= 6]:
            if wp_timing[pilot_wp][0] < wp_timing[comp_wp][1] - 6:
                result.add("Time-Travel Deliverable", "HIGH", 0,
                    f"WP{pilot_wp} starts M{wp_timing[pilot_wp][0]} but WP{comp_wp} ends M{wp_timing[comp_wp][1]}.",
                    "Integration WPs must follow component delivery.",
                    "Anti-Pattern", 4)


def check_exploitation(pages: dict, result: AnalysisResult, start: int):
    for num, text in pages.items():
        if num < start:
            continue
        lower = text.lower()
        if 'exploitation' not in lower or ('strategy' not in lower and 'plan' not in lower):
            continue
        specific = any(m in lower for m in ['eur ', '€', 'revenue', 'pricing', 'saas', 'license fee', 'licensing'])
        generic = any(m in lower for m in ['partners will', 'results will be', 'will integrate', 'plan to'])
        if generic and not specific:
            result.add("Exploitation Fog", "HIGH", num,
                "Generic exploitation — no named partner plans with revenue models.",
                "Each partner: WHAT product + WHICH market + WHEN + revenue model.",
                "Anti-Pattern", 4)
            break


def check_market(pages: dict, result: AnalysisResult, start: int):
    for num, text in pages.items():
        if num < start:
            continue
        if re.search(r'(?:USD|EUR|€|\$)\s*[\d,.]+\s*(?:bn|billion|trillion)', text, re.IGNORECASE):
            if not any(w in text.lower() for w in ['addressable', 'serviceable', 'sub-segment', 'target segment']):
                result.add("TAM Distraction", "MEDIUM", num,
                    "Large market figure cited without sub-segment drill-down.",
                    "Total market → addressable → serviceable → your capture path. Cite sources.",
                    "Anti-Pattern", 4)
                break


def check_output_outcome_impact(pages: dict, result: AnalysisResult, start: int):
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        lower = text.lower()
        if 'expected outcome' not in lower and 'expected impact' not in lower:
            continue
        if 'outcome' in lower and 'impact' in lower:
            outcome_pos = lower.find('outcome')
            outcome_section = lower[outcome_pos:outcome_pos + 500]
            publish_words = ['publish', 'paper', 'conference', 'journal', 'disseminat']
            if any(p in outcome_section for p in publish_words):
                result.add("Output-Outcome Confusion", "MEDIUM", num,
                    "Publications listed as outcomes — publications are outputs, not outcomes.",
                    "Outputs=what you produce. Outcomes=what changes. Impacts=long-term societal change.",
                    "Anti-Pattern", 4)
                break


def check_dissemination_exploitation_conflation(pages: dict, result: AnalysisResult, start: int):
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        lower = text.lower()
        if 'dissemination' not in lower or 'exploitation' not in lower:
            continue
        combined = lower.count('dissemination and exploitation') + lower.count('exploitation and dissemination')
        separate_d = lower.count('dissemination') - combined * 2
        separate_e = lower.count('exploitation') - combined * 2
        if combined > 3 and separate_d < 2 and separate_e < 2:
            result.add("D&E Conflation", "MEDIUM", num,
                "Dissemination and exploitation always appear together, never separately.",
                "These are different: dissemination=awareness, exploitation=economic/policy value creation.",
                "Anti-Pattern", 4)
            break


def check_governance(pages: dict, result: AnalysisResult, start: int):
    for num, text in pages.items():
        if num < start:
            continue
        lower = text.lower()
        governance_terms = ['general assembly', 'steering committee', 'advisory board',
                            'project board', 'executive committee']
        if sum(1 for g in governance_terms if g in lower) < 2:
            continue
        if not any(p in lower for p in ['conflict resolution', 'contingency', 'escalation', 'ip dispute', 'decision making']):
            result.add("Governance Template", "MEDIUM", num,
                "Standard governance structure without project-specific conflict/IP mechanisms.",
                "Add: conflict resolution procedure, IP governance, escalation paths.",
                "Anti-Pattern", 4)
        break


def check_acronyms(model: ProposalModel, result: AnalysisResult):
    safe = {'EU', 'AI', 'XR', 'VR', 'AR', 'MR', 'BIM', 'GIS', 'API', 'SSH', 'KPI',
            'TRL', 'DMP', 'FAIR', 'GDPR', 'SME', 'IOT', 'CEO', 'CTO', 'RIA',
            'HTTP', 'JSON', 'CSV', 'PDF', 'URL', 'GPU', 'CPU', 'HPC', 'WP', 'PM',
            'THE', 'AND', 'FOR', 'NOT', 'BUT', 'NOR', 'YET', 'CSA', 'ERC', 'ETF',
            'NATO', 'WHO', 'UN', 'ICT', 'IoT', 'ML', 'NLP', 'LLM', 'UAV', 'UAS'}
    text = model.part_b_text
    used = model.acronyms_used - safe
    # Filter: look for definition pattern "(ACRONYM)" near expanded form
    defined = set()
    for acr in used:
        if re.search(rf'\([^)]*{acr}[^)]*\)', text) or re.search(rf'\b{acr}\b.*?means', text):
            defined.add(acr)
    undefined = used - defined - model.acronyms_defined
    undefined = {a for a in undefined if len(a) >= 3 and not a.isdigit()}
    if len(undefined) > 8:
        result.add("Orphaned Acronyms", "LOW", 0,
            f"{len(undefined)} potentially undefined acronyms: {', '.join(sorted(undefined)[:12])}",
            "Master acronym list + define at first use.",
            "Anti-Pattern", 4)


def check_sota(pages: dict, result: AnalysisResult, start: int):
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        lower = text.lower()
        if ('state of the art' in lower or 'state-of-the-art' in lower) and ('advancement' in lower or 'beyond' in lower):
            competitors = ['nvidia', 'omniverse', 'unity', 'unreal', 'microsoft',
                           'bentley', 'siemens', 'dassault', 'autodesk', 'cesium',
                           'google', 'meta', 'amazon', 'oracle', 'sap', 'ibm']
            if not any(c in lower for c in competitors):
                result.add("Reinvented Wheel", "HIGH", num,
                    "Proposal claims beyond-SotA without naming any commercial competitors.",
                    "Name and cite competitors, explain the specific gap you fill.",
                    "Anti-Pattern", 4)
            break


def check_partner_driven_wps(model: ProposalModel, result: AnalysisResult):
    """Detect WP-per-partner structure (anti-pattern: each partner owns one WP)."""
    if len(model.work_packages) < 3 or len(model.partners) < 3:
        return
    leads = [wp.lead for wp in model.work_packages if wp.lead]
    if not leads:
        return
    lead_counts = Counter(leads)
    unique_leads = len(lead_counts)
    # If number of unique WP leads equals number of WPs, each partner owns exactly one WP
    if unique_leads == len(leads) and unique_leads >= len(model.partners) - 1:
        result.add("Partner-Driven WP Structure", "HIGH", 0,
            f"Each partner appears to lead exactly one WP ({unique_leads} WPs, {unique_leads} different leads).",
            "WPs should be structured around research objectives, not partner territories. "
            "Partner-driven WPs signal poor integration.",
            "Anti-Pattern", 4)


def check_ai_disclosure(model: ProposalModel, result: AnalysisResult):
    """If AI/ML is in the proposal, check for AI tool disclosure."""
    lower = model.part_b_text.lower()
    has_ai = any(t in lower for t in [
        'machine learning', 'deep learning', 'neural network', 'large language model',
        'generative ai', 'chatgpt', 'gpt-4', 'llm', 'foundation model'
    ])
    if has_ai:
        has_disclosure = any(d in lower for d in [
            'ai tool', 'ai-generated', 'generated with', 'written with',
            'assisted by ai', 'ai assistance', 'disclosure'
        ])
        if not has_disclosure:
            result.add("AI Tool Disclosure Missing", "LOW", 0,
                "Proposal uses AI/ML as a topic but does not disclose AI tool usage in writing.",
                "HE now requires disclosure if AI tools were used in preparing the proposal text.",
                "Anti-Pattern", 4)


def check_lump_sum(pages: dict, result: AnalysisResult, start: int):
    """Check for lump-sum WP design issues."""
    for num, text in pages.items():
        if num < start:
            continue
        lower = text.lower()
        if 'lump sum' not in lower and 'lump-sum' not in lower:
            continue
        # In lump-sum, each WP must have a fixed price — check for per-WP budget
        wp_budgets = re.findall(r'WP\s*\d+.*?EUR\s*[\d,]+', text, re.IGNORECASE)
        if not wp_budgets:
            result.add("Lump-Sum WP Budget Missing", "HIGH", num,
                "Proposal uses lump-sum scheme but no per-WP budget breakdown detected.",
                "Lump-sum grants require a fixed budget per WP — include WP cost tables.",
                "Anti-Pattern", 4)
        break


def check_meeting_milestones(pages: dict, result: AnalysisResult, start: int):
    for num, text in pages.items():
        if num < start or is_admin_page(text):
            continue
        lower = text.lower()
        if 'milestone' not in lower:
            continue
        bad_milestones = re.findall(
            r'(?:milestone|ms\s*\d+)[:\s]*(.*?(?:meeting|workshop|review|kick.?off|conference|webinar).*?)(?:\n|$)',
            lower
        )
        if bad_milestones:
            result.add("Meeting Milestones", "HIGH", num,
                f"Milestone is an event, not a verifiable achievement: '{bad_milestones[0][:80]}'",
                "Milestones must be concrete verifiable outputs, not calendar events.",
                "Anti-Pattern", 4)
            break


def check_budget_narrative(pages: dict, result: AnalysisResult, start: int):
    """Check that each WP has a budget narrative, not just tables."""
    for num, text in pages.items():
        if num < start:
            continue
        lower = text.lower()
        if 'budget' not in lower and 'costs' not in lower:
            continue
        # Look for cost justification text
        has_justification = any(w in lower for w in [
            'personnel costs are justified', 'cost justification',
            'rates are based on', 'hourly rate', 'daily rate',
            'cost breakdown', 'budget breakdown'
        ])
        has_table = bool(re.search(r'\d{4,}\s+\d{4,}', text))  # numeric table
        if has_table and not has_justification:
            result.add("Budget Table Without Narrative", "MEDIUM", num,
                "Budget appears as numbers only with no cost justification narrative.",
                "Add narrative explaining personnel rates, equipment necessity, travel rationale.",
                "Anti-Pattern", 4)
            break


def check_consortium_diversity(model: ProposalModel, result: AnalysisResult):
    """Score country diversity; flag low-diversity consortia."""
    if not model.partners:
        return
    countries = Counter(p.country for p in model.partners if p.country)
    n_countries = len(countries)
    n_partners = len(model.partners)
    if n_countries == 0:
        return
    diversity = n_countries / n_partners  # 1.0 = all different countries

    # Flag if too concentrated in one country
    dominant_country, dominant_count = countries.most_common(1)[0]
    if dominant_count > n_partners * 0.5 and n_partners >= 4:
        result.add("Low Country Diversity", "MEDIUM", 0,
            f"{dominant_count}/{n_partners} partners from {dominant_country} — consortium may lack geographic balance.",
            "Horizon Europe values geographic spread. Consider broadening to Widening countries.",
            "Anti-Pattern", 4)

    # Positive signal: includes widening countries
    widening = {'BG', 'HR', 'CY', 'CZ', 'EE', 'HU', 'LV', 'LT', 'MT', 'PL',
                'PT', 'RO', 'SK', 'SI', 'AL', 'BA', 'MK', 'MD', 'ME', 'RS', 'UA'}
    has_widening = any(p.country in widening for p in model.partners if p.country)
    if has_widening and n_countries >= 4:
        # This is a positive signal — no finding raised, but noted in score bonus
        pass


# ============================================================
# PRE-FLIGHT RUNNER
# ============================================================

def run_pre_flight(model: ProposalModel, call_text: Optional[str]) -> list:
    """Run the 10-question pre-flight checklist. Returns list of (question_dict, result)."""
    results = []
    for q in PRE_FLIGHT_CHECKLIST:
        try:
            outcome = q["check"](model, call_text)
        except Exception:
            outcome = None
        results.append((q, outcome))
    return results


def format_pre_flight(pf_results: list) -> list:
    """Format pre-flight results as report lines."""
    lines = []
    lines.append("  PRE-FLIGHT CHECKLIST (10 gatekeepers)")
    lines.append("  " + "-" * 72)
    blockers = 0
    warnings = 0
    for q, outcome in pf_results:
        if outcome is True:
            icon = "PASS"
        elif outcome is False:
            icon = "FAIL"
            if q["weight"] == "BLOCKER":
                blockers += 1
            else:
                warnings += 1
        else:
            icon = "????"
            warnings += 1
        lines.append(f"  [{icon}] Q{q['id']:>2}. {q['question']}")
        if outcome is not True:
            lines.append(f"         {q['why'][:90]}")
    lines.append("")
    if blockers > 0:
        lines.append(f"  !! {blockers} BLOCKER(S) DETECTED — proposal may be desk-rejected")
    elif warnings > 0:
        lines.append(f"  ~  {warnings} item(s) need manual verification")
    else:
        lines.append(f"  All 10 pre-flight checks PASSED")
    lines.append("")
    return lines


# ============================================================
# EIC PATHFINDER SCORING (when --eic-pathfinder flag is used)
# ============================================================

def score_eic_pathfinder(model: ProposalModel, result: AnalysisResult) -> dict:
    """Score proposal against EIC Pathfinder Open sub-criteria."""
    text = model.full_text.lower() if model.full_text else ""
    scores = {}

    for criterion_key, criterion in EIC_PATHFINDER_CRITERIA.items():
        sub_scores = {}
        for sub_key, sub in criterion["sub_criteria"].items():
            base = 3.0
            bonus = 0.0
            penalty = 0.0

            pos_found = sum(1 for m in sub["markers_positive"] if m in text)
            neg_found = sum(1 for m in sub["markers_negative"] if m in text)

            bonus += min(1.5, pos_found * 0.15)
            penalty += neg_found * 0.3

            sub_score = round(max(1.0, min(5.0, base + bonus - penalty)), 1)
            sub_scores[sub_key] = {
                "name": sub["name"],
                "score": sub_score,
                "positive_markers": pos_found,
                "negative_markers": neg_found,
            }

        avg = sum(s["score"] for s in sub_scores.values()) / len(sub_scores)
        scores[criterion_key] = {
            "weight": criterion["weight"],
            "threshold": criterion["threshold"],
            "sub_criteria": sub_scores,
            "average": round(avg, 2),
            "passes_threshold": avg >= criterion["threshold"],
        }

    weighted = sum(
        scores[k]["average"] * scores[k]["weight"]
        for k in scores
    )
    scores["_weighted_total"] = round(weighted, 2)
    scores["_max_possible"] = 5.0
    return scores


def format_eic_pathfinder_scores(scores: dict) -> list:
    """Format EIC Pathfinder scores as report lines."""
    lines = []
    lines.append("  EIC PATHFINDER OPEN — CALL-SPECIFIC SCORING")
    lines.append("  " + "-" * 72)
    lines.append("  Weights: Excellence 50% | Impact 30% | Implementation 20%")
    lines.append("  Thresholds: Excellence >=4.0 | Impact >=3.5 | Implementation >=3.0")
    lines.append("")

    for criterion_key in ["Excellence", "Impact", "Implementation"]:
        c = scores[criterion_key]
        status = "PASS" if c["passes_threshold"] else "FAIL"
        filled = int((c["average"] - 1.0) / 4.0 * 20)
        bar = "#" * filled + "." * (20 - filled)
        lines.append(f"  {criterion_key:<16} {c['average']:.1f}/5.0  [{bar}]  "
                      f"threshold {c['threshold']}  [{status}]  (weight {int(c['weight']*100)}%)")
        for sub_key, sub in c["sub_criteria"].items():
            s_filled = int((sub["score"] - 1.0) / 4.0 * 16)
            s_bar = "#" * s_filled + "." * (16 - s_filled)
            lines.append(f"    {sub['name']:<36} {sub['score']}/5.0  [{s_bar}]  "
                          f"(+{sub['positive_markers']} / -{sub['negative_markers']})")
        lines.append("")

    wt = scores["_weighted_total"]
    lines.append(f"  WEIGHTED TOTAL:  {wt:.2f} / 5.00")

    all_pass = all(scores[k]["passes_threshold"] for k in ["Excellence", "Impact", "Implementation"])
    if all_pass and wt >= 4.0:
        lines.append(f"  VERDICT:  COMPETITIVE (all thresholds passed, weighted >=4.0)")
    elif all_pass:
        lines.append(f"  VERDICT:  PASSES THRESHOLDS but weighted score is low — may not rank high enough")
    else:
        failing = [k for k in ["Excellence", "Impact", "Implementation"]
                    if not scores[k]["passes_threshold"]]
        lines.append(f"  VERDICT:  FAILS THRESHOLD on {', '.join(failing)} — will be rejected")
    lines.append("")
    return lines


# ============================================================
# STRATEGIC DIMENSION SCORING
# ============================================================

def score_strategic_dimensions(model: ProposalModel) -> dict:
    """Score proposal across 8 strategic dimensions beyond call criteria."""
    text = model.full_text.lower() if model.full_text else ""
    scores = {}

    for dim_key, dim in STRATEGIC_DIMENSIONS.items():
        found = sum(1 for m in dim["markers"] if m in text)
        total = len(dim["markers"])
        raw_pct = (found / total * 100) if total > 0 else 0
        score_5 = round(max(1.0, min(5.0, 1.0 + raw_pct * 0.04)), 1)
        scores[dim_key] = {
            "name": dim["name"],
            "score": score_5,
            "found": found,
            "total": total,
            "weight": dim["weight"],
            "description": dim["description"],
        }

    weighted_sum = sum(s["score"] * s["weight"] for s in scores.values())
    total_weight = sum(s["weight"] for s in scores.values())
    scores["_weighted_avg"] = round(weighted_sum / total_weight, 2) if total_weight else 0
    return scores


def format_strategic_dimensions(scores: dict) -> list:
    """Format strategic dimension scores as report lines."""
    lines = []
    lines.append("  STRATEGIC DIMENSIONS (beyond call criteria)")
    lines.append("  " + "-" * 72)
    for dim_key, dim in sorted(scores.items(), key=lambda x: x[1].get("weight", 0) if isinstance(x[1], dict) and "weight" in x[1] else 0, reverse=True):
        if dim_key.startswith("_"):
            continue
        filled = int((dim["score"] - 1.0) / 4.0 * 16)
        bar = "#" * filled + "." * (16 - filled)
        lines.append(f"  {dim['name']:<24} {dim['score']}/5.0  [{bar}]  "
                      f"({dim['found']}/{dim['total']} markers, weight {dim['weight']}%)")
    lines.append("")
    lines.append(f"  STRATEGIC WEIGHTED AVG:  {scores['_weighted_avg']:.2f} / 5.00")
    lines.append("")
    return lines


# ============================================================
# SCORING  (base 3.0, bonuses up to +2.0, penalties up to -2.0)
# ============================================================

SEVERITY_WEIGHTS = {"CRITICAL": 0.8, "HIGH": 0.4, "MEDIUM": 0.12, "LOW": 0.03}

CRITERION_MAP = {
    "Excellence": {
        "layers": [1, 2, 3],
        "patterns": [
            "Call Outcome Gap", "Call Terminology Gap", "TRL Mismatch", "Action Type Mismatch",
            "IA + Low TRL Mismatch", "RIA + High TRL Mismatch",
            "Stale References", "No Foundational Citations", "Prior Art Blindness",
            "Self-Citation Overload", "No Forward Vision", "Standards Blindness",
            "SMILE Violation: Data First", "Philosophy Lecture Opening",
            "Buzzword Overload", "Phantom Baseline", "Reinvented Wheel",
            "Abstract-Body Disconnect", "Abstract Too Short",
        ] + [f"SMILE Gap: {p['name']}" for p in SMILE_PHASES.values()],
        "bonus_patterns": ["No Detectable Citations"],
    },
    "Impact": {
        "layers": [2, 3, 4],
        "patterns": [
            "Policy Alignment Gap", "Work Programme Parrot",
            "Outcomes Without Deliverables", "Call Outcome Gap",
            "Exploitation Fog", "TAM Distraction", "Copy-Paste SSH Section",
            "Output-Outcome Confusion", "D&E Conflation",
            "AI Tool Disclosure Missing",
        ],
        "bonus_patterns": [],
    },
    "Implementation": {
        "layers": [1, 4],
        "patterns": [
            "Consortium Too Small", "Country Diversity Insufficient",
            "Zero-PM Task Lead", "WP Exceeds Duration", "WP Invalid Dates",
            "Orphaned Deliverable References", "Meeting Milestone",
            "Unfinished Template", "Ghost Partner", "Time-Travel Deliverable",
            "All-Medium Risk Table", "Governance Template", "Unaddressed Conflict-Zone Risk",
            "Meeting Milestones", "Technical-Only Risks", "Zero-PM Task Lead",
            "Page Limit Risk", "Heavy Management WP", "Orphaned Acronyms",
            "Partner-Driven WP Structure", "High Subcontracting Ratio",
            "Lump-Sum WP Budget Missing", "Budget Table Without Narrative",
            "Low Country Diversity", "Low Industry Ratio for IA",
            "Under-Resourced Management",
        ],
        "bonus_patterns": [],
    },
}


def estimate_scores(result: AnalysisResult, model: ProposalModel) -> dict:
    scores = {}
    for criterion, cfg in CRITERION_MAP.items():
        base = 3.0
        penalty = 0.0
        bonus = 0.0

        all_patterns = cfg["patterns"]

        for f in result.findings:
            if f.pattern in all_patterns:
                penalty += SEVERITY_WEIGHTS.get(f.severity, 0.1)

        # Bonus: citations found
        if criterion == "Excellence":
            if model.citations_found:
                years = [yr for _, yr in model.citations_found]
                recent_pct = len([y for y in years if y >= 2023]) / len(years) * 100
                if recent_pct >= 30:
                    bonus += 0.3
                if len(years) >= 20:
                    bonus += 0.2
            if model.kpis_found:
                bonus += min(0.3, len(model.kpis_found) * 0.05)
            if model.abstract_text and len(model.abstract_text) >= 1000:
                bonus += 0.2

        if criterion == "Impact":
            if model.deliverables:
                bonus += min(0.4, len(model.deliverables) * 0.04)
            if model.milestones:
                bonus += min(0.2, len(model.milestones) * 0.05)

        if criterion == "Implementation":
            if len(model.partners) >= 5:
                bonus += 0.2
            countries = set(p.country for p in model.partners if p.country)
            if len(countries) >= 5:
                bonus += 0.2
            if model.work_packages and model.tasks:
                bonus += 0.1
            if model.risks:
                risk_cats = set()
                for r in model.risks:
                    rl = r.description.lower()
                    if any(w in rl for w in ['technical', 'system', 'data']):
                        risk_cats.add('technical')
                    if any(w in rl for w in ['partner', 'personnel', 'management']):
                        risk_cats.add('management')
                    if any(w in rl for w in ['market', 'regulatory', 'adoption']):
                        risk_cats.add('market')
                bonus += len(risk_cats) * 0.1

        score = base + bonus - penalty
        scores[criterion] = round(max(1.0, min(5.0, score)), 1)
    return scores


# ============================================================
# BUDGET ANALYSIS MODE
# ============================================================

def run_budget_analysis(model: ProposalModel, result: AnalysisResult):
    """Dedicated budget analysis for --budget flag."""
    cat = "Budget Analysis"
    layer = 1

    if model.budget_total == 0:
        result.add("Budget Not Parseable", "HIGH", 0,
            "Could not extract total budget from the document.",
            "Budget tables may use non-standard formatting.",
            cat, layer)
        return

    # EU contribution rate
    if model.budget_eu > 0 and model.budget_total > 0:
        eu_rate = model.budget_eu / model.budget_total * 100
        if eu_rate > 100:
            result.add("EU Rate Exceeds 100%", "CRITICAL", 0,
                f"EU contribution ({eu_rate:.1f}%) exceeds total budget.",
                "Check budget calculation — EU rate for RIA is 100%, IA is 70% for profit entities.",
                cat, layer)
        elif eu_rate > 100.1:
            pass
        elif eu_rate < 60:
            result.add("Low EU Contribution Rate", "LOW", 0,
                f"EU contribution rate is {eu_rate:.1f}% — lower than typical.",
                "RIA: 100% for non-profits, 100% for profit entities. IA: 70% for profit entities.",
                cat, layer)

    # Personnel cost share
    if model.budget_total > 0 and model.personnel_total > 0:
        pers_pct = model.personnel_total / model.budget_total * 100
        if pers_pct < 30:
            result.add("Low Personnel Cost Share", "MEDIUM", 0,
                f"Personnel costs are only {pers_pct:.1f}% of total budget.",
                "Personnel is typically 50-70% of HE budgets. Low share may signal equipment/subcontracting inflation.",
                cat, layer)
        elif pers_pct > 85:
            result.add("Very High Personnel Share", "LOW", 0,
                f"Personnel costs are {pers_pct:.1f}% of total budget.",
                "Very high personnel share — check if travel/equipment/indirect are correctly allocated.",
                cat, layer)

    # Indirect cost rate check (flat rate is 25% of direct costs)
    if model.personnel_total > 0 and model.indirect_total > 0:
        direct_costs = (model.personnel_total + model.equipment_total +
                        model.travel_total + model.subcontracting_total)
        expected_indirect = direct_costs * 0.25
        actual_rate = model.indirect_total / direct_costs * 100 if direct_costs > 0 else 0
        if abs(actual_rate - 25) > 5:
            result.add("Indirect Cost Rate Unexpected", "MEDIUM", 0,
                f"Indirect costs are {actual_rate:.1f}% of direct costs (HE flat rate is 25%).",
                "Unless using actual indirect costs (rare), the flat rate is 25%.",
                cat, layer)


# ============================================================
# REPORT
# ============================================================

def format_report(result: AnalysisResult, pdf_path: str, model: ProposalModel,
                  smile_scores: Optional[dict] = None, has_call: bool = False,
                  budget_mode: bool = False,
                  eic_pathfinder: bool = False,
                  pf_results: Optional[list] = None,
                  eic_scores: Optional[dict] = None,
                  strategic_scores: Optional[dict] = None,
                  future_scores: Optional[dict] = None) -> str:
    scores = estimate_scores(result, model)
    total = sum(scores.values())
    severity_counts = Counter(f.severity for f in result.findings)
    layer_counts = Counter(f.layer for f in result.findings)
    pattern_counts = Counter(f.pattern for f in result.findings)

    lines = []
    w = 76

    lines.append("")
    lines.append("=" * w)
    lines.append("  C.R.U.C.I.B.L.E. v" + __version__)
    lines.append("  Consortia Review Under Controlled Interrogation")
    lines.append("  Before Live Evaluation")
    if eic_pathfinder:
        lines.append("  MODE: EIC Pathfinder Open 2026")
    lines.append("=" * w)
    lines.append(f"  File:        {Path(pdf_path).name}")
    lines.append(f"  Pages:       {model.total_pages}")
    lines.append(f"  Findings:    {len(result.findings)}")
    lines.append(f"  Call text:   {'provided' if has_call else 'NOT PROVIDED (Layer 2 limited)'}")
    lines.append("")

    # --- Proposal snapshot ---
    lines.append("  PROPOSAL SNAPSHOT")
    lines.append("  " + "-" * (w - 4))
    lines.append(f"  Acronym:       {model.acronym or '(not detected)'}")
    if model.title:
        lines.append(f"  Title:         {model.title[:70]}")
    lines.append(f"  Duration:      {model.duration_months}m" if model.duration_months else "  Duration:      (not detected)")
    lines.append(f"  Action type:   {model.action_type or '(not detected)'}")
    lines.append(f"  Call ID:       {model.call_id or '(not detected)'}")
    lines.append(f"  Partners:      {len(model.partners)}" +
                 (f" — {', '.join(set(p.country for p in model.partners if p.country))}"
                  if model.partners else ""))
    lines.append(f"  Work packages: {len(model.work_packages)}" +
                 (f" (WP{model.work_packages[0].number}–WP{model.work_packages[-1].number})"
                  if model.work_packages else ""))
    lines.append(f"  Deliverables:  {len(model.deliverables)}")
    lines.append(f"  Milestones:    {len(model.milestones)}")
    lines.append(f"  Citations:     {len(model.citations_found)}")
    if model.budget_total > 0:
        lines.append(f"  Budget total:  EUR {model.budget_total:>12,.0f}")
    if model.budget_eu > 0:
        lines.append(f"  EU contrib:    EUR {model.budget_eu:>12,.0f}")
    lines.append("")

    # --- Pre-flight checklist (if available) ---
    if pf_results:
        lines.extend(format_pre_flight(pf_results))

    # --- EIC Pathfinder scores (if available) ---
    if eic_scores:
        lines.extend(format_eic_pathfinder_scores(eic_scores))

    # --- Strategic dimensions (if available) ---
    if strategic_scores:
        lines.extend(format_strategic_dimensions(strategic_scores))

    # --- Future Tech Radar (if available) ---
    if future_scores:
        lines.extend(format_future_tech_radar(future_scores))

    # --- Four-layer summary ---
    layer_names = {1: "Structural Integrity", 2: "Call Alignment",
                   3: "Field & SMILE", 4: "Anti-Patterns"}
    lines.append("  FOUR-LAYER ANALYSIS")
    lines.append("  " + "-" * (w - 4))
    for layer in [1, 2, 3, 4]:
        count = layer_counts.get(layer, 0)
        crits = len([f for f in result.findings if f.layer == layer and f.severity == "CRITICAL"])
        highs = len([f for f in result.findings if f.layer == layer and f.severity == "HIGH"])
        lines.append(f"  Layer {layer}: {layer_names[layer]:<24} "
                     f"{count:>3} findings ({crits} critical, {highs} high)")
    lines.append("")

    # --- Score ---
    lines.append("  ESTIMATED SCORE  (base 3.0 + bonuses - penalties, range 1.0-5.0)")
    lines.append("  " + "-" * (w - 4))
    for criterion, score in scores.items():
        filled = int((score - 1.0) / 4.0 * 20)
        bar = "#" * filled + "." * (20 - filled)
        status = "STRONG" if score >= 4.0 else ("OK" if score >= 3.0 else "WEAK")
        lines.append(f"  {criterion:<16} {score}/5.0  [{bar}]  {status}")
    lines.append(f"  {'TOTAL':<16} {total:.1f}/15.0")
    passes = total >= 10.0 and all(s >= 3.0 for s in scores.values())
    lines.append(f"  Threshold:      {'LIKELY ABOVE' if passes else 'AT RISK'}")
    lines.append("")

    # --- SMILE radar ---
    if smile_scores:
        lines.append("  SMILE METHODOLOGY COVERAGE")
        lines.append("  " + "-" * (w - 4))
        for phase, coverage in smile_scores.items():
            bar_len = int(coverage / 5)
            bar = "#" * bar_len + "." * (20 - bar_len)
            status = "STRONG" if coverage >= 50 else ("OK" if coverage >= 25 else "GAP")
            lines.append(f"  {phase:<28} {coverage:>3.0f}%  [{bar}]  {status}")
        lines.append("")

    # --- Severity ---
    lines.append("  SEVERITY SUMMARY")
    lines.append("  " + "-" * (w - 4))
    icons = {"CRITICAL": "!!", "HIGH": "! ", "MEDIUM": "~ ", "LOW": "  "}
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        c = severity_counts.get(sev, 0)
        lines.append(f"  {icons[sev]} {sev:<12} {c}")
    lines.append("")

    lines.append("  TOP ISSUES")
    lines.append("  " + "-" * (w - 4))
    for pattern, count in pattern_counts.most_common(15):
        lines.append(f"  [{count:>3}x] {pattern}")
    lines.append("")

    # --- Findings by layer ---
    lines.append("=" * w)
    lines.append("  FINDINGS BY LAYER")
    lines.append("=" * w)
    for layer in [1, 2, 3, 4]:
        layer_findings = [f for f in result.findings if f.layer == layer]
        if not layer_findings:
            continue
        lines.append(f"\n  === LAYER {layer}: {layer_names[layer].upper()} ===\n")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            sev_findings = [f for f in layer_findings if f.severity == sev]
            if not sev_findings:
                continue
            lines.append(f"  --- {sev} ---")
            for f in sev_findings:
                pg = f"p.{f.page}" if f.page > 0 else "global"
                lines.append(f"  [{f.pattern}] ({pg})")
                lines.append(f"    {f.text}")
                lines.append(f"    -> {f.suggestion}")
                lines.append("")

    # --- Checklist ---
    lines.append("=" * w)
    lines.append("  PRE-SUBMISSION CHECKLIST")
    lines.append("=" * w)
    checklist = [
        "STRUCTURAL: ≥3 partners from ≥3 eligible countries confirmed",
        "STRUCTURAL: All WP end months within project duration",
        "STRUCTURAL: Every deliverable ID in text also in deliverable table",
        "STRUCTURAL: No milestones that are meetings/workshops",
        "STRUCTURAL: No partner with zero PMs leads tasks",
        "STRUCTURAL: Subcontracting <30% of total budget (or justified)",
        "STRUCTURAL: Management WP 5-10% of total effort",
        "STRUCTURAL: Abstract has problem/solution/impact structure (1500-2000 chars)",
        "STRUCTURAL: Gender balance in named researchers checked",
        "STRUCTURAL: Ethics self-assessment complete",
        "CALL: Every expected outcome bullet maps to ≥1 deliverable",
        "CALL: Call terminology mirrored (not paraphrased)",
        "CALL: TRL targets align with call specification",
        "CALL: Action type (RIA/IA/CSA) consistent with TRL targets",
        "CALL: Referenced EU policies match call text",
        "FIELD: ≥30% citations from last 2 years",
        "FIELD: Seminal/foundational work cited (pre-2020)",
        "FIELD: Prior EU-funded projects referenced",
        "FIELD: Specific standards bodies named (ISO/IEEE/W3C/ETSI)",
        "FIELD: Forward vision present (roadmap, post-project, 2030+)",
        "SMILE: Impact first, data last — opening leads with problem",
        "SMILE: All 6 phases addressed (Reality→Wisdom)",
        "SMILE: Three perspectives covered (People/Systems/Planet)",
        "SMILE: Stakeholder table/matrix present (Reality Emulation)",
        "SMILE: Validation methodology defined (Concurrent Engineering)",
        "SMILE: Specific ontologies/standards named (Collective Intelligence)",
        "SMILE: Decision support outputs defined (Contextual Intelligence)",
        "SMILE: AI maturity path described (Continuous Intelligence)",
        "SMILE: Open source/sustainability plan (Perpetual Wisdom)",
        "ANTI: All placeholders removed ([TBD], [insert], [XX])",
        "ANTI: Every KPI has a cited baseline + measurement method",
        "ANTI: Each partner has ≥1 paragraph with profile + personnel",
        "ANTI: WPs structured by objective, not by partner territory",
        "ANTI: Risk table covers technical + management + market risks",
        "ANTI: Outputs ≠ outcomes ≠ impacts (defined separately)",
        "ANTI: Exploitation names partner + product + market + revenue model",
        "ANTI: Dissemination and exploitation treated separately",
        "ANTI: Governance has conflict resolution + IP escalation path",
        "ANTI: Commercial competitors named in SotA section",
        "ANTI: No time-travel deliverables (integration before components)",
        "ANTI: Page limit checked: 40 for RIA/IA, 25 for CSA",
        "ANTI: Acronym list complete, all defined at first use",
        "ANTI: AI tool usage disclosed if AI used in writing",
        "BUDGET: Personnel cost per PM within country benchmarks",
        "FINAL: Spellcheck + read by non-author reviewer",
    ]
    for item in checklist:
        lines.append(f"  [ ] {item}")
    lines.append("")

    return "\n".join(lines)


# ============================================================
# MAIN ORCHESTRATION
# ============================================================

def run_analysis(pdf_path: str, call_path: Optional[str] = None,
                 verbose: bool = False, budget_mode: bool = False,
                 eic_pathfinder: bool = False):
    pages, page_count = extract_text(pdf_path)

    if verbose:
        print("  Pass 1: Extraction...")
    model = extract_proposal_model(pages, page_count)

    if verbose:
        print(model.summary())
        print(f"\n  Part B starts at page {model.part_b_start_page}")

    result = AnalysisResult()

    call_text = None
    if call_path:
        call_text = load_call_text(call_path)
        if verbose:
            print(f"  Call text: {len(call_text)} chars loaded")

    if verbose:
        print("\n  Pass 2: Analysis...")

    # Layer 1: Structural Integrity
    if verbose:
        print("  Layer 1: Structural Integrity...")
    check_structural_integrity(model, result)

    # Layer 2: Call Alignment
    if verbose:
        print("  Layer 2: Call Alignment...")
    check_call_alignment(model, result, call_text)

    # Layer 3: Field & SMILE
    if verbose:
        print("  Layer 3: Field & SMILE...")
    check_field_awareness(model, result)
    smile_scores = check_smile_alignment(model, result)

    # Layer 4: Anti-Patterns
    start = model.part_b_start_page
    detectors = [
        ("Placeholders", lambda: check_unfilled_placeholders(pages, result, start)),
        ("Buzzwords", lambda: check_buzzwords(pages, result, start)),
        ("Opening", lambda: check_opening(pages, result, start)),
        ("Baselines", lambda: check_baselines(pages, result, start)),
        ("Partners", lambda: check_ghost_partners(pages, result, start)),
        ("Copy-paste SSH", lambda: check_copy_paste_ssh(pages, result, start)),
        ("Risks", lambda: check_risks(pages, result, start, model)),
        ("Timeline", lambda: check_timeline(pages, result, start)),
        ("Exploitation", lambda: check_exploitation(pages, result, start)),
        ("Market", lambda: check_market(pages, result, start)),
        ("Meeting milestones", lambda: check_meeting_milestones(pages, result, start)),
        ("Output/Outcome", lambda: check_output_outcome_impact(pages, result, start)),
        ("D&E conflation", lambda: check_dissemination_exploitation_conflation(pages, result, start)),
        ("Governance", lambda: check_governance(pages, result, start)),
        ("SotA", lambda: check_sota(pages, result, start)),
        ("Partner-driven WPs", lambda: check_partner_driven_wps(model, result)),
        ("AI disclosure", lambda: check_ai_disclosure(model, result)),
        ("Lump-sum", lambda: check_lump_sum(pages, result, start)),
        ("Acronyms", lambda: check_acronyms(model, result)),
        ("Budget narrative", lambda: check_budget_narrative(pages, result, start)),
        ("Consortium diversity", lambda: check_consortium_diversity(model, result)),
    ]

    if verbose:
        print("  Layer 4: Anti-Patterns...")
    for name, fn in detectors:
        try:
            fn()
            if verbose:
                print(f"    + {name}")
        except Exception as e:
            if verbose:
                print(f"    x {name}: {e}")

    # Budget mode: additional budget-focused checks
    if budget_mode:
        if verbose:
            print("  Budget mode: additional checks...")
        run_budget_analysis(model, result)

    # Pass 0: Pre-flight checklist
    pf_results = run_pre_flight(model, call_text)
    if verbose:
        print("  Pass 0: Pre-flight checklist complete")

    # EIC Pathfinder mode: call-specific scoring + strategic dimensions + future radar
    eic_scores = None
    strategic_scores = None
    future_scores = None
    if eic_pathfinder:
        if verbose:
            print("  Pass 3: EIC Pathfinder scoring...")
        eic_scores = score_eic_pathfinder(model, result)
        strategic_scores = score_strategic_dimensions(model)
        if verbose:
            print("  Pass 4: Future Tech Radar (3yr/5yr/10yr)...")
        future_scores = score_future_tech_radar(model)

    return result, model, smile_scores, pf_results, eic_scores, strategic_scores, future_scores


def main():
    parser = argparse.ArgumentParser(
        description="C.R.U.C.I.B.L.E. v4.0.0 — Full Horizon Europe proposal analyzer",
        epilog="Two-pass: Extract → Analyze. Built on SMILE methodology. Impact first, data last.",
    )
    parser.add_argument("pdf", help="Path to proposal PDF")
    parser.add_argument("--call", "-c", metavar="PATH",
                        help="Call/topic text file or PDF (enables Layer 2)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show extraction and analysis progress")
    parser.add_argument("--json", "-j", metavar="PATH",
                        help="Save full JSON output to file")
    parser.add_argument("--output", "-o", metavar="PATH",
                        help="Save text report to file")
    parser.add_argument("--budget", "-b", action="store_true",
                        help="Enable budget analysis mode (additional cost checks)")
    parser.add_argument("--model", "-m", action="store_true",
                        help="Print the extracted ProposalModel and exit (debug)")
    parser.add_argument("--eic-pathfinder", "-e", action="store_true",
                        help="EIC Pathfinder Open mode: call-specific scoring + strategic dimensions")

    args = parser.parse_args()

    if not Path(args.pdf).exists():
        print(f"ERROR: File not found: {args.pdf}")
        sys.exit(1)

    print(f"\n  C.R.U.C.I.B.L.E. v{__version__}")
    print(f"  Analyzing: {args.pdf}")
    if args.call:
        print(f"  Call text: {args.call}")
    if args.budget:
        print("  Budget mode: enabled")
    if args.eic_pathfinder:
        print("  EIC Pathfinder Open mode: enabled")

    result, model, smile_scores, pf_results, eic_scores, strategic_scores, future_scores = run_analysis(
        args.pdf, args.call, args.verbose, args.budget, args.eic_pathfinder
    )

    if args.model:
        print("\n" + model.summary())
        sys.exit(0)

    report = format_report(result, args.pdf, model, smile_scores,
                           bool(args.call), args.budget,
                           args.eic_pathfinder, pf_results,
                           eic_scores, strategic_scores, future_scores)
    print(report)

    if args.output:
        Path(args.output).write_text(report, encoding='utf-8')
        print(f"\n  Report saved: {args.output}")

    if args.json:
        scores = estimate_scores(result, model)
        data = {
            "tool": "CRUCIBLE",
            "version": __version__,
            "file": str(args.pdf),
            "call_provided": bool(args.call),
            "budget_mode": args.budget,
            "pages": model.total_pages,
            "model": {
                "acronym": model.acronym,
                "title": model.title,
                "duration_months": model.duration_months,
                "call_id": model.call_id,
                "action_type": model.action_type,
                "partner_count": len(model.partners),
                "partners": [
                    {"name": p.name, "pic": p.pic, "country": p.country,
                     "is_sme": p.is_sme, "person_months": p.person_months}
                    for p in model.partners
                ],
                "wp_count": len(model.work_packages),
                "work_packages": [
                    {"number": wp.number, "title": wp.title, "lead": wp.lead,
                     "start_month": wp.start_month, "end_month": wp.end_month}
                    for wp in model.work_packages
                ],
                "deliverable_count": len(model.deliverables),
                "milestone_count": len(model.milestones),
                "citation_count": len(model.citations_found),
                "kpi_count": len(model.kpis_found),
                "budget_total": model.budget_total,
                "budget_eu": model.budget_eu,
            },
            "scores": scores,
            "total": sum(scores.values()),
            "smile_coverage": smile_scores,
            "eic_pathfinder_scores": eic_scores,
            "strategic_dimensions": strategic_scores,
            "pre_flight": [
                {"id": q["id"], "question": q["question"],
                 "weight": q["weight"], "result": r}
                for q, r in (pf_results or [])
            ],
            "findings": [
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
            ],
        }
        Path(args.json).write_text(json.dumps(data, indent=2), encoding='utf-8')
        print(f"  JSON saved: {args.json}")


if __name__ == "__main__":
    main()
