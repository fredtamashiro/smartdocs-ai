"""Semantic evaluation tests use a fake judge and never call OpenAI or Langfuse."""

import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.evaluation.cli import compare_reports
from app.evaluation.dataset import cloud_dataset_name, load_dataset
from app.evaluation.judge import JudgeVerdict, judge_report, validate_synthetic_report


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        case = self.dataset["cases"][0]
        self.report = {
            "dataset": cloud_dataset_name(self.dataset), "dataset_sha256": self.dataset["sha256"],
            "dataset_version": self.dataset["version"], "metrics_version": "1.0.1",
            "run_name": "synthetic-test", "published": False, "experiment_id": None,
            "summary": {}, "cases": [{"case_id": case["id"], "question": case["question"],
                "document": case["document"], "expected": case["expected"],
                "output": {"answer": "Pressione INICIAR por 3 segundos (p. 1).",
                           "source_pages": [1], "error_type": None},
                "metrics": {"fact_coverage_lexical": 1.0}, "trace_id": None}],
        }
        self.settings = SimpleNamespace(app_env="test")

    def _judge(self, score=1.0):
        fake = MagicMock()
        fake.invoke.return_value = {"parsed": JudgeVerdict(status="scored", score=score,
            reason="Fatos e evidências coerentes.", response_behavior="answered"), "parsing_error": None,
            "raw": SimpleNamespace(usage_metadata={"input_tokens": 20,
                                                      "output_tokens": 8, "total_tokens": 28})}
        return fake

    def test_structured_verdict_validation(self):
        self.assertEqual(JudgeVerdict.model_validate({"status": "scored", "score": 0.5,
                                                      "reason": "Parcial.",
                                                      "response_behavior": "not_applicable"}).score, 0.5)
        for payload in ({"status": "scored", "score": 1.2, "reason": "inválido"},
                        {"status": "not_evaluable", "score": 0, "reason": "inválido"},
                        {"status": "scored", "score": None, "reason": "inválido"}):
            with self.assertRaises(ValidationError):
                JudgeVerdict.model_validate(payload)

    def test_local_judge_uses_synthetic_evidence_and_never_publishes(self):
        fake = self._judge()
        with patch("app.config.get_settings", return_value=self.settings), patch(
            "app.graph.manual_graph.answer_question_with_manual_graph", side_effect=AssertionError("RAG called")
        ):
            judged = judge_report(self.report, self.dataset, model="judge-test", judge=fake,
                                  concurrency=1)
        self.assertEqual(fake.invoke.call_count, 2)
        self.assertIn("3 segundos", fake.invoke.call_args_list[0].args[0])
        self.assertEqual(judged["cases"][0]["evidence_origin"], "synthetic_pages_reconstructed_incomplete")
        self.assertEqual(judged["semantic_summary"]["answer_correctness"]["mean_score"], 1.0)
        self.assertIsNone(judged["cases"][0]["semantic"]["faithfulness"]["score"])
        self.assertFalse(judged["scores_published"])

    def test_timeout_and_parsing_failure_are_not_evaluable(self):
        fake = self._judge()
        fake.invoke.side_effect = TimeoutError("private error")
        with patch("app.config.get_settings", return_value=self.settings):
            judged = judge_report(self.report, self.dataset, model="judge-test", judge=fake)
        verdict = judged["cases"][0]["semantic"]["answer_correctness"]
        self.assertIsNone(verdict["score"])
        self.assertEqual(verdict["error_type"], "TimeoutError")
        self.assertNotIn("private error", verdict["reason"])
        fake.invoke.side_effect = None
        fake.invoke.return_value = {"parsed": None, "parsing_error": ValueError("bad"),
                                    "raw": SimpleNamespace()}
        with patch("app.config.get_settings", return_value=self.settings):
            judged = judge_report(self.report, self.dataset, model="judge-test", judge=fake)
        self.assertEqual(judged["cases"][0]["semantic"]["answer_correctness"]["error_type"], "ValueError")

    def test_not_evaluable_without_reference_or_evidence(self):
        case = next(case for case in self.dataset["cases"] if case["id"] == "aur-06")
        report = deepcopy(self.report)
        row = report["cases"][0]
        row.update(case_id=case["id"], question=case["question"], document=case["document"],
                   expected=case["expected"])
        row["output"] = {"answer": "Não há informação sobre Bluetooth.",
                         "source_pages": [], "error_type": None}
        fake = self._judge()
        with patch("app.config.get_settings", return_value=self.settings):
            judged = judge_report(report, self.dataset, model="judge-test", judge=fake)
        semantic = judged["cases"][0]["semantic"]
        self.assertIsNone(semantic["answer_correctness"]["score"])
        self.assertIsNone(semantic["faithfulness"]["score"])
        self.assertEqual(fake.invoke.call_count, 1)

    def test_abstention_score_behavior_conflict_requires_review(self):
        case = next(case for case in self.dataset["cases"] if case["id"] == "bor-06")
        report = deepcopy(self.report)
        row = report["cases"][0]
        row.update(case_id=case["id"], question=case["question"], document=case["document"],
                   expected=case["expected"])
        row["output"] = {"answer": "Interpreto prazo como retirada até as 18 horas.",
                         "source_pages": [3], "error_type": None}
        fake = self._judge(score=1.0)
        with patch("app.config.get_settings", return_value=self.settings):
            judged = judge_report(report, self.dataset, model="judge-test", judge=fake)
        verdict = judged["cases"][0]["semantic"]["abstention_correctness"]
        self.assertEqual(verdict["response_behavior"], "answered")
        self.assertEqual(verdict["model_score"], 1.0)
        self.assertIsNone(verdict["score"])
        self.assertEqual(verdict["status"], "not_evaluable")
        self.assertTrue(verdict["deterministic_correction"]["human_review_required"])

    def test_clear_refusal_does_not_hide_inconsistent_judge_label(self):
        case = next(case for case in self.dataset["cases"] if case["id"] == "aur-06")
        report = deepcopy(self.report)
        row = report["cases"][0]
        row.update(case_id=case["id"], question=case["question"], document=case["document"],
                   expected=case["expected"])
        row["output"] = {"answer": "Nao ha informacao sobre Bluetooth no manual.",
                         "source_pages": [2], "error_type": None}
        with patch("app.config.get_settings", return_value=self.settings):
            judged = judge_report(report, self.dataset, model="judge-test", judge=self._judge(1.0))
        verdict = judged["cases"][0]["semantic"]["abstention_correctness"]
        self.assertEqual(verdict["model_behavior"], "answered")
        self.assertEqual(verdict["response_behavior"], "answered")
        self.assertIsNone(verdict["score"])
        self.assertTrue(verdict["deterministic_correction"]["lexical_abstention_signal"])
        self.assertEqual(judged["error_analysis"]["judge_behavior_disagreements"], [])

    def test_publish_scores_correlate_to_original_item_trace(self):
        report = deepcopy(self.report)
        report.update(published=True, experiment_id="experiment-1")
        report["cases"][0]["trace_id"] = "a" * 32
        fake = self._judge()
        client = MagicMock()
        with patch("app.config.get_settings", return_value=self.settings):
            judged = judge_report(report, self.dataset, model="judge-test", judge=fake,
                                  publish=True, client=client)
        self.assertTrue(judged["scores_published"])
        self.assertEqual(judged["published_score_count"], 2)
        self.assertEqual(client.create_score.call_count, 2)
        for call in client.create_score.call_args_list:
            self.assertEqual(call.kwargs["trace_id"], "a" * 32)
            self.assertEqual(call.kwargs["metadata"]["case_id"], "aur-01")
        abstention_call = next(call for call in client.create_score.call_args_list
                               if call.kwargs["name"] == "smartdocs.abstention_correctness")
        self.assertEqual(abstention_call.kwargs["metadata"]["decision_rule_version"], "2.0.0")
        client.flush.assert_called_once()
        with patch("app.config.get_settings", return_value=self.settings):
            with self.assertRaises(ValueError):
                judge_report(self.report, self.dataset, model="judge-test", judge=fake,
                             publish=True, client=client)

    def test_synthetic_provenance_and_comparison(self):
        broken = deepcopy(self.report)
        broken["cases"][0]["question"] = "produção"
        with self.assertRaises(ValueError):
            validate_synthetic_report(broken, self.dataset)
        with patch("app.config.get_settings", return_value=self.settings):
            before = judge_report(self.report, self.dataset, model="judge-test", judge=self._judge(1))
            after = judge_report(self.report, self.dataset, model="judge-test", judge=self._judge(0.5))
        self.assertEqual(compare_reports(before, after)["semantic_changes"]["answer_correctness"]["delta"], -0.5)
        incompatible = deepcopy(after)
        incompatible.pop("decision_rule_versions")
        with self.assertRaises(ValueError):
            compare_reports(before, incompatible)


if __name__ == "__main__":
    unittest.main()
