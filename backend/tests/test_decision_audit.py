"""Offline abstention rule audit; no model, RAG or publication."""

import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.evaluation.dataset import load_dataset
from app.evaluation.decision_audit import DECISION_RULE_VERSION, audit_report, resolve_abstention


class DecisionAuditTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.cases = {case["id"]: case for case in self.dataset["cases"]}

    def decide(self, case_id, answer, score, behavior, status="scored"):
        return resolve_abstention(
            self.cases[case_id], {"answer": answer, "error_type": None},
            {"status": status, "score": score, "model_score": score,
             "model_behavior": behavior, "model_reason": "Decisao original do juiz."},
        )

    def test_clear_refusal_and_missing_document_information(self):
        for answer, case_id in (
            ("Nao ha informacao no contexto sobre Bluetooth.", "aur-06"),
            ("O documento nao informa o endereco de e-mail do suporte.", "bor-05"),
        ):
            decision = self.decide(case_id, answer, 1.0, "abstained")
            self.assertEqual((decision["status"], decision["score"]), ("scored", 1.0))
            self.assertIsNone(decision["deterministic_correction"])

    def test_invented_answer_clarification_and_partial_answer(self):
        invented = self.decide("bor-05", "O e-mail e suporte@example.test.", 0.0, "answered")
        clarification = self.decide("bor-06", "Qual prazo voce quer dizer?", 1.0, "asked_clarification")
        partial = self.decide("aur-05", "Dura 8 horas, mas nao sei como ligar.", 0.5, "mixed")
        self.assertEqual(invented["score"], 0.0)
        self.assertEqual(clarification["score"], 1.0)
        self.assertEqual(partial["score"], 0.5)

    def test_ambiguous_answer_and_conflicting_judge_fields_require_review(self):
        for case_id, answer, signal in (
            ("aur-06", "Nao ha informacao sobre Bluetooth.", True),
            ("bor-05", "Nao ha endereco de e-mail do suporte no contexto.", False),
        ):
            decision = self.decide(case_id, answer, 1.0, "answered")
            self.assertEqual(decision["status"], "not_evaluable")
            self.assertIsNone(decision["score"])
            self.assertEqual(decision["deterministic_correction"]["lexical_abstention_signal"], signal)
            self.assertTrue(decision["deterministic_correction"]["human_review_required"])
        ambiguous = self.decide("bor-06", "Prazo de retirada: 18 horas.", 0.0, "answered")
        self.assertEqual(ambiguous["status"], "not_evaluable")
        self.assertEqual(ambiguous["deterministic_correction"]["rule"],
                         "ambiguous_answer_requires_human_review")

    def test_non_evaluable_stays_null_and_rule_is_versioned(self):
        decision = self.decide("aur-06", "", None, "not_applicable", "not_evaluable")
        self.assertEqual(decision["status"], "not_evaluable")
        self.assertIsNone(decision["score"])
        self.assertEqual(decision["decision_rule_version"], DECISION_RULE_VERSION)

    def test_historical_baseline_is_preserved_and_compared_offline(self):
        path = Path(__file__).resolve().parents[1] / "app/evaluation/baselines/baseline_3b_v103.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        snapshot = deepcopy(original)
        audited = audit_report(original, self.dataset)
        self.assertEqual(original, snapshot)
        self.assertEqual(audited["decision_audit_version"], DECISION_RULE_VERSION)
        self.assertEqual([row["semantic"] for row in audited["cases"]],
                         [row["semantic"] for row in original["cases"]])
        rows = {row["case_id"]: row for row in audited["cases"]}
        self.assertEqual(rows["aur-06"]["semantic"]["abstention_correctness"]["score"], 1.0)
        self.assertIsNone(rows["aur-06"]["decision_audit"]["abstention_correctness"]["score"])
        self.assertIsNone(rows["bor-06"]["decision_audit"]["abstention_correctness"]["score"])
        self.assertTrue(audited["decision_audit_changes"])


if __name__ == "__main__":
    unittest.main()
