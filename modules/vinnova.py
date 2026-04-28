"""
CRUCIBLE Module: Vinnova (Swedish Innovation Agency)

Call-specific logic for Swedish national funding:
- Impact Innovation (Resilient Metals, etc.)
- Strategic Innovation Programs (SIP)
- Challenge-Driven Innovation
- Eurostar / CELTIC-NEXT via Vinnova

Learned from: DTMETAL proposal (Apr 2026) for Impact Innovation:
Resilient Metall- och Mineralförsörjning, 40 MSEK pot.

Four evaluation criteria (each scored 1-7):
  1. Relevans — alignment with call challenge + urgency
  2. Potential — innovation height + scalability + societal benefit
  3. Aktörer — consortium strength + complementarity + commitment
  4. Genomförbarhet — feasibility of plan, budget, timeline, risks

MIT License — WINNIIO AB / Life Atlas
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from modules import CallModule

if TYPE_CHECKING:
    from crucible import AnalysisResult, ProposalAnchor, ProposalModel


# Vinnova Impact Innovation category constraints
VINNOVA_CATEGORIES = {
    1: {"label": "Konceptstudie", "max_months": 14, "max_budget_sek": 2_000_000,
        "min_cofinancing": 0.0},
    2: {"label": "Genomförbarhetsstudie", "max_months": 24, "max_budget_sek": 5_000_000,
        "min_cofinancing": 0.50},
    3: {"label": "Pilot & demonstration", "max_months": 36, "max_budget_sek": 10_000_000,
        "min_cofinancing": 0.50},
}


@dataclass
class VinnovaModule(CallModule):
    name: str = "vinnova"
    version: str = "1.0.0"
    description: str = "Vinnova — Swedish Innovation Agency (Impact Innovation, SIP, etc.)"
    funding_body: str = "Vinnova"
    languages: list = field(default_factory=lambda: ["sv", "en"])
    countries: list = field(default_factory=lambda: ["SE"])

    def matches(self, anchor: "ProposalAnchor") -> float:
        score = 0.0

        fb = (anchor.funding_body or "").lower()
        fp = (anchor.funding_program or "").lower()
        combined = fb + " " + fp

        if "vinnova" in combined:
            score += 0.6
        if any(k in combined for k in [
            "impact innovation", "strategiskt innovationsprogram",
            "utmaningsdriven", "celtic", "eurostar",
        ]):
            score += 0.3
        if anchor.language == "sv":
            score += 0.1
        if anchor.country and anchor.country.upper() == "SE":
            score += 0.1

        return min(score, 1.0)

    def get_lexicon(self) -> dict[str, list[str]]:
        return {
            "impact innovation": ["effektdriven innovation"],
            "concept study": ["konceptstudie"],
            "feasibility study": ["genomförbarhetsstudie"],
            "pilot": ["pilot", "demonstration"],
            "co-financing": ["medfinansiering", "egenfinansiering"],
            "letter of intent": ["avsiktsförklaring", "LOI"],
            "project description": ["projektbeskrivning"],
            "summary": ["sammanfattning"],
            "non-confidential summary": ["icke-konfidentiell sammanfattning"],
            "total defence": ["totalförsvar", "total-digitalförsvaret"],
            "heightened alert": ["höjd beredskap", "skärpt beredskap"],
            "key person risk": ["nyckelpersonberoende", "nyckelpersonrisk"],
            "tacit knowledge": ["tyst kunskap", "erfarenhetsbaserad kunskap"],
            "knowledge externalization": ["kunskapsexternalisering"],
            "capacity model": ["kapacitetsmodell"],
            "transferability": ["överförbarhet"],
            "societal benefit": ["samhällsnytta"],
            "defence industry": ["försvarsindustri"],
            "sme": ["SME", "små och medelstora företag"],
            "resilience": ["resiliens", "motståndskraft"],
            "supply chain": ["leveranskedja", "försörjningskedja"],
        }

    def get_preflight_questions(self) -> list[dict]:
        return [
            {
                "id": "VIN-PF1",
                "question": "Does the proposal include Projektbeskrivning, Sammanfattning, and Icke-konfidentiell sammanfattning?",
                "weight": 3,
            },
            {
                "id": "VIN-PF2",
                "question": "Is a signed Letter of Intent (LOI/Avsiktsförklaring) attached?",
                "weight": 3,
            },
            {
                "id": "VIN-PF3",
                "question": "Is the project category (Kat 1/2/3) explicitly stated?",
                "weight": 2,
            },
            {
                "id": "VIN-PF4",
                "question": "Does the budget respect Vinnova category caps and co-financing requirements?",
                "weight": 3,
            },
            {
                "id": "VIN-PF5",
                "question": "Is each organization's role, commitment level, and named personnel specified?",
                "weight": 2,
            },
            {
                "id": "VIN-PF6",
                "question": "Are all company figures (revenue, employees) consistent across all documents?",
                "weight": 2,
            },
        ]

    def get_structural_checks(self) -> list[tuple[str, callable]]:
        return [
            ("VIN: Category-budget alignment", self._check_category_budget),
            ("VIN: Co-financing requirement", self._check_cofinancing),
            ("VIN: Duration vs category cap", self._check_duration_cap),
            ("VIN: LOI presence", self._check_loi),
            ("VIN: Named personnel in Projektgruppen", self._check_named_personnel),
            ("VIN: Gender balance in team", self._check_gender_balance),
            ("VIN: AP hours arithmetic", self._check_ap_hours),
            ("VIN: Cross-document consistency", self._check_cross_doc_consistency),
            ("VIN: Risk register completeness", self._check_risks),
            ("VIN: Transferability/replication", self._check_transferability),
        ]

    def get_detectors(self) -> list[tuple[str, callable]]:
        return [
            ("VIN: Vague MSB/FOI references", self._detect_vague_authority_refs),
            ("VIN: Missing scenario analysis", self._detect_missing_scenarios),
            ("VIN: Key person dependency undisclosed", self._detect_key_person_risk),
            ("VIN: Empty Projektgruppen table", self._detect_empty_team_table),
            ("VIN: Category-scope mismatch", self._detect_scope_mismatch),
        ]

    def score(self, model: "ProposalModel", result: "AnalysisResult") -> Optional[dict]:
        """Score against Vinnova's 4 evaluation criteria (1-7 scale)."""
        findings = result.findings
        text_lower = model.full_text.lower()

        crit = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")
        med = sum(1 for f in findings if f.severity == "MEDIUM")

        # Relevans: call alignment + urgency framing
        relevans = 5.0
        relevance_markers = ["resilien", "försörjningskedja", "supply chain",
                             "totalförsvar", "beredskap", "critical mineral",
                             "kritisk mineral", "strategisk"]
        relevans += sum(0.3 for m in relevance_markers if m in text_lower)
        relevans -= crit * 0.5
        relevans = max(1, min(7, relevans))

        # Potential: innovation height + scalability
        potential = 4.5
        potential_markers = ["digital twin", "digital tvilling", "kunskapsexternalisering",
                            "overf.rbarhet", "skalbar", "scalab", "novel",
                            "nytt tillvägagångssätt", "branschöverskridande"]
        potential += sum(0.3 for m in potential_markers if re.search(m, text_lower))
        potential -= high * 0.3
        potential = max(1, min(7, potential))

        # Aktörer: consortium strength
        aktorer = 4.5
        if len(model.partners) >= 3:
            aktorer += 0.5
        if any("rise" in (p.name or "").lower() for p in model.partners):
            aktorer += 0.5
        if any(p.is_sme for p in model.partners):
            aktorer += 0.3
        named_people = len(model.researchers)
        if named_people >= 3:
            aktorer += 0.5
        aktorer -= crit * 0.3
        aktorer = max(1, min(7, aktorer))

        # Genomförbarhet: feasibility
        genomforbarhet = 5.0
        if model.work_packages:
            genomforbarhet += 0.3
        if model.milestones:
            genomforbarhet += 0.3
        if model.risks:
            genomforbarhet += 0.3
        genomforbarhet -= crit * 0.8
        genomforbarhet -= high * 0.3
        genomforbarhet = max(1, min(7, genomforbarhet))

        return {
            "relevans": round(relevans, 1),
            "potential": round(potential, 1),
            "aktörer": round(aktorer, 1),
            "genomförbarhet": round(genomforbarhet, 1),
            "composite": round((relevans + potential + aktorer + genomforbarhet) / 4, 1),
        }

    def format_scores(self, scores: dict) -> list[str]:
        if not scores:
            return []
        return [
            "",
            "  ╔══════════════════════════════════════════════╗",
            "  ║  VINNOVA — Estimated Evaluation Scores       ║",
            "  ╠══════════════════════════════════════════════╣",
            f"  ║  Relevans:        {scores.get('relevans', 0):.1f} / 7.0                ║",
            f"  ║  Potential:       {scores.get('potential', 0):.1f} / 7.0                ║",
            f"  ║  Aktörer:         {scores.get('aktörer', 0):.1f} / 7.0                ║",
            f"  ║  Genomförbarhet:  {scores.get('genomförbarhet', 0):.1f} / 7.0                ║",
            f"  ║  Composite:       {scores.get('composite', 0):.1f} / 7.0                ║",
            "  ╚══════════════════════════════════════════════╝",
        ]

    def get_extraction_hints(self) -> dict:
        return {
            "budget_patterns": [
                r'(?:Total|Totalt|Summa)[:\s]+([\d\s,\.]+)\s*(?:SEK|kr)',
                r'(?:Stödberättigande|Eligible)\s+kostnader?[:\s]+([\d\s,\.]+)',
                r'(?:Sökt\s+bidrag|Requested)[:\s]+([\d\s,\.]+)',
            ],
            "duration_patterns": [
                r'(?:Projektperiod|Duration)[:\s]+(\d{1,2})\s*(?:månader|months|mån)',
                r'(\d{4}-\d{2})\s*[-–]\s*(\d{4}-\d{2})',
            ],
            "partner_patterns": [
                r'(?:Organisationsnamn|Organization)[:\s]+([^\n]{5,80})',
                r'(?:Org\.?\s*nr|Org number)[:\s]+(\d{6}-\d{4})',
            ],
        }

    # --- Structural checks ---

    @staticmethod
    def _check_category_budget(model: "ProposalModel", result: "AnalysisResult"):
        text_lower = model.full_text.lower()
        detected_cat = None

        for cat_num, props in VINNOVA_CATEGORIES.items():
            if props["label"].lower() in text_lower:
                detected_cat = cat_num
                break

        if not detected_cat:
            for cat_num in [1, 2, 3]:
                if f"kategori {cat_num}" in text_lower or f"kat {cat_num}" in text_lower:
                    detected_cat = cat_num
                    break

        if detected_cat and model.budget_total > 0:
            cap = VINNOVA_CATEGORIES[detected_cat]["max_budget_sek"]
            if model.budget_total > cap:
                result.add(
                    "Budget Exceeds Category Cap", "CRITICAL", 0,
                    f"Kategori {detected_cat} ({VINNOVA_CATEGORIES[detected_cat]['label']}) "
                    f"max is {cap:,.0f} SEK. Budget: {model.budget_total:,.0f}.",
                    f"Reduce budget to ≤{cap:,.0f} SEK or change category.",
                    "structural", 1,
                )

    @staticmethod
    def _check_cofinancing(model: "ProposalModel", result: "AnalysisResult"):
        text_lower = model.full_text.lower()
        cofin_match = re.search(
            r'(?:medfinansiering|co-?financing)[:\s]+(\d+)\s*%', text_lower
        )
        if cofin_match:
            pct = int(cofin_match.group(1))
            if pct < 50:
                result.add(
                    "Co-financing Below 50%", "HIGH", 0,
                    f"Co-financing at {pct}%. Kat 2/3 require ≥50% co-financing.",
                    "Verify category. Kat 1 has no co-financing requirement.",
                    "structural", 1,
                )

    @staticmethod
    def _check_duration_cap(model: "ProposalModel", result: "AnalysisResult"):
        text_lower = model.full_text.lower()
        detected_cat = None
        for cat_num in [1, 2, 3]:
            if f"kategori {cat_num}" in text_lower or f"kat {cat_num}" in text_lower:
                detected_cat = cat_num
                break

        if detected_cat and model.duration_months > 0:
            cap = VINNOVA_CATEGORIES[detected_cat]["max_months"]
            if model.duration_months > cap:
                result.add(
                    "Duration Exceeds Category Cap", "CRITICAL", 0,
                    f"Kategori {detected_cat} max is {cap} months. "
                    f"Duration: {model.duration_months} months.",
                    f"Reduce to ≤{cap} months or change category.",
                    "structural", 1,
                )

    @staticmethod
    def _check_loi(model: "ProposalModel", result: "AnalysisResult"):
        text_lower = model.full_text.lower()
        has_loi = any(k in text_lower for k in [
            "avsiktsförklaring", "letter of intent", "loi"
        ])
        if not has_loi:
            result.add(
                "No LOI Detected", "HIGH", 0,
                "No Letter of Intent / Avsiktsförklaring found in submission documents.",
                "Attach signed LOI from all consortium partners.",
                "structural", 1,
            )

    @staticmethod
    def _check_named_personnel(model: "ProposalModel", result: "AnalysisResult"):
        text_lower = model.full_text.lower()
        if "projektgrupp" in text_lower:
            name_pattern = re.findall(
                r'([A-ZÅÄÖ][a-zåäö]+\s+[A-ZÅÄÖ][a-zåäö]+)', model.full_text
            )
            if len(set(name_pattern)) < 3:
                result.add(
                    "Few Named Personnel", "MEDIUM", 0,
                    f"Only {len(set(name_pattern))} unique names detected. "
                    "Evaluators want to see named key personnel with roles.",
                    "Name at least the project leader, scientific lead, and domain expert.",
                    "structural", 1,
                )

    @staticmethod
    def _check_gender_balance(model: "ProposalModel", result: "AnalysisResult"):
        text_lower = model.full_text.lower()
        gender_markers_m = len(re.findall(r'\b[Mm]\b', model.full_text))
        gender_markers_k = len(re.findall(r'\b[Kk]\b', model.full_text))
        # Very rough heuristic — Swedish forms use M/K in team tables
        if "projektgrupp" in text_lower:
            k_count = len(re.findall(r'\|\s*K\s*\|', model.full_text))
            m_count = len(re.findall(r'\|\s*M\s*\|', model.full_text))
            total = k_count + m_count
            if total > 0 and k_count / total < 0.2:
                result.add(
                    "Low Gender Balance", "MEDIUM", 0,
                    f"Team table shows {k_count}K / {m_count}M. "
                    "Vinnova values gender-balanced teams.",
                    "Identify women participants or explain mitigation plan.",
                    "structural", 1,
                )

    @staticmethod
    def _check_ap_hours(model: "ProposalModel", result: "AnalysisResult"):
        # Look for AP (Arbetspaket) hour tables
        text = model.full_text
        hour_matches = re.findall(
            r'(?:AP\s*\d+|Arbetspaket\s*\d+)[^\n]*?(\d{2,4})\s*(?:timmar|h\b|tim)',
            text, re.IGNORECASE
        )
        if hour_matches:
            ap_total = sum(int(h) for h in hour_matches)
            if model.wp_hours_total > 0 and abs(ap_total - model.wp_hours_total) > 50:
                result.add(
                    "AP Hours Mismatch", "HIGH", 0,
                    f"AP section hours sum to {ap_total}h but total declared is "
                    f"{model.wp_hours_total:.0f}h.",
                    "Reconcile hour allocations across all APs.",
                    "structural", 1,
                )

    @staticmethod
    def _check_cross_doc_consistency(model: "ProposalModel", result: "AnalysisResult"):
        # This is a flag — actual cross-doc checking needs multi-file input
        # For single-PDF mode, check internal consistency
        if model.named_entities:
            for entity, facts in model.named_entities.items():
                revs = facts.get("revenues", [])
                emps = facts.get("employees", [])
                if len(set(revs)) > 1 or len(set(emps)) > 1:
                    # Already caught by U3, but Vinnova cares extra
                    pass

    @staticmethod
    def _check_risks(model: "ProposalModel", result: "AnalysisResult"):
        if not model.risks and "risk" in model.full_text.lower():
            result.add(
                "Risk Table Missing or Unparseable", "HIGH", 0,
                "Risks mentioned in text but no structured risk table detected.",
                "Include a risk register with probability, impact, and mitigation.",
                "structural", 1,
            )
        if model.risks:
            for risk in model.risks:
                if not risk.mitigation or len(risk.mitigation) < 10:
                    result.add(
                        "Risk Without Mitigation", "MEDIUM", 0,
                        f"Risk '{risk.description[:50]}' has no meaningful mitigation.",
                        "Every risk needs a specific, actionable mitigation strategy.",
                        "structural", 1,
                    )
                    break

    @staticmethod
    def _check_transferability(model: "ProposalModel", result: "AnalysisResult"):
        text_lower = model.full_text.lower()
        transfer_markers = [
            "överförbarhet", "replikerbar", "transferab", "replicat",
            "andra branscher", "andra sektorer", "other sectors",
            "generalisera", "generaliz",
        ]
        if not any(m in text_lower for m in transfer_markers):
            result.add(
                "No Transferability Claim", "MEDIUM", 0,
                "No mention of how results transfer to other sectors/domains.",
                "Vinnova values cross-sector applicability. "
                "Add a section on how the methodology applies beyond this domain.",
                "structural", 1,
            )

    # --- Anti-pattern detectors ---

    @staticmethod
    def _detect_vague_authority_refs(pages, result, start, model):
        text = model.full_text
        vague_refs = re.findall(
            r'\b(?:MSB|FOI|Tillväxtverket|SKR|Myndigheten)\s+'
            r'(?:rapport|rekommendation|riktlinje|analys)',
            text, re.IGNORECASE
        )
        for ref in vague_refs[:3]:
            context_start = text.lower().find(ref.lower())
            if context_start >= 0:
                window = text[max(0, context_start - 20):context_start + len(ref) + 100]
                if not re.search(r'\b\d{4}[:/]\d+|\bdnr\b|\bISO\b|\d{4}', window):
                    result.add(
                        "Vague Swedish Authority Reference", "MEDIUM", 0,
                        f"Reference '{ref[:60]}' lacks publication ID/year.",
                        "Add year, dnr, or document ID (e.g. 'MSB 2024, dnr 30143').",
                        "anti-pattern", 4,
                    )
                    break

    @staticmethod
    def _detect_missing_scenarios(pages, result, start, model):
        text_lower = model.full_text.lower()
        has_scenarios = any(k in text_lower for k in [
            "scenario", "what-if", "krisscenario", "beredskapsscenario",
        ])
        if "beredskap" in text_lower and not has_scenarios:
            result.add(
                "No Scenario Analysis", "MEDIUM", 0,
                "Proposal mentions preparedness/beredskap but includes no scenario analysis.",
                "Add 2-3 concrete scenarios (e.g. key person loss, supply disruption, "
                "cyber attack) with how the solution addresses each.",
                "anti-pattern", 4,
            )

    @staticmethod
    def _detect_key_person_risk(pages, result, start, model):
        text_lower = model.full_text.lower()
        has_tacit = any(k in text_lower for k in [
            "tyst kunskap", "tacit knowledge", "nyckelperson",
            "erfarenhetsbaserad",
        ])
        has_mitigation = any(k in text_lower for k in [
            "kunskapsexternalisering", "knowledge externalization",
            "knowledge capture", "kunskapsöverföring",
        ])
        if has_tacit and not has_mitigation:
            result.add(
                "Key Person Risk Without Mitigation Strategy", "HIGH", 0,
                "Tacit knowledge / key person dependency mentioned but no knowledge "
                "externalization strategy described.",
                "Describe how the project captures and externalizes tacit knowledge.",
                "anti-pattern", 4,
            )

    @staticmethod
    def _detect_empty_team_table(pages, result, start, model):
        if model.tables_empty > 0:
            pass  # Already caught by universal U1

    @staticmethod
    def _detect_scope_mismatch(pages, result, start, model):
        text_lower = model.full_text.lower()
        detected_cat = None
        for cat_num in [1, 2, 3]:
            if f"kategori {cat_num}" in text_lower or f"kat {cat_num}" in text_lower:
                detected_cat = cat_num
                break

        if detected_cat == 1:
            heavy_markers = [
                "pilot", "demonstration", "implementering", "driftsättning",
                "deployment", "full-scale",
            ]
            heavy_count = sum(1 for m in heavy_markers if m in text_lower)
            if heavy_count >= 3:
                result.add(
                    "Scope Too Ambitious for Kat 1", "HIGH", 0,
                    f"Kategori 1 (concept study) but {heavy_count} "
                    "implementation/pilot terms detected.",
                    "Kat 1 is for concept validation, not deployment. "
                    "Either reduce scope or apply for Kat 2/3.",
                    "anti-pattern", 4,
                )
