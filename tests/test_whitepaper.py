"""
Tests for the whitepaper module — SMILE canonical diagram scoring.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crucible import AnalysisResult, ProposalModel, ProposalAnchor, run_analysis
from modules import get_registry
from modules.whitepaper import (
    WhitepaperModule,
    DT_JOURNEY_STAGES,
    DIAGRAM_ELEMENTS,
    BLEND_WEIGHTS,
    SUPPRESSED_PATTERNS,
)


SMILE_TEXT = """
Zoom out to Zoom in — a whitepaper on benefits-driven digital twin
implementation. We start with Reality Emulation: creating a 3D shared
reality on a Reality Canvas with a virtual first mindset — record
everything. Stakeholder mapping and PESTELED analysis anchor the work.
Concurrent engineering follows: we invite to innovate, define the
as-is and to-be, validate hypotheses, and define the minimal viable
twin (MVT) against industry standards (ISO) and KPIs.
Collective intelligence emerges through scenario planning, table-top
exercises, open source tooling, and access to real-time data.
Contextual intelligence: physical sensors, ontology creation, BIM and
IFC alignment, data fabric integration, remote enablement.
Continuous intelligence: a 4D digital twin with connected everything,
real-time decisions, predictive analytics, and root cause analysis in
an ontology factory built on historic data and machine learning.
Perpetual wisdom: prescriptive maintenance, AI driven prognostics,
black swan identification, circular strategies, and AI factories with
distributed intelligence.
The Spin Twin Lifecycle spans Virtual Minimal Viable Twinning,
Prototype Launch, Interoperable Operation, and Phoenix Strategies —
a perpetual cycle where Phoenix Strategies loop back into Reality
Emulation. The journey never ends; it is a flywheel.
The AI Journey runs from human decision making through data
contextualization to AI-ready, AI-infused, AI-ingrained, and finally
explainable AI decision making.
The Digital Mesh altitude stack zooms out from component and asset to
factory, organization, operating context, and the global supply chain.
Create ontology factories as the foundation for AI factories, on a
knowledge graph ontology foundation creating relationships between
fragmented realities — a real-world planetary foundation in 3D,
understandable by all, from boardroom to shop floor.
Outcome, action, insight, information, data: continuous contextual
business transformation and knowledge transfer. People, planet, and
systems perspectives — tacit knowledge from people, GIS and satellite
data from the planet, standards and metadata mastery from systems.
"""


def _model_from_text(text: str, pages: int = 20) -> ProposalModel:
    m = ProposalModel()
    m.full_text = text
    m.part_b_text = text
    m.total_pages = pages
    return m


class TestRegistration:
    def test_whitepaper_registered(self):
        registry = get_registry()
        mod = registry.get_by_name("whitepaper")
        assert mod is not None
        assert isinstance(mod, WhitepaperModule)

    def test_listed(self):
        assert any("whitepaper" in d for d in get_registry().list_modules())


class TestAutoDetection:
    def test_matches_no_funder(self):
        anchor = ProposalAnchor(language="en", page_count=20)
        assert WhitepaperModule().matches(anchor) > 0.3

    def test_no_match_with_funder(self):
        anchor = ProposalAnchor(language="en", page_count=20,
                                funding_body="Vinnova")
        assert WhitepaperModule().matches(anchor) == 0.0

    def test_no_match_tiny_doc(self):
        anchor = ProposalAnchor(language="en", page_count=2)
        assert WhitepaperModule().matches(anchor) <= 0.3

    def test_does_not_hijack_horizon(self):
        anchor = ProposalAnchor(language="en", page_count=45,
                                funding_body="European Commission",
                                funding_program="Horizon Europe")
        registry = get_registry()
        selected = registry.auto_detect(anchor)
        assert selected is not None
        assert selected.name == "horizon-europe"


class TestMarkerSets:
    def test_six_dt_stages(self):
        assert len(DT_JOURNEY_STAGES) == 6
        names = [s["name"] for s in DT_JOURNEY_STAGES.values()]
        assert "Reality Emulation" in names
        assert "Perpetual Wisdom" in names

    def test_stages_have_markers(self):
        for stage in DT_JOURNEY_STAGES.values():
            assert len(stage["markers"]) >= 10
            assert all(m == m.lower() for m in stage["markers"])

    def test_diagram_elements_present(self):
        for key in ["perspective_people", "perspective_planet",
                    "perspective_systems", "spin_twin_lifecycle",
                    "ai_journey", "digital_mesh", "ontology_ai_factories",
                    "knowledge_graph", "value_chain", "understandable_by_all",
                    "record_everything", "perpetual_loop"]:
            assert key in DIAGRAM_ELEMENTS
            assert DIAGRAM_ELEMENTS[key]["markers"]

    def test_blend_weights_sum_to_one(self):
        assert abs(sum(BLEND_WEIGHTS.values()) - 1.0) < 1e-9


class TestSuppression:
    def test_proposal_findings_removed(self):
        mod = WhitepaperModule()
        result = AnalysisResult()
        result.add("Consortium Too Small", "CRITICAL", 0, "x", "y")
        result.add("Budget Not Parseable", "HIGH", 0, "x", "y")
        result.add("No Call Text Provided", "MEDIUM", 0, "x", "y")
        result.add("Dense Paragraphs", "MEDIUM", 3, "x", "y")
        result.add("Orphaned Acronyms", "MEDIUM", 0, "x", "y")
        mod.score(_model_from_text(SMILE_TEXT), result)
        patterns = [f.pattern for f in result.findings]
        assert "Consortium Too Small" not in patterns
        assert "Budget Not Parseable" not in patterns
        assert "No Call Text Provided" not in patterns
        # Whitepaper-appropriate quality checks survive
        assert "Dense Paragraphs" in patterns
        assert "Orphaned Acronyms" in patterns

    def test_suppressed_set_has_key_gatekeepers(self):
        for p in ["Ghost Partner", "WP Exceeds Duration",
                  "Ethics Self-Assessment Not Detected",
                  "Call Outcome Gap", "Page Limit Risk"]:
            assert p in SUPPRESSED_PATTERNS


class TestScoring:
    def test_score_structure(self):
        scores = WhitepaperModule().score(_model_from_text(SMILE_TEXT),
                                          AnalysisResult())
        for key in ["smile_diagram", "strategic", "future_radar", "pesteled",
                    "interop", "stress", "composite", "stages", "elements"]:
            assert key in scores
        assert 0.0 <= scores["composite"] <= 5.0
        assert len(scores["stages"]) == 6
        assert len(scores["elements"]) == len(DIAGRAM_ELEMENTS)

    def test_smile_text_scores_high_diagram_alignment(self):
        scores = WhitepaperModule().score(_model_from_text(SMILE_TEXT),
                                          AnalysisResult())
        assert scores["smile_diagram"] >= 3.0
        assert scores["elements"]["perpetual_loop"]["status"] != "MISSING"
        assert scores["elements"]["ontology_ai_factories"]["status"] != "MISSING"

    def test_off_topic_text_scores_low(self):
        text = "We sell shoes. Our shoes are comfortable and stylish. " * 200
        scores = WhitepaperModule().score(_model_from_text(text),
                                          AnalysisResult())
        assert scores["smile_diagram"] < 2.0

    def test_format_scores(self):
        mod = WhitepaperModule()
        scores = mod.score(_model_from_text(SMILE_TEXT), AnalysisResult())
        lines = mod.format_scores(scores)
        joined = "\n".join(lines)
        assert "WHITEPAPER" in joined
        assert "DT JOURNEY" in joined
        assert "DIAGRAM ELEMENT COVERAGE" in joined
        assert "COMPOSITE" in joined

    def test_format_scores_empty(self):
        assert WhitepaperModule().format_scores({}) == []


class TestStructuralChecks:
    def test_perpetual_loop_missing_flagged(self):
        mod = WhitepaperModule()
        model = _model_from_text("A digital twin document with no closure.")
        result = AnalysisResult()
        mod._check_perpetual_loop(model, result)
        assert any(f.pattern == "Perpetual Loop Not Closed"
                   for f in result.findings)

    def test_perpetual_loop_present_ok(self):
        mod = WhitepaperModule()
        result = AnalysisResult()
        mod._check_perpetual_loop(_model_from_text(SMILE_TEXT), result)
        assert not any(f.pattern == "Perpetual Loop Not Closed"
                       for f in result.findings)

    def test_key_elements_missing_flagged(self):
        mod = WhitepaperModule()
        result = AnalysisResult()
        mod._check_key_elements(_model_from_text("Shoes are great."), result)
        assert any(f.pattern.startswith("Diagram Element Missing")
                   for f in result.findings)


class TestEndToEnd:
    def test_run_analysis_with_forced_module(self, tmp_path):
        wp = tmp_path / "whitepaper.txt"
        wp.write_text(SMILE_TEXT * 5, encoding="utf-8")
        out = run_analysis(str(wp), module_name="whitepaper")
        active_module, module_scores = out[-2], out[-1]
        assert active_module is not None
        assert active_module.name == "whitepaper"
        assert module_scores is not None
        assert 0.0 <= module_scores["composite"] <= 5.0
        # No proposal-only findings survive
        result = out[0]
        patterns = {f.pattern for f in result.findings}
        assert not (patterns & SUPPRESSED_PATTERNS)
