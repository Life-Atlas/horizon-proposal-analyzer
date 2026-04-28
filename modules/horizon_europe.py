"""
CRUCIBLE Module: Horizon Europe / EIC Pathfinder

Call-specific logic for EU Framework Programme proposals:
- Horizon Europe (RIA, IA, CSA)
- EIC Pathfinder Open
- EIC Accelerator
- MSCA, ERC

Detects from: HORIZON-* call IDs, EU funding body references,
multi-country consortia with PIC numbers.

MIT License — WINNIIO AB / Life Atlas
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from modules import CallModule

if TYPE_CHECKING:
    from crucible import AnalysisResult, ProposalAnchor, ProposalModel


@dataclass
class HorizonEuropeModule(CallModule):
    name: str = "horizon-europe"
    version: str = "1.0.0"
    description: str = "Horizon Europe / EIC Pathfinder / EU Framework Programme"
    funding_body: str = "European Commission"
    languages: list = field(default_factory=lambda: ["en"])
    countries: list = field(default_factory=lambda: ["EU"])

    def matches(self, anchor: "ProposalAnchor") -> float:
        score = 0.0

        if anchor.funding_body and "european" in anchor.funding_body.lower():
            score += 0.5
        if anchor.funding_program and "horizon" in anchor.funding_program.lower():
            score += 0.4

        fb = (anchor.funding_body or "").lower()
        fp = (anchor.funding_program or "").lower()
        combined = fb + " " + fp

        if any(k in combined for k in ["eic", "erc", "msca", "horizon europe"]):
            score += 0.3
        if anchor.language == "en":
            score += 0.05

        return min(score, 1.0)

    def get_lexicon(self) -> dict[str, list[str]]:
        return {
            "work package": [],
            "deliverable": [],
            "milestone": [],
            "consortium": [],
            "dissemination": [],
            "exploitation": [],
            "open science": [],
            "gender dimension": [],
            "responsible research": [],
            "technology readiness level": ["TRL"],
            "lump sum": [],
            "person month": ["PM"],
        }

    def get_preflight_questions(self) -> list[dict]:
        return [
            {
                "id": "HE-PF1",
                "question": "Does the proposal have a Part B with Excellence/Impact/Implementation structure?",
                "weight": 3,
            },
            {
                "id": "HE-PF2",
                "question": "Are all partners from ≥3 different EU/Associated countries?",
                "weight": 3,
            },
            {
                "id": "HE-PF3",
                "question": "Is the action type (RIA/IA/CSA) explicitly stated?",
                "weight": 2,
            },
            {
                "id": "HE-PF4",
                "question": "Does the budget use the EU template format with PIC numbers?",
                "weight": 2,
            },
        ]

    def get_structural_checks(self) -> list[tuple[str, callable]]:
        return [
            ("HE: Partner country diversity", self._check_partner_countries),
            ("HE: Page count vs action type", self._check_page_count),
            ("HE: Action type TRL consistency", self._check_action_trl),
            ("HE: Industry PM ratio for IA", self._check_industry_pm),
            ("HE: Management WP effort", self._check_management_wp),
            ("HE: Subcontracting ratio", self._check_subcontracting),
            ("HE: Equipment cost ratio", self._check_equipment),
        ]

    def get_detectors(self) -> list[tuple[str, callable]]:
        return [
            ("HE: SSH copy-paste", self._detect_ssh_copypaste),
            ("HE: Lump-sum issues", self._detect_lump_sum),
            ("HE: Exploitation plan", self._detect_exploitation),
            ("HE: D&E conflation", self._detect_de_conflation),
            ("HE: Consortium diversity", self._detect_consortium_diversity),
            ("HE: Theory of Change", self._detect_theory_of_change),
            ("HE: Gender dimension", self._detect_gender_dimension),
        ]

    def score(self, model: "ProposalModel", result: "AnalysisResult") -> Optional[dict]:
        scores = {}
        findings = result.findings

        crit = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")
        med = sum(1 for f in findings if f.severity == "MEDIUM")

        base = 10.0
        base -= crit * 1.5
        base -= high * 0.5
        base -= med * 0.15

        scores["excellence"] = max(0, min(5, base / 2))
        scores["impact"] = max(0, min(5, base / 2))
        scores["implementation"] = max(0, min(5, base / 2))
        scores["composite"] = round(sum(scores.values()) / 3, 1)

        return scores

    def format_scores(self, scores: dict) -> list[str]:
        if not scores:
            return []
        lines = [
            "",
            "  ╔══════════════════════════════════════════╗",
            "  ║  HORIZON EUROPE — Estimated Eval Scores  ║",
            "  ╠══════════════════════════════════════════╣",
            f"  ║  Excellence:      {scores.get('excellence', 0):.1f} / 5.0              ║",
            f"  ║  Impact:          {scores.get('impact', 0):.1f} / 5.0              ║",
            f"  ║  Implementation:  {scores.get('implementation', 0):.1f} / 5.0              ║",
            f"  ║  Composite:       {scores.get('composite', 0):.1f} / 5.0              ║",
            "  ╚══════════════════════════════════════════╝",
        ]
        return lines

    # --- Structural checks (called by core engine) ---

    @staticmethod
    def _check_partner_countries(model: "ProposalModel", result: "AnalysisResult"):
        countries = set(p.country for p in model.partners if p.country)
        if 0 < len(countries) < 3:
            result.add(
                "Insufficient Country Diversity", "CRITICAL", 0,
                f"Only {len(countries)} country/ies detected ({', '.join(countries)}). "
                "Horizon Europe typically requires ≥3 independent EU/Associated countries.",
                "Add partners from additional EU/Associated countries.",
                "structural", 1,
            )

    @staticmethod
    def _check_page_count(model: "ProposalModel", result: "AnalysisResult"):
        limits = {"RIA": 45, "IA": 45, "CSA": 30, "ERC": 25}
        at = model.action_type.upper() if model.action_type else ""
        for key, limit in limits.items():
            if key in at and model.part_b_pages > limit:
                result.add(
                    "Page Limit Exceeded", "CRITICAL", 0,
                    f"{at}: Part B is {model.part_b_pages} pages, limit is {limit}.",
                    f"Cut Part B to ≤{limit} pages.",
                    "structural", 1,
                )

    @staticmethod
    def _check_action_trl(model: "ProposalModel", result: "AnalysisResult"):
        at = model.action_type.upper() if model.action_type else ""
        text_lower = model.full_text.lower()
        trls = [int(m.group(1)) for m in re.finditer(r'TRL[\s\-]*(\d)', text_lower)]
        if trls:
            max_trl = max(trls)
            if "RIA" in at and max_trl > 5:
                result.add(
                    "TRL Too High for RIA", "HIGH", 0,
                    f"RIA found with TRL {max_trl}. RIAs typically target TRL 2-5.",
                    "Verify action type or adjust TRL claims.",
                    "structural", 1,
                )
            if "IA" in at and max_trl < 5:
                result.add(
                    "TRL Too Low for IA", "HIGH", 0,
                    f"IA found with max TRL {max_trl}. IAs typically start at TRL 5+.",
                    "Verify action type or adjust TRL claims.",
                    "structural", 1,
                )

    @staticmethod
    def _check_industry_pm(model: "ProposalModel", result: "AnalysisResult"):
        at = model.action_type.upper() if model.action_type else ""
        if "IA" not in at:
            return
        total_pm = sum(p.person_months for p in model.partners)
        industry_pm = sum(p.person_months for p in model.partners if p.is_sme or not p.country)
        if total_pm > 0 and industry_pm / total_pm < 0.4:
            result.add(
                "Low Industry Effort for IA", "MEDIUM", 0,
                f"Industry accounts for {industry_pm / total_pm * 100:.0f}% of PMs. "
                "IAs expect ≥40-50% industry-driven effort.",
                "Increase industry partner person-months or reclassify.",
                "structural", 1,
            )

    @staticmethod
    def _check_management_wp(model: "ProposalModel", result: "AnalysisResult"):
        for wp in model.work_packages:
            if "management" in (wp.title or "").lower() or "coordination" in (wp.title or "").lower():
                total_pm = sum(p.person_months for p in model.partners)
                if total_pm > 0 and wp.effort_pm > total_pm * 0.10:
                    result.add(
                        "Excessive Management Effort", "MEDIUM", 0,
                        f"Management WP uses {wp.effort_pm:.0f} PM ({wp.effort_pm / total_pm * 100:.0f}% of total). "
                        "Reviewers flag management >10% as overhead.",
                        "Reduce management WP to ≤10% of total PMs.",
                        "structural", 1,
                    )

    @staticmethod
    def _check_subcontracting(model: "ProposalModel", result: "AnalysisResult"):
        if model.budget_total > 0 and model.subcontracting_total > 0:
            ratio = model.subcontracting_total / model.budget_total
            if ratio > 0.30:
                result.add(
                    "Subcontracting Ratio High", "HIGH", 0,
                    f"Subcontracting is {ratio * 100:.0f}% of total budget. "
                    "EC expects most work done by beneficiaries.",
                    "Justify subcontracting or reduce ratio to <30%.",
                    "structural", 1,
                )

    @staticmethod
    def _check_equipment(model: "ProposalModel", result: "AnalysisResult"):
        if model.budget_total > 0 and model.equipment_total > 0:
            ratio = model.equipment_total / model.budget_total
            if ratio > 0.15:
                result.add(
                    "Equipment Cost Ratio High", "MEDIUM", 0,
                    f"Equipment is {ratio * 100:.0f}% of total budget. Justify carefully.",
                    "Only claim depreciation during project lifetime.",
                    "structural", 1,
                )

    # --- Anti-pattern detectors (stubs — these delegate to existing core checks) ---
    # In future versions these will contain the full logic extracted from core.
    # For now the core engine's existing detectors handle these.

    @staticmethod
    def _detect_ssh_copypaste(pages, result, start, model):
        pass  # Handled by core check_copy_paste_ssh

    @staticmethod
    def _detect_lump_sum(pages, result, start, model):
        pass  # Handled by core check_lump_sum

    @staticmethod
    def _detect_exploitation(pages, result, start, model):
        pass  # Handled by core check_exploitation

    @staticmethod
    def _detect_de_conflation(pages, result, start, model):
        pass  # Handled by core check_dissemination_exploitation_conflation

    @staticmethod
    def _detect_consortium_diversity(pages, result, start, model):
        pass  # Handled by core check_consortium_diversity

    @staticmethod
    def _detect_theory_of_change(pages, result, start, model):
        pass  # Handled by core check_theory_of_change

    @staticmethod
    def _detect_gender_dimension(pages, result, start, model):
        pass  # Handled by core check_gender_dimension
