"""Tests for the CRUCIBLE API server."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from server import app, _gate_response, _rate_limits, RATE_WINDOWS


class TestGateResponse:
    """Test tier gating without running the full analysis."""

    FULL = {
        "tool": "CRUCIBLE",
        "version": "5.1.0",
        "file": "test.pdf",
        "tier": "enterprise",
        "call_provided": False,
        "pages": 50,
        "model": {"acronym": "TEST", "title": "Test", "duration_months": 36,
                  "call_id": "", "action_type": "", "partner_count": 3,
                  "wp_count": 5, "deliverable_count": 10, "milestone_count": 5,
                  "citation_count": 20, "kpi_count": 5, "budget_total": 3000000,
                  "budget_eu": 3000000},
        "scores": {"Excellence": 3.5, "Impact": 3.0, "Implementation": 3.0},
        "total": 9.5,
        "composite": {"score": 4.1, "grade": "A", "components": {}},
        "smile_coverage": {"phase1": 50},
        "eic_pathfinder_scores": {"_weighted_total": 4.0},
        "strategic_dimensions": {"_weighted_avg": 4.5},
        "future_tech_radar": {"_weighted_avg": 3.8},
        "pestled_scores": {"_weighted_avg": 3.5},
        "eu_interop_scores": {"_weighted_avg": 3.9},
        "stress_test_scores": {"_overall": 4.0},
        "pre_flight": [],
        "findings": [
            {"pattern": "P1", "severity": "HIGH", "page": 1, "text": "t",
             "suggestion": "s", "category": "c", "layer": 4},
            {"pattern": "P2", "severity": "MEDIUM", "page": 2, "text": "t",
             "suggestion": "s", "category": "c", "layer": 4},
            {"pattern": "P3", "severity": "LOW", "page": 3, "text": "t",
             "suggestion": "s", "category": "c", "layer": 1},
            {"pattern": "P4", "severity": "HIGH", "page": 4, "text": "t",
             "suggestion": "s", "category": "c", "layer": 2},
            {"pattern": "P5", "severity": "CRITICAL", "page": 5, "text": "t",
             "suggestion": "s", "category": "c", "layer": 3},
            {"pattern": "P6", "severity": "HIGH", "page": 6, "text": "t",
             "suggestion": "s", "category": "c", "layer": 4},
        ],
        "finding_count": 6,
    }

    def test_enterprise_gets_everything(self):
        resp = _gate_response(self.FULL, "enterprise")
        assert resp["tier"] == "enterprise"
        assert resp["scores"] is not None
        assert resp["composite"] is not None
        assert resp["pestled_scores"] is not None
        assert resp["stress_test_scores"] is not None
        assert len(resp["findings"]) == 6

    def test_free_gates_findings(self):
        resp = _gate_response(self.FULL, "free")
        assert resp["tier"] == "free"
        assert resp["scores"] is None
        assert resp["total"] is None
        assert resp["composite"] is None
        assert resp["pestled_scores"] is None
        assert resp["eic_pathfinder_scores"] is None
        assert all(f["layer"] == 4 for f in resp["findings"])
        assert len(resp["findings"]) <= 5

    def test_single_gates_advanced(self):
        resp = _gate_response(self.FULL, "single")
        assert resp["tier"] == "single"
        assert resp["scores"] is not None
        assert resp["composite"] is None
        assert resp["pestled_scores"] is None
        assert len(resp["findings"]) <= 25

    def test_pro_keeps_scores(self):
        resp = _gate_response(self.FULL, "pro")
        assert resp["scores"] is not None
        assert resp["smile_coverage"] is not None
        assert len(resp["findings"]) == 6

    def test_gate_does_not_mutate_original(self):
        original_count = len(self.FULL["findings"])
        _gate_response(self.FULL, "free")
        assert len(self.FULL["findings"]) == original_count

    def test_model_always_present(self):
        for tier in ["free", "single", "pro", "enterprise"]:
            resp = _gate_response(self.FULL, tier)
            assert resp["model"]["acronym"] == "TEST"
            assert resp["pages"] == 50


class TestRateLimiting:
    def setup_method(self):
        _rate_limits.clear()

    def test_rate_windows_defined(self):
        for tier in ["free", "single", "pro", "enterprise"]:
            assert tier in RATE_WINDOWS
            max_req, window = RATE_WINDOWS[tier]
            assert max_req > 0
            assert window > 0

    def test_free_is_most_restrictive(self):
        assert RATE_WINDOWS["free"][0] < RATE_WINDOWS["pro"][0]

    def test_enterprise_is_most_permissive(self):
        assert RATE_WINDOWS["enterprise"][0] > RATE_WINDOWS["pro"][0]


class TestHealthEndpoint:
    """Test that the app imports and mounts correctly."""

    def test_app_has_routes(self):
        routes = [r.path for r in app.routes]
        assert "/health" in routes
        assert "/analyze" in routes
