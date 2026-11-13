import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from visual_platform.domain.compliance import evaluate_rules
from visual_platform.domain.facts import Facts
from visual_platform.domain.rules import RuleDocument


class RuleTests(unittest.TestCase):
    # Synthetic policy fixture, not a statement of any current marketplace policy.
    def setUp(self):
        self.rule = {
            "platform": "amazon",
            "version": "synthetic-test-1",
            "evidence_status": "verified",
            "config": {
                "complete_rule_set": True,
                "require_identity_review": False,
                "min_width": 100,
                "min_height": 100,
                "max_bytes": 1000,
                "require_white_background": True,
                "forbid_added_text": True,
                "forbid_added_watermarks": True,
                "min_product_long_edge_ratio": 0.5,
            },
        }
        self.facts = {
            "schema_version": 1,
            "analysis_complete": True,
            "image_width": 200,
            "image_height": 100,
            "text_items": [],
            "logo_items": [],
            "watermark_items": [],
            "background": {"classification": "white", "confidence": 0.99},
            "product_extent": {"bbox": [20, 10, 180, 90], "confidence": 0.99},
            "uncertainties": [],
        }
        self.local = {"width": 200, "height": 100, "byte_size": 500}

    def report(self, **kwargs):
        Facts.model_validate(self.facts)
        return evaluate_rules("a" * 64, [self.rule], self.facts, self.local, **kwargs)

    def reasons(self, result):
        return [r["code"] for p in result["per_platform"] for r in p["reasons"]]

    def test_complete_synthetic_rule_passes_and_scope_is_preserved(self):
        self.rule.update(marketplace="US", image_type="main")
        r = self.report()
        self.assertEqual(r["auto_overall"], "compliant")
        self.assertEqual(r["per_platform"][0]["rule_version"], "synthetic-test-1")
        self.assertEqual(r["per_platform"][0]["marketplace"], "US")

    def test_unknown_evidence_or_incomplete_rules_never_pass(self):
        for key, value in [("evidence_status", "unverified"), ("config", {})]:
            rule = copy.deepcopy(self.rule)
            self.rule[key] = value
            self.assertEqual(self.report()["auto_overall"], "manual_review")
            self.rule = rule
        self.assertEqual(
            evaluate_rules("a" * 64, [], self.facts, self.local)["auto_overall"], "manual_review"
        )

    def test_intrinsic_marks_preserved_added_marks_fail(self):
        for group in ("text_items", "logo_items", "watermark_items"):
            with self.subTest(group=group):
                self.facts[group] = [
                    {
                        "text": "physical brand",
                        "bbox": [20, 20, 40, 40],
                        "origin": "on_product",
                        "confidence": 0.99,
                    }
                ]
                self.assertEqual(self.report()["auto_overall"], "compliant")
                self.facts[group][0]["origin"] = "added_overlay"
                self.assertEqual(self.report()["auto_overall"], "non_compliant")
                self.facts[group] = []

    def test_unknown_mark_origin_and_low_confidence_require_review(self):
        for origin, confidence in [("unknown", 0.99), ("added_overlay", 0.2)]:
            self.facts["text_items"] = [
                {"text": "x", "bbox": [20, 20, 40, 40], "origin": origin, "confidence": confidence}
            ]
            r = self.report()
            self.assertEqual(r["auto_overall"], "manual_review")
            self.assertIn("mark_origin_uncertain", self.reasons(r))

    def test_hard_failure_dominates_uncertainty(self):
        self.facts["analysis_complete"] = False
        self.local["byte_size"] = 1001
        r = self.report()
        self.assertEqual(r["auto_overall"], "non_compliant")
        self.assertIn("max_bytes", self.reasons(r))
        self.rule["evidence_status"] = "unverified"
        self.assertEqual(self.report()["auto_overall"], "manual_review")
        self.assertEqual(
            self.report(hard_failures=["image_corrupt"])["auto_overall"], "non_compliant"
        )

    def test_sampling_and_identity_review(self):
        self.assertEqual(self.report(sampling_selected=True)["auto_overall"], "manual_review")
        self.rule["config"]["require_identity_review"] = True
        self.assertIn("product_identity_requires_review", self.reasons(self.report()))

    def test_low_confidence_background_and_facts_dimension_mismatch(self):
        self.facts["background"]["confidence"] = 0.1
        self.assertIn("background_uncertain", self.reasons(self.report()))
        self.local["width"] = 201
        self.assertIn("facts_dimension_mismatch", self.reasons(self.report()))

    def test_product_long_edge_uses_long_image_edge(self):
        self.facts["product_extent"]["bbox"] = [0, 0, 80, 80]
        self.assertIn("product_long_edge_ratio", self.reasons(self.report()))
        self.facts["product_extent"] = None
        self.assertEqual(self.report()["auto_overall"], "manual_review")

    def test_bad_config_is_review_not_worker_failure(self):
        self.rule["config"] = {"minimum_confidence": float("nan")}
        r = self.report()
        self.assertEqual(r["auto_overall"], "manual_review")
        self.assertIn("rule_config_invalid", self.reasons(r))

    def test_rule_document_requires_official_archived_evidence(self):
        doc = {
            "platform": "amazon",
            "marketplace": "US",
            "category": "general",
            "image_type": "main",
            "version": "test",
            "evidence_status": "verified",
            "config": {},
        }
        with self.assertRaises(ValidationError):
            RuleDocument.model_validate(doc)
        doc.update(
            source_urls=["https://sellercentral.amazon.com/help/test"],
            retrieved_at=datetime.now(timezone.utc),
            evidence_sha256="a" * 64,
        )
        RuleDocument.model_validate(doc)
        for url in [
            "https://amazon.com.evil.test/rule",
            "https://user:pass@amazon.com/rule",
            "http://amazon.com/rule",
        ]:
            doc["source_urls"] = [url]
            with self.assertRaises(ValidationError):
                RuleDocument.model_validate(doc)

    def test_checked_in_seeds_are_unverified_and_incomplete(self):
        paths = list(Path("rules/seeds").glob("*.json"))
        self.assertEqual(len(paths), 3)
        for path in paths:
            document = RuleDocument.model_validate(json.loads(path.read_text()))
            self.assertEqual(document.evidence_status, "unverified")
            self.assertFalse(document.config.complete_rule_set)

    def test_boolean_schema_version_is_not_integer(self):
        self.facts["schema_version"] = True
        with self.assertRaises(ValidationError):
            Facts.model_validate(self.facts)
