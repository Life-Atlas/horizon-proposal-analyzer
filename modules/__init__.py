"""
CRUCIBLE Module System — Call-specific plugins for proposal analysis.

Each funding body / call type has its own module that provides:
- Lexicon additions (call-specific terminology)
- Pre-flight questions
- Structural integrity checks
- Anti-pattern detectors
- Call-specific scoring
- Extraction hints (budget patterns, partner formats, etc.)

Auto-detection uses the spatial-temporal anchor to select the right module.
When no module matches, universal checks run and gaps are logged for
future incorporation ("lore learning").

MIT License — WINNIIO AB / Life Atlas
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from crucible import AnalysisResult, ProposalModel, ProposalAnchor

__all__ = ["CallModule", "ModuleRegistry", "LoreLog"]

LORE_FILE = Path(__file__).parent / "lore.json"


@dataclass
class CallModule:
    """Base class for all call-specific modules.

    Subclasses override methods to inject call-specific logic into the
    universal CRUCIBLE pipeline. Methods that return empty defaults are
    safe no-ops — the core engine skips them gracefully.
    """

    name: str = "base"
    version: str = "0.0.0"
    description: str = ""
    funding_body: str = ""
    languages: list = field(default_factory=list)
    countries: list = field(default_factory=list)

    def matches(self, anchor: "ProposalAnchor") -> float:
        """Return confidence 0.0–1.0 that this module handles the proposal.

        The registry picks the highest-scoring module above 0.3 threshold.
        """
        return 0.0

    def get_lexicon(self) -> dict[str, list[str]]:
        """Call-specific terminology → translation pairs."""
        return {}

    def get_preflight_questions(self) -> list[dict]:
        """Call-specific pre-flight gatekeeper questions.

        Each dict: {id, question, weight, check: callable(model, call_text) -> str}
        """
        return []

    def get_structural_checks(self) -> list[tuple[str, callable]]:
        """Call-specific structural checks.

        Each tuple: (name, fn(model, result) -> None)
        """
        return []

    def get_detectors(self) -> list[tuple[str, callable]]:
        """Call-specific anti-pattern detectors.

        Each tuple: (name, fn(pages, result, start, model) -> None)
        """
        return []

    def score(self, model: "ProposalModel", result: "AnalysisResult") -> Optional[dict]:
        """Call-specific scoring (e.g. EIC Pathfinder, Vinnova 4-criteria)."""
        return None

    def format_scores(self, scores: dict) -> list[str]:
        """Format call-specific scores for the text report."""
        return []

    def get_extraction_hints(self) -> dict:
        """Hints for the extraction engine.

        Keys: budget_patterns, partner_patterns, duration_patterns, etc.
        Each is a list of regex strings.
        """
        return {}

    def get_markers(self) -> dict[str, list[str]]:
        """Call-specific marker groups for scoring dimensions.

        Keys are dimension names, values are marker term lists.
        """
        return {}


class ModuleRegistry:
    """Discovers, registers, and selects call-specific modules."""

    def __init__(self):
        self._modules: list[CallModule] = []

    def register(self, module: CallModule):
        self._modules.append(module)

    def auto_detect(self, anchor: "ProposalAnchor") -> Optional[CallModule]:
        """Select the best module for this proposal based on spatial anchor."""
        candidates = []
        for mod in self._modules:
            score = mod.matches(anchor)
            if score > 0.3:
                candidates.append((score, mod))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def get_by_name(self, name: str) -> Optional[CallModule]:
        for mod in self._modules:
            if mod.name.lower() == name.lower():
                return mod
        return None

    def list_modules(self) -> list[str]:
        return [f"{m.name} v{m.version} — {m.description}" for m in self._modules]


class LoreLog:
    """Logs unmatched patterns for future module development.

    When CRUCIBLE encounters a proposal that no module recognizes,
    it records the anchor fingerprint and any unusual patterns.
    Humans review lore.json to decide what to incorporate.
    """

    @staticmethod
    def log_unknown(anchor: "ProposalAnchor", notes: list[str]):
        entries = []
        if LORE_FILE.exists():
            try:
                entries = json.loads(LORE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                entries = []

        entry = {
            "timestamp": datetime.now().isoformat(),
            "language": anchor.language,
            "country": anchor.country,
            "region": anchor.region,
            "funding_body": anchor.funding_body,
            "funding_program": anchor.funding_program,
            "doc_scale": anchor.doc_scale,
            "page_count": anchor.page_count,
            "word_count": anchor.word_count,
            "notes": notes,
            "incorporated": False,
        }
        entries.append(entry)

        LORE_FILE.write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                             encoding="utf-8")

    @staticmethod
    def get_unincorporated() -> list[dict]:
        if not LORE_FILE.exists():
            return []
        try:
            entries = json.loads(LORE_FILE.read_text(encoding="utf-8"))
            return [e for e in entries if not e.get("incorporated")]
        except (json.JSONDecodeError, OSError):
            return []


# Import and register built-in modules
_registry = ModuleRegistry()


def get_registry() -> ModuleRegistry:
    """Get the global module registry, populating it on first call."""
    if not _registry._modules:
        _load_builtin_modules()
    return _registry


def _load_builtin_modules():
    from modules.horizon_europe import HorizonEuropeModule
    from modules.vinnova import VinnovaModule

    _registry.register(HorizonEuropeModule())
    _registry.register(VinnovaModule())
