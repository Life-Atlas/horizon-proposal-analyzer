"""
CRUCIBLE Module: Whitepaper (SMILE Canonical Diagram)

Scores whitepapers / thought-leadership documents against the canonical
SMILE "Zoom out to Zoom in" diagram (Nicolas Waern, WINNIIO) instead of
EU-proposal machinery.

Yardstick: SMILE-Canonical-Diagram-Extraction.md (Jul 9, 2026):
  - DT Journey: 6 stages with cycles boxes + use-case + alignment bullets
  - 3 perspectives: People / Planet / Systems
  - Spin Twin Lifecycle: Virtual MVT → Prototype Launch →
    Interoperable Operation → Phoenix Strategies (perpetual loop)
  - AI Journey: Human Decision Making → ... → Explainable AI Decision Making
  - Digital Mesh altitude stack: component → asset → factory →
    organization → operating context → global supply chain
  - Ontology factories → AI factories spine, knowledge-graph foundation
  - Top value chain: Outcome → Action → Insight → Information → Data
  - "Understandable by all", Record Everything, perpetual loop closure

A whitepaper is NOT a proposal: no consortium, no work packages, no LOI,
no budget tables, no call text. Those checks are suppressed here.

MIT License — WINNIIO AB / Life Atlas
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from modules import CallModule

if TYPE_CHECKING:
    from crucible import AnalysisResult, ProposalAnchor, ProposalModel


# ------------------------------------------------------------
# Proposal-only findings that must not penalize a whitepaper.
# These are produced by universal core checks; the module filters
# them out of the result before scoring/reporting.
# ------------------------------------------------------------

SUPPRESSED_PATTERNS = {
    # Consortium / partners
    "Consortium Too Small", "Country Diversity Insufficient",
    "Partners Not Detected", "Ghost Partner", "Low Country Diversity",
    "Low Industry Ratio for IA", "Partner-Driven WP Structure",
    # Work packages / deliverables / milestones / tasks
    "WP Exceeds Duration", "WP Invalid Dates", "Zero-PM Task Lead",
    "Orphaned Deliverable References", "Outcomes Without Deliverables",
    "Time-Travel Deliverable", "Meeting Milestone", "Meeting Milestones",
    "Heavy Management WP", "Under-Resourced Management",
    # Budget / PM / cost structure
    "Budget Not Parseable", "Budget Table Without Narrative",
    "Scope-Budget Mismatch", "EU Rate Exceeds 100%",
    "Low EU Contribution Rate", "Indirect Cost Rate Unexpected",
    "Low Personnel Cost Share", "Suspiciously High Personnel Cost",
    "Suspiciously Low Personnel Cost", "Very High Personnel Share",
    "Hours Arithmetic Mismatch", "High Equipment Ratio",
    "High Subcontracting Ratio", "Lump-Sum WP Budget Missing",
    # Call-text / action-type gatekeepers
    "Call Outcome Gap", "Call Terminology Gap", "No Call Text Provided",
    "Work Programme Parrot", "Policy Alignment Gap", "Vague Policy Reference",
    "TRL Mismatch", "Action Type Mismatch",
    "IA + Low TRL Mismatch", "RIA + High TRL Mismatch",
    "Page Limit Risk",
    # Proposal-template machinery
    "LOI", "No LOI Detected", "Ethics Self-Assessment Not Detected",
    "Empty Table Detected", "Unfinished Template",
    "Copy-Paste SSH Section", "D&E Conflation", "Exploitation Fog",
    "Governance Template", "All-Medium Risk Table", "Technical-Only Risks",
    "Unaddressed Conflict-Zone Risk",
    "Gender Imbalance", "Missing Gender Dimension", "Shallow Gender Treatment",
    "Employee Count Inconsistency", "Revenue Figure Inconsistency",
}


# ------------------------------------------------------------
# DT Journey — 6 stages. Markers derived from the canonical diagram:
# cycles-box terms + use-case bullets + alignment-row bullets + synonyms.
# All markers are lowercase substrings matched against full text.
# ------------------------------------------------------------

DT_JOURNEY_STAGES = {
    "reality_emulation": {
        "name": "Reality Emulation",
        "cycle": "Creating a 3D shared reality",
        "markers": [
            "reality emulation", "shared reality", "3d", "reality canvas",
            "job-that-is-done", "jobs to be done", "job to be done",
            "virtual first", "virtual-first", "record everything",
            "point cloud", "photogrammetry", "gaussian splat", "laser scan",
            "reality capture", "stakeholder mapping", "pesteled", "pestle",
            "5 why", "five why", "pace layering", "invite to demonstrate",
            "start anywhere", "where and when", "who needs to be involved",
        ],
    },
    "concurrent_engineering": {
        "name": "Concurrent Engineering",
        "cycle": "Invite to Innovate",
        "markers": [
            "concurrent engineering", "invite to innovate", "as-is", "to-be",
            "virtual user", "validate hypothes", "collective truth",
            "minimal viable twin", "mvt", "define scope",
            "industry standard", "iso ", "iso-", "kpi", "success factor",
            "organizational landscape", "vr", "ar", "xr",
            "industry regulation", "existing data",
        ],
    },
    "collective_intelligence": {
        "name": "Collective Intelligence",
        "cycle": "Emulation based Scenarios",
        "markers": [
            "collective intelligence", "scenario planning", "scenario",
            "table-top", "tabletop", "what-if", "open source", "open-source",
            "real-time data", "eliminate constraint", "constraint",
            "crm", "erp", "scorecard", "data strategy", "security strategy",
            "risk and optimization", "validate qualitat", "validate quantitat",
            "operational mvt",
        ],
    },
    "contextual_intelligence": {
        "name": "Contextual Intelligence",
        "cycle": "100% Virtual first completion",
        "markers": [
            "contextual intelligence", "physical sensor", "sensor",
            "initial kpi", "operational metric", "business value",
            "ontology creation", "ontology", "remote enablement", "remote",
            "attack surface", "lifecycle consolidation",
            "bim", "cim", "citygml", "ifc", "data fabric",
            "facility management", "fm alignment", "5m",
        ],
    },
    "continuous_intelligence": {
        "name": "Continuous Intelligence",
        "cycle": "4D Digital Twin Creation",
        "markers": [
            "continuous intelligence", "4d", "connected everything",
            "command & control", "command and control", "real-time decision",
            "up-time", "uptime", "predictive analytic", "predictive",
            "root cause", "ontology factory", "historic data",
            "humanized hmi", "hmi", "ml-data", "machine learning",
            "industry 4.0", "industry 5.0", "gamification",
        ],
    },
    "perpetual_wisdom": {
        "name": "Perpetual Wisdom",
        "cycle": "DT Fine tuning + XD Knowledge Transformation",
        "markers": [
            "perpetual wisdom", "prescriptive maintenance", "prescriptive",
            "prognostic", "event pipeline", "black swan", "simulate everything",
            "up cycle", "upcycle", "ecosystem enablement",
            "circular", "scm optimization", "supply chain optimization",
            "open-source contribution", "ai factory", "ai factories",
            "distributed intelligence", "virtual sensor", "metaverse",
            "meta-verse", "ip consolidation", "lifecycle analysis",
            "looping strateg", "decomposable", "re-use knowledge",
            "reuse knowledge", "optimize dt journey",
        ],
    },
}


# ------------------------------------------------------------
# Diagram element groups beyond the DT Journey stages.
# ------------------------------------------------------------

DIAGRAM_ELEMENTS = {
    "perspective_people": {
        "name": "Perspective: People",
        "markers": [
            "people", "stakeholder", "organization agnostic",
            "tacit knowledge", "key person", "key-person", "skills",
            "workforce", "human-in-the-loop", "human in control",
            "shared understanding", "training",
        ],
    },
    "perspective_planet": {
        "name": "Perspective: Planet",
        "markers": [
            "planet", "gis", "bim", "satellite", "reality canvas",
            "energy", "sustainab", "circular", "esg", "cbam",
            "environment", "resilien",
        ],
    },
    "perspective_systems": {
        "name": "Perspective: Systems",
        "markers": [
            "system", "operating context", "standard", "ontology alignment",
            "metadata", "interoperab", "planetary scope",
        ],
    },
    "spin_twin_lifecycle": {
        "name": "Spin Twin Lifecycle",
        "markers": [
            "spin twin", "minimal viable twin", "mvt", "virtual mvt",
            "prototype launch", "prototype", "interoperable operation",
            "future foundation", "phoenix strateg", "phoenix",
            "days/weeks", "weeks/months", "years/decades",
        ],
    },
    "ai_journey": {
        "name": "AI Journey ladder",
        "markers": [
            "human decision", "data contextualization", "contextualiz",
            "ai-ready", "ai ready", "ai-infused", "ai infused",
            "ai-ingrained", "ai ingrained", "explainable ai",
        ],
    },
    "digital_mesh": {
        "name": "Digital Mesh / altitude stack",
        "markers": [
            "digital mesh", "component", "asset", "factory", "machine",
            "organization", "operating context", "supply chain",
            "supply-chain", "zoom out", "zoom in", "altitude",
        ],
    },
    "ontology_ai_factories": {
        "name": "Ontology factories → AI factories",
        "markers": [
            "ontology factor", "ai factor", "foundation for ai",
            "explainable ai factor",
        ],
    },
    "knowledge_graph": {
        "name": "Knowledge Graph foundation",
        "markers": [
            "knowledge graph", "ontology", "graph", "relationship",
            "fragmented realit", "semantic",
        ],
    },
    "value_chain": {
        "name": "Value chain (Outcome→Action→Insight→Information→Data)",
        "markers": [
            "outcome", "action", "insight", "information", "data",
            "knowledge transfer", "operating model", "business transformation",
        ],
    },
    "understandable_by_all": {
        "name": "Understandable by all",
        "markers": [
            "understandable by all", "understood by all", "board to floor",
            "boardroom", "shop floor", "common language",
            "shared understanding", "accessible to everyone",
            "understandable", "no code", "no-code",
        ],
    },
    "record_everything": {
        "name": "Record Everything",
        "markers": [
            "record everything", "capture everything", "continuous capture",
            "capture knowledge", "recorded", "digital knowledge capture",
        ],
    },
    "perpetual_loop": {
        "name": "Perpetual loop closure (Phoenix → Reality Emulation)",
        "markers": [
            "loop back", "loops back", "looping back", "feeds back",
            "feed back into", "back into", "perpetual", "phoenix",
            "closed loop", "closed-loop", "virtuous cycle", "cycle anew",
            "begins again", "starts again", "re-enter", "re-emulat",
            "transcend the now", "never ends", "never-ending", "flywheel",
        ],
    },
}

# Elements important enough to raise a finding when MISSING
KEY_ELEMENTS = [
    "ontology_ai_factories", "knowledge_graph",
    "ai_journey", "perpetual_loop",
]

# Whitepaper composite blend (all sub-scores on /5 scale)
BLEND_WEIGHTS = {
    "smile_diagram": 0.40,
    "strategic": 0.15,
    "future_radar": 0.15,
    "pesteled": 0.10,
    "interop": 0.10,
    "stress": 0.10,
}

WHITEPAPER_SIGNALS = [
    "whitepaper", "white paper", "white-paper", "thesis", "manifesto",
    "position paper", "point of view", "thought leadership",
]

SMILE_SIGNALS = [
    "smile", "zoom out to zoom in", "reality emulation", "spin twin",
    "digital mesh", "ontology factor", "perpetual wisdom",
    "reality canvas", "minimal viable twin",
]


def _doc_scale(total_pages: int) -> str:
    """Mirror ProposalAnchor.doc_scale classification for scoring."""
    if total_pages <= 5:
        return "micro"
    elif total_pages <= 15:
        return "compact"
    elif total_pages <= 30:
        return "standard"
    return "extended"


def _coverage_status(found: int, total: int) -> str:
    if total == 0 or found == 0:
        return "MISSING"
    if found / total >= 0.35 and found >= 2:
        return "COVERED"
    return "PARTIAL"


@dataclass
class WhitepaperModule(CallModule):
    name: str = "whitepaper"
    version: str = "1.0.0"
    description: str = "Whitepaper — scored against the canonical SMILE diagram"
    funding_body: str = ""
    languages: list = field(default_factory=lambda: ["en", "sv"])
    countries: list = field(default_factory=list)

    def matches(self, anchor: "ProposalAnchor") -> float:
        """Whitepaper-ish signal: no funding body / call detected.

        The anchor carries no raw text, so auto-detection is conservative:
        a document with no funder, no program, and non-trivial length is
        treated as a probable whitepaper. Explicit path: --module whitepaper.
        """
        if anchor.funding_body or anchor.funding_program:
            return 0.0
        score = 0.0
        if anchor.page_count >= 5:
            score += 0.35
        if anchor.language in self.languages:
            score += 0.05
        return min(score, 1.0)

    def get_lexicon(self) -> dict[str, list[str]]:
        return {
            "digital twin": ["digital tvilling"],
            "reality emulation": [],
            "spin twin lifecycle": [],
            "minimal viable twin": ["MVT"],
            "ontology factory": [],
            "ai factory": [],
            "knowledge graph": ["kunskapsgraf"],
            "explainable ai": ["förklarbar AI"],
            "digital mesh": [],
            "perpetual wisdom": [],
            "zoom out to zoom in": [],
        }

    def get_structural_checks(self) -> list[tuple[str, callable]]:
        return [
            ("WP: Perpetual loop closure", self._check_perpetual_loop),
            ("WP: Key diagram elements", self._check_key_elements),
        ]

    def get_detectors(self) -> list[tuple[str, callable]]:
        return []

    # --- Scoring ---

    def score(self, model: "ProposalModel", result: "AnalysisResult") -> Optional[dict]:
        """Score against the canonical SMILE diagram + whitepaper blend.

        Also filters proposal-only findings out of the result so a
        whitepaper is never penalized for lacking consortium/budget/WP
        machinery. Runs before report generation and estimate_scores,
        so both scoring and the report see the cleaned finding set.
        """
        self._suppress_proposal_findings(result)

        # Lazy import to avoid circular import at module load
        import crucible

        text = model.full_text.lower() if model.full_text else ""
        ds = _doc_scale(model.total_pages)

        # Per-stage DT Journey coverage
        stages = {}
        for key, stage in DT_JOURNEY_STAGES.items():
            found = sum(1 for m in stage["markers"] if m in text)
            total = len(stage["markers"])
            stages[key] = {
                "name": stage["name"],
                "cycle": stage["cycle"],
                "found": found,
                "total": total,
                "score": crucible._score_markers(found, total, ds),
                "status": _coverage_status(found, total),
            }

        # Diagram element coverage
        elements = {}
        for key, elem in DIAGRAM_ELEMENTS.items():
            found = sum(1 for m in elem["markers"] if m in text)
            total = len(elem["markers"])
            elements[key] = {
                "name": elem["name"],
                "found": found,
                "total": total,
                "score": crucible._score_markers(found, total, ds),
                "status": _coverage_status(found, total),
            }

        stage_avg = round(sum(s["score"] for s in stages.values()) / len(stages), 2)
        elem_avg = round(sum(e["score"] for e in elements.values()) / len(elements), 2)
        smile_diagram = round(stage_avg * 0.5 + elem_avg * 0.5, 2)

        # Audience-relevant core dimensions (all /5)
        strategic = crucible.score_strategic_dimensions(model, ds)["_weighted_avg"]
        future = crucible.score_future_tech_radar(model, ds)["_weighted_avg"]
        pesteled = crucible.score_pesteled(model, ds)["_weighted_avg"]
        interop = crucible.score_eu_interop(model, ds)["_weighted_avg"]
        stress = crucible.score_stress_test(model)["_overall"]

        components = {
            "smile_diagram": smile_diagram,
            "strategic": strategic,
            "future_radar": future,
            "pesteled": pesteled,
            "interop": interop,
            "stress": stress,
        }
        composite = round(
            sum(components[k] * w for k, w in BLEND_WEIGHTS.items()), 1
        )

        return {
            **components,
            "composite": composite,
            "stages": stages,
            "elements": elements,
        }

    def format_scores(self, scores: dict) -> list[str]:
        if not scores:
            return []
        lines = [
            "",
            "  ╔══════════════════════════════════════════════════════╗",
            "  ║  WHITEPAPER — SMILE Canonical Diagram Scoring        ║",
            "  ╠══════════════════════════════════════════════════════╣",
            f"  ║  SMILE diagram alignment (40%):  {scores.get('smile_diagram', 0):.2f} / 5.00        ║",
            f"  ║  Strategic dimensions    (15%):  {scores.get('strategic', 0):.2f} / 5.00        ║",
            f"  ║  Future tech radar       (15%):  {scores.get('future_radar', 0):.2f} / 5.00        ║",
            f"  ║  PESTELED                (10%):  {scores.get('pesteled', 0):.2f} / 5.00        ║",
            f"  ║  Interop / standards     (10%):  {scores.get('interop', 0):.2f} / 5.00        ║",
            f"  ║  Stress / quality        (10%):  {scores.get('stress', 0):.2f} / 5.00        ║",
            f"  ║  COMPOSITE:                      {scores.get('composite', 0):.1f} / 5.0          ║",
            "  ╚══════════════════════════════════════════════════════╝",
            "",
            "  DT JOURNEY — per-stage diagram coverage",
            "  " + "-" * 72,
        ]
        for stage in scores.get("stages", {}).values():
            filled = int((stage["score"] - 1.0) / 4.0 * 16)
            bar = "#" * filled + "." * (16 - filled)
            lines.append(
                f"  {stage['name']:<26} {stage['score']}/5.0  [{bar}]  "
                f"({stage['found']}/{stage['total']} markers, {stage['status']})"
            )
        lines.append("")
        lines.append("  DIAGRAM ELEMENT COVERAGE")
        lines.append("  " + "-" * 72)
        for elem in scores.get("elements", {}).values():
            lines.append(
                f"  [{elem['status']:<7}] {elem['name']} "
                f"({elem['found']}/{elem['total']} markers)"
            )
        lines.append("")
        return lines

    # --- Finding suppression ---

    @staticmethod
    def _suppress_proposal_findings(result: "AnalysisResult"):
        """Remove proposal-only findings (consortium, budget, WPs, call text)."""
        result.findings[:] = [
            f for f in result.findings
            if f.pattern not in SUPPRESSED_PATTERNS
        ]

    # --- Structural checks ---

    @staticmethod
    def _check_perpetual_loop(model: "ProposalModel", result: "AnalysisResult"):
        text = model.full_text.lower()
        markers = DIAGRAM_ELEMENTS["perpetual_loop"]["markers"]
        found = sum(1 for m in markers if m in text)
        if found == 0:
            result.add(
                "Perpetual Loop Not Closed", "HIGH", 0,
                "No loop-back language detected. The canonical diagram is a "
                "perpetual cycle: Phoenix Strategies / Perpetual Wisdom must "
                "explicitly feed back into Virtual MVT / Reality Emulation.",
                "Add explicit loop-closure language: Phoenix Strategies loop "
                "back into Reality Emulation — the journey never terminates.",
                "SMILE Diagram", 1,
            )

    @staticmethod
    def _check_key_elements(model: "ProposalModel", result: "AnalysisResult"):
        text = model.full_text.lower()
        for key in KEY_ELEMENTS:
            elem = DIAGRAM_ELEMENTS[key]
            found = sum(1 for m in elem["markers"] if m in text)
            if found == 0:
                result.add(
                    f"Diagram Element Missing: {elem['name']}", "MEDIUM", 0,
                    f"No markers found for canonical diagram element "
                    f"'{elem['name']}'.",
                    "Whitepapers should touch every spine element of the "
                    "canonical SMILE diagram.",
                    "SMILE Diagram", 1,
                )
