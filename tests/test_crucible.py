"""
CRUCIBLE test suite — runs against a real proposal PDF if available,
falls back to synthetic tests for CI.
"""

import sys
import os
import re
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crucible import (
    extract_text,
    find_part_b_start,
    is_admin_page,
    get_full_text,
    get_part_b_text,
    ProposalModel,
    Finding,
    AnalysisResult,
    run_analysis,
    estimate_scores,
    run_pre_flight,
    score_pestled,
    score_eu_interop,
    score_stress_test,
    format_pestled,
    format_eu_interop,
    format_stress_test,
    PESTLED_DIMENSIONS,
    EU_INTEROP_LAYERS,
    STRESS_TEST,
    SMILE_PHASES,
    SMILE_PERSPECTIVES,
    PRE_FLIGHT_CHECKLIST,
    __version__,
)


EDGE_VERSE_PDF = Path(__file__).parent.parent.parent / "edge_verse_proposal.pdf"
HAS_PDF = EDGE_VERSE_PDF.exists()


class TestVersion:
    def test_version_format(self):
        assert re.match(r"\d+\.\d+\.\d+", __version__)


class TestDataStructures:
    def test_finding_creation(self):
        f = Finding("Test Pattern", "HIGH", 5, "some text", "fix it", "Cat", 4)
        assert f.pattern == "Test Pattern"
        assert f.severity == "HIGH"
        assert f.page == 5
        assert f.layer == 4

    def test_analysis_result_add(self):
        r = AnalysisResult()
        r.add("P1", "HIGH", 1, "text", "suggestion", "cat", 4)
        assert len(r.findings) == 1
        assert r.findings[0].pattern == "P1"

    def test_analysis_result_counts_by_severity(self):
        r = AnalysisResult()
        r.add("P1", "CRITICAL", 1, "t", "s", "c", 4)
        r.add("P2", "HIGH", 2, "t", "s", "c", 4)
        r.add("P3", "HIGH", 3, "t", "s", "c", 4)
        r.add("P4", "LOW", 4, "t", "s", "c", 4)
        counts = {}
        for f in r.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        assert counts["CRITICAL"] == 1
        assert counts["HIGH"] == 2
        assert counts["LOW"] == 1

    def test_proposal_model_defaults(self):
        m = ProposalModel()
        assert m.acronym == ""
        assert len(m.partners) == 0
        assert m.budget_total == 0.0


class TestSmileFramework:
    def test_smile_has_six_phases(self):
        assert len(SMILE_PHASES) == 6

    def test_smile_has_three_perspectives(self):
        assert len(SMILE_PERSPECTIVES) == 3

    def test_smile_phases_have_markers(self):
        for phase_id, phase in SMILE_PHASES.items():
            assert "name" in phase
            assert "proposal_markers" in phase
            assert len(phase["proposal_markers"]) > 0

    def test_smile_perspectives_have_markers(self):
        for persp_id, persp in SMILE_PERSPECTIVES.items():
            assert "name" in persp
            assert "markers" in persp


class TestPreFlight:
    def test_preflight_has_ten_checks(self):
        assert len(PRE_FLIGHT_CHECKLIST) == 10

    def test_preflight_checks_have_required_fields(self):
        for check in PRE_FLIGHT_CHECKLIST:
            assert "id" in check
            assert "question" in check
            assert "why" in check
            assert "weight" in check
            assert "check" in check
            assert check["weight"] in ("BLOCKER", "CRITICAL", "HIGH", "MEDIUM")


class TestAdminPageDetection:
    def test_admin_page_detected(self):
        admin_text = "Administrative forms\nLegal name\nSME Data\nPIC\n12345"
        assert is_admin_page(admin_text)

    def test_part_b_not_admin(self):
        part_b_text = "1.1 Excellence\nThe proposed research addresses the critical need..."
        assert not is_admin_page(part_b_text)


class TestScoring:
    def test_score_range(self):
        r = AnalysisResult()
        m = ProposalModel()
        scores = estimate_scores(r, m)
        for criterion, score in scores.items():
            assert 1.0 <= score <= 5.0, f"{criterion} score {score} out of range"

    def test_penalties_reduce_score(self):
        r = AnalysisResult()
        m = ProposalModel()
        clean_scores = estimate_scores(r, m)

        r2 = AnalysisResult()
        r2.add("Unfilled Placeholder", "CRITICAL", 1, "t", "s", "c", 4)
        r2.add("Unfilled Placeholder", "CRITICAL", 2, "t", "s", "c", 4)
        r2.add("Unfilled Placeholder", "CRITICAL", 3, "t", "s", "c", 4)
        penalized_scores = estimate_scores(r2, m)

        assert penalized_scores["Excellence"] <= clean_scores["Excellence"]


@pytest.mark.skipif(not HAS_PDF, reason="EDGE-VERSE PDF not available")
class TestEdgeVerse:
    """Integration tests using the actual EDGE-VERSE proposal."""

    @pytest.fixture(scope="class")
    def analysis(self):
        output = run_analysis(
            str(EDGE_VERSE_PDF), None, verbose=False,
            budget_mode=False, eic_pathfinder=False,
        )
        result, model, smile, pf = output[0], output[1], output[2], output[3]
        return result, model, smile, pf

    def test_extracts_pages(self, analysis):
        _, model, _, _ = analysis
        assert model.total_pages > 100

    def test_finds_partners(self, analysis):
        _, model, _, _ = analysis
        assert len(model.partners) >= 10

    def test_finds_work_packages(self, analysis):
        _, model, _, _ = analysis
        assert len(model.work_packages) >= 5

    def test_finds_deliverables(self, analysis):
        _, model, _, _ = analysis
        assert len(model.deliverables) >= 20

    def test_finds_findings(self, analysis):
        result, _, _, _ = analysis
        assert len(result.findings) >= 30

    def test_all_findings_have_required_fields(self, analysis):
        result, _, _, _ = analysis
        for f in result.findings:
            assert f.pattern, "Finding missing pattern name"
            assert f.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
            assert f.layer in (1, 2, 3, 4)
            assert f.text, "Finding missing text"
            assert f.suggestion, "Finding missing suggestion"

    def test_detects_action_type(self, analysis):
        _, model, _, _ = analysis
        assert model.action_type in ("Innovation Action", "Research and Innovation Action", "")

    def test_score_estimates_reasonable(self, analysis):
        result, model, _, _ = analysis
        scores = estimate_scores(result, model)
        total = sum(scores.values())
        assert 3.0 <= total <= 15.0

    def test_smile_scores_returned(self, analysis):
        _, _, smile, _ = analysis
        assert smile is not None
        assert isinstance(smile, dict)

    def test_preflight_runs(self, analysis):
        _, _, _, pf = analysis
        assert pf is not None
        assert len(pf) == 10

    def test_findings_span_multiple_layers(self, analysis):
        result, _, _, _ = analysis
        layers = set(f.layer for f in result.findings)
        assert len(layers) >= 2, f"Findings only in layers: {layers}"


class TestPESTLED:
    def test_has_eight_dimensions(self):
        assert len(PESTLED_DIMENSIONS) == 8

    def test_dimensions_have_required_fields(self):
        for key, dim in PESTLED_DIMENSIONS.items():
            assert "name" in dim
            assert "description" in dim
            assert "markers" in dim
            assert "weight" in dim
            assert len(dim["markers"]) > 0

    def test_weights_sum_to_100(self):
        total = sum(d["weight"] for d in PESTLED_DIMENSIONS.values())
        assert total == 100

    def test_score_returns_all_dimensions(self):
        m = ProposalModel()
        m.full_text = "government policy regulation market revenue cost community stakeholder ai edge drone sustainability gdpr compliance ethical transparency urban reconstruction"
        scores = score_pestled(m)
        for key in PESTLED_DIMENSIONS:
            assert key in scores
        assert "_weighted_avg" in scores
        assert "_coverage" in scores

    def test_score_range(self):
        m = ProposalModel()
        m.full_text = "test"
        scores = score_pestled(m)
        for key, val in scores.items():
            if not key.startswith("_"):
                assert 1.0 <= val["score"] <= 5.0

    def test_format_returns_lines(self):
        m = ProposalModel()
        m.full_text = "government market community ai sustainability gdpr ethical urban"
        scores = score_pestled(m)
        lines = format_pestled(scores)
        assert len(lines) > 0
        assert any("PESTLE+D" in l for l in lines)


class TestEUInterop:
    def test_has_seven_layers(self):
        assert len(EU_INTEROP_LAYERS) == 7

    def test_layers_have_required_fields(self):
        for key, layer in EU_INTEROP_LAYERS.items():
            assert "name" in layer
            assert "description" in layer
            assert "markers" in layer
            assert "weight" in layer

    def test_weights_sum_to_100(self):
        total = sum(l["weight"] for l in EU_INTEROP_LAYERS.values())
        assert total == 100

    def test_score_returns_all_layers(self):
        m = ProposalModel()
        m.full_text = "api protocol citygml schema ontology governance license context trust community"
        scores = score_eu_interop(m)
        for key in EU_INTEROP_LAYERS:
            assert key in scores
        assert "_weighted_avg" in scores
        assert "_maturity" in scores

    def test_format_returns_lines(self):
        m = ProposalModel()
        m.full_text = "api schema ontology governance license context trust"
        scores = score_eu_interop(m)
        lines = format_eu_interop(scores)
        assert len(lines) > 0
        assert any("INTEROP" in l for l in lines)


class TestStressTest:
    def test_has_three_lenses(self):
        assert "concept" in STRESS_TEST
        assert "context" in STRESS_TEST
        assert "crisis" in STRESS_TEST

    def test_each_lens_has_checks(self):
        for key, test in STRESS_TEST.items():
            assert "name" in test
            assert "checks" in test
            assert len(test["checks"]) == 5

    def test_checks_have_required_fields(self):
        for key, test in STRESS_TEST.items():
            for check in test["checks"]:
                assert "id" in check
                assert "question" in check
                assert "positive" in check
                assert "negative" in check
                assert "weight" in check

    def test_score_returns_all_lenses(self):
        m = ProposalModel()
        m.full_text = "proof of principle bottleneck demonstrated network effect track record why now green deal easa customer uk fallback deputy cambridge open-source phase"
        scores = score_stress_test(m)
        assert "concept" in scores
        assert "context" in scores
        assert "crisis" in scores
        assert "_overall" in scores
        assert "_verdict" in scores

    def test_verdict_categories(self):
        m = ProposalModel()
        m.full_text = "test"
        scores = score_stress_test(m)
        assert scores["_verdict"] in ("STRESS-TESTED", "PARTIALLY RESILIENT", "FRAGILE")

    def test_format_returns_lines(self):
        m = ProposalModel()
        m.full_text = "proof of principle bottleneck demonstrated network effect track record"
        scores = score_stress_test(m)
        lines = format_stress_test(scores)
        assert len(lines) > 0
        assert any("STRESS TEST" in l for l in lines)
