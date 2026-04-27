"""
tests/test_candidates.py — Unit tests for manage-candidates.py (schema v1).

Tests cover:
  - Schema v1 field construction (build_candidate_v1)
  - Validation (validate_candidate_v1)
  - Auto-promotion gate (can_auto_promote)
  - High-risk keyword detection (contains_high_risk_keyword)
  - Classification derivation (compute_classification)
  - Type classification heuristic (classify_type)
  - Legacy migration (migrate_legacy)

Run with:
  python3 -m pytest tests/test_candidates.py -v
  # or
  python3 tests/test_candidates.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Allow running from repo root or tests/ directory
# ---------------------------------------------------------------------------
repo_root = Path(__file__).parent.parent
scripts_dir = repo_root / "scripts" / "context_access"
sys.path.insert(0, str(scripts_dir))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "manage_candidates",
    scripts_dir / "manage-candidates.py",
)
mc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evidence(kind="session_history", ref="batch 1", locator="batch:1:msg:1"):
    return [mc.make_evidence_entry(kind, ref, locator)]


def _build(**kwargs):
    """Build a schema v1 candidate with safe defaults."""
    defaults = dict(
        claim="- The project uses Python 3.11",
        topic_id="42",
        created_by="test-agent",
        evidence=_make_evidence(),
        confidence="high",
        risk="low",
    )
    defaults.update(kwargs)
    return mc.build_candidate_v1(**defaults)


# ---------------------------------------------------------------------------
# Tests: build_candidate_v1
# ---------------------------------------------------------------------------

class TestBuildCandidateV1(unittest.TestCase):

    def test_schema_version_is_1(self):
        c = _build()
        self.assertEqual(c["schema_version"], 1)

    def test_id_format(self):
        c = _build()
        self.assertTrue(c["id"].startswith("CAND-"), c["id"])

    def test_required_fields_present(self):
        c = _build()
        for field in ("schema_version", "id", "created_at", "created_by",
                      "topic_id", "type", "claim", "confidence", "risk",
                      "classification", "evidence", "status", "human_review"):
            self.assertIn(field, c, f"missing field: {field}")

    def test_auto_promotable_fact(self):
        c = _build(claim="- src/main.py is the entrypoint", confidence="high", risk="low")
        self.assertEqual(c["type"], "fact")
        self.assertTrue(c["classification"]["auto_promotable"])
        self.assertEqual(c["status"], "candidate")

    def test_high_risk_type_sets_needs_approval(self):
        c = _build(
            claim="- We decided to use append-only memory",
            fact_type="architecture_decision",
        )
        self.assertFalse(c["classification"]["auto_promotable"])
        self.assertTrue(c["classification"]["needs_human_approval"])
        self.assertEqual(c["status"], "needs-approval")

    def test_evidence_built_from_evidence_list(self):
        ev_entry = mc.make_evidence_entry("repo_doc", "README.md", "line:10")
        c = _build(evidence=[ev_entry])
        self.assertEqual(len(c["evidence"]), 1)
        ev = c["evidence"][0]
        self.assertEqual(ev["kind"], "repo_doc")
        self.assertEqual(ev["ref"], "README.md")
        self.assertEqual(ev["locator"], "line:10")

    def test_optional_fields_absent_when_not_provided(self):
        c = _build()
        self.assertNotIn("project", c)
        self.assertNotIn("summary", c)
        self.assertNotIn("suggested_target", c)

    def test_optional_fields_present_when_provided(self):
        c = _build(project="myproject", summary="context here",
                   suggested_target=".agent/memory/topic-42.md")
        self.assertEqual(c["project"], "myproject")
        self.assertEqual(c["summary"], "context here")
        self.assertEqual(c["suggested_targets"], [".agent/memory/topic-42.md"])

    def test_human_review_block(self):
        c = _build()
        hr = c["human_review"]
        self.assertIn("required", hr)
        self.assertIsNone(hr["decision"])
        self.assertIsNone(hr["reviewer"])

    def test_human_review_required_for_high_risk_type(self):
        c = _build(fact_type="constraint", claim="- Agents must never drop tables")
        self.assertTrue(c["human_review"]["required"])

    def test_human_review_not_required_for_fact(self):
        c = _build(claim="- App uses FastAPI", confidence="high", risk="low")
        self.assertFalse(c["human_review"]["required"])


# ---------------------------------------------------------------------------
# Tests: validate_candidate_v1
# ---------------------------------------------------------------------------

class TestValidateCandidateV1(unittest.TestCase):

    def test_valid_candidate_returns_no_errors(self):
        c = _build()
        errs = mc.validate_candidate_v1(c)
        self.assertEqual(errs, [], errs)

    def test_missing_schema_version(self):
        c = _build()
        del c["schema_version"]
        errs = mc.validate_candidate_v1(c)
        self.assertTrue(any("schema_version" in e for e in errs), errs)

    def test_wrong_schema_version(self):
        c = _build()
        c["schema_version"] = 0
        errs = mc.validate_candidate_v1(c)
        self.assertTrue(any("schema_version" in e for e in errs), errs)

    def test_missing_claim(self):
        c = _build()
        c["claim"] = ""
        errs = mc.validate_candidate_v1(c)
        self.assertTrue(any("claim" in e for e in errs), errs)

    def test_unknown_type(self):
        c = _build()
        c["type"] = "nonsense_type"
        errs = mc.validate_candidate_v1(c)
        self.assertTrue(any("type" in e for e in errs), errs)

    def test_invalid_confidence(self):
        c = _build()
        c["confidence"] = "very_high"
        errs = mc.validate_candidate_v1(c)
        self.assertTrue(any("confidence" in e for e in errs), errs)

    def test_invalid_risk(self):
        c = _build()
        c["risk"] = "none"
        errs = mc.validate_candidate_v1(c)
        self.assertTrue(any("risk" in e for e in errs), errs)

    def test_empty_evidence_list(self):
        c = _build()
        c["evidence"] = []
        errs = mc.validate_candidate_v1(c)
        self.assertTrue(any("evidence" in e for e in errs), errs)

    def test_invalid_status(self):
        c = _build()
        c["status"] = "pending"
        errs = mc.validate_candidate_v1(c)
        self.assertTrue(any("status" in e for e in errs), errs)


# ---------------------------------------------------------------------------
# Tests: can_auto_promote
# ---------------------------------------------------------------------------

class TestCanAutoPromote(unittest.TestCase):

    def test_clean_fact_passes(self):
        c = _build(claim="- The app uses FastAPI", confidence="high", risk="low")
        ok, reason = mc.can_auto_promote(c)
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "")

    def test_wrong_status_blocked(self):
        c = _build()
        c["status"] = "needs-approval"
        ok, reason = mc.can_auto_promote(c)
        self.assertFalse(ok)
        self.assertIn("status", reason)

    def test_high_risk_type_blocked(self):
        c = _build(fact_type="architecture_decision", claim="- We chose microservices")
        ok, reason = mc.can_auto_promote(c)
        self.assertFalse(ok)

    def test_high_risk_level_blocked(self):
        c = _build(risk="high")
        ok, reason = mc.can_auto_promote(c)
        # build_candidate_v1 sets status=needs-approval for high risk,
        # so can_auto_promote fails at the status gate (still correctly blocked)
        self.assertFalse(ok)

    def test_low_confidence_blocked(self):
        c = _build(confidence="low")
        ok, reason = mc.can_auto_promote(c)
        # build_candidate_v1 sets status=needs-approval for low confidence,
        # so can_auto_promote fails at the status gate (still correctly blocked)
        self.assertFalse(ok)

    def test_empty_evidence_blocked(self):
        c = _build()
        c["evidence"] = []
        ok, reason = mc.can_auto_promote(c)
        self.assertFalse(ok)
        self.assertIn("evidence", reason)

    def test_high_risk_keyword_in_claim_blocked(self):
        c = _build(claim="- The production database is PostgreSQL", confidence="high", risk="low")
        ok, reason = mc.can_auto_promote(c)
        # build_candidate_v1 sets status=needs-approval when keyword detected,
        # so can_auto_promote fails at the status gate (still correctly blocked)
        self.assertFalse(ok)

    def test_keyword_case_insensitive(self):
        c = _build(claim="- Uses a SECRET key for signing", confidence="high", risk="low")
        ok, reason = mc.can_auto_promote(c)
        self.assertFalse(ok)

    def test_schema_invalid_blocked(self):
        c = _build()
        c["schema_version"] = 0
        ok, reason = mc.can_auto_promote(c)
        self.assertFalse(ok)
        self.assertIn("schema", reason.lower())

    def test_medium_confidence_medium_risk_passes(self):
        c = _build(
            claim="- The API returns JSON responses",
            confidence="medium",
            risk="medium",
        )
        ok, reason = mc.can_auto_promote(c)
        self.assertTrue(ok, reason)


# ---------------------------------------------------------------------------
# Tests: contains_high_risk_keyword
# ---------------------------------------------------------------------------

class TestHighRiskKeyword(unittest.TestCase):

    def test_no_keyword(self):
        self.assertIsNone(mc.contains_high_risk_keyword("- The app uses FastAPI"))

    def test_keyword_production(self):
        result = mc.contains_high_risk_keyword("- The production server runs on AWS")
        self.assertIsNotNone(result)

    def test_keyword_secret(self):
        result = mc.contains_high_risk_keyword("- Store the secret in env vars")
        self.assertIsNotNone(result)

    def test_keyword_case_insensitive(self):
        result = mc.contains_high_risk_keyword("- Use a TOKEN for auth")
        self.assertIsNotNone(result)

    def test_keyword_gdpr(self):
        result = mc.contains_high_risk_keyword("- GDPR compliance is required")
        self.assertIsNotNone(result)

    def test_partial_word_not_matched(self):
        # "key" should only match whole word — "monkey" should not trigger
        result = mc.contains_high_risk_keyword("- The monkey patching approach works")
        self.assertIsNone(result)

    def test_keyword_token(self):
        result = mc.contains_high_risk_keyword("- The token expires after 1 hour")
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# Tests: classify_type
# ---------------------------------------------------------------------------

class TestClassifyType(unittest.TestCase):

    def test_architecture_decision(self):
        self.assertEqual(mc.classify_type("We decided to use microservices"), "architecture_decision")

    def test_constraint(self):
        self.assertEqual(mc.classify_type("Agents must never call the DB directly"), "constraint")

    def test_process_rule(self):
        self.assertEqual(mc.classify_type("The review process requires two approvals"), "process_rule")

    def test_preference(self):
        self.assertEqual(mc.classify_type("Dmitrii prefers explicit over implicit"), "preference")

    def test_resolved_issue(self):
        self.assertEqual(mc.classify_type("The flaky test was fixed in PR #42"), "resolved_issue")

    def test_default_fact(self):
        self.assertEqual(mc.classify_type("- The app uses Python 3.11"), "fact")


# ---------------------------------------------------------------------------
# Tests: compute_classification
# ---------------------------------------------------------------------------

class TestDeriveClassification(unittest.TestCase):

    def test_auto_promotable_fact(self):
        cls = mc.derive_classification("fact", "high", "low", "- src/main.py is the entrypoint")
        self.assertTrue(cls["auto_promotable"])
        self.assertFalse(cls["needs_human_approval"])

    def test_high_risk_type_never_auto(self):
        cls = mc.derive_classification("architecture_decision", "high", "low", "- something")
        self.assertFalse(cls["auto_promotable"])
        self.assertTrue(cls["needs_human_approval"])

    def test_high_risk_level_blocks(self):
        cls = mc.derive_classification("fact", "high", "high", "- something safe")
        self.assertFalse(cls["auto_promotable"])

    def test_low_confidence_blocks(self):
        cls = mc.derive_classification("fact", "low", "low", "- something safe")
        self.assertFalse(cls["auto_promotable"])

    def test_keyword_in_claim_blocks(self):
        cls = mc.derive_classification("fact", "high", "low", "- production server is AWS")
        self.assertFalse(cls["auto_promotable"])
        self.assertIn("keyword", cls["reason"])

    def test_reason_field_present(self):
        cls = mc.derive_classification("fact", "high", "low", "- safe claim")
        self.assertIn("reason", cls)
        self.assertIsInstance(cls["reason"], str)


# ---------------------------------------------------------------------------
# Tests: migrate_legacy (schema v0 → v1)
# ---------------------------------------------------------------------------

class TestMigrateLegacy(unittest.TestCase):

    def _legacy_fact(self):
        return {
            "id": "CAND-OLD-001",
            "created_at": "2026-01-01T00:00:00Z",
            "created_by": "old-agent",
            "topic_id": "42",
            "type": "fact",
            "claim": "- Something old",
            "status": "candidate",
        }

    def _legacy_arch(self):
        return {
            "id": "CAND-OLD-002",
            "created_at": "2026-01-01T00:00:00Z",
            "created_by": "old-agent",
            "topic_id": "42",
            "type": "architecture_decision",
            "claim": "- We chose append-only storage",
            "status": "candidate",
        }

    def test_schema_version_set_to_1(self):
        c = mc.migrate_legacy(self._legacy_fact())
        self.assertEqual(c["schema_version"], 1)

    def test_evidence_defaulted(self):
        c = mc.migrate_legacy(self._legacy_fact())
        self.assertIsInstance(c["evidence"], list)
        self.assertGreater(len(c["evidence"]), 0)
        self.assertEqual(c["evidence"][0]["kind"], "manual")

    def test_confidence_defaulted(self):
        c = mc.migrate_legacy(self._legacy_fact())
        self.assertEqual(c["confidence"], "medium")

    def test_risk_defaulted(self):
        c = mc.migrate_legacy(self._legacy_fact())
        self.assertEqual(c["risk"], "medium")

    def test_fact_status_set_to_needs_approval(self):
        """Legacy migration forces all non-terminal candidates to needs-approval for safety."""
        c = mc.migrate_legacy(self._legacy_fact())
        self.assertEqual(c["status"], "needs-approval")

    def test_arch_decision_moved_to_needs_approval(self):
        """High-risk type gets moved to needs-approval during migration."""
        c = mc.migrate_legacy(self._legacy_arch())
        self.assertEqual(c["status"], "needs-approval")

    def test_terminal_status_preserved(self):
        leg = self._legacy_fact()
        leg["status"] = "approved"
        c = mc.migrate_legacy(leg)
        self.assertEqual(c["status"], "approved")

    def test_v1_candidate_not_re_migrated(self):
        c = _build()
        original_id = c["id"]
        original_version = c["schema_version"]
        mc.migrate_legacy(c)
        self.assertEqual(c["id"], original_id)
        self.assertEqual(c["schema_version"], original_version)

    def test_classification_added(self):
        c = mc.migrate_legacy(self._legacy_fact())
        self.assertIn("classification", c)
        self.assertIn("auto_promotable", c["classification"])

    def test_human_review_added(self):
        c = mc.migrate_legacy(self._legacy_fact())
        self.assertIn("human_review", c)
        self.assertIsNone(c["human_review"]["decision"])


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
