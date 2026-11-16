"""Offline calibration and human-review agreement tests."""

import unittest
import json
from copy import deepcopy
from pathlib import Path

from app.evaluation.calibration import (
    CALIBRATION_VERSION, CALIBRATED_RUBRICS, calibrate_report, classify_case,
    compare_rubric_versions, evidence_provenance,
)
from app.evaluation.dataset import cloud_dataset_name, load_dataset
from app.evaluation.human_review import compare_human_review, create_review_template
from app.evaluation.judge import CRITERIA, RUBRIC_VERSION


def _verdict(score, behavior=None, model_behavior=None, model_score=None):
    return {"status": "scored" if score is not None else "not_evaluable", "score": score,
            "reason": "Decisão 3B.", "model_reason": "Justificativa original do juiz.",
            "response_behavior": behavior, "model_behavior": model_behavior or behavior,
            "model_score": score if model_score is None else model_score,
            "rubric_version": RUBRIC_VERSION, "error_type": None}


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        cases = {case["id"]: case for case in self.dataset["cases"]}
        answers = {
            "aur-06": "Não há informação sobre Bluetooth no documento.",
            "aur-07": "Temperatura a cada 5 minutos, umidade a cada 10 minutos e dados por 30 dias.",
            "bor-05": "O e-mail não está presente no contexto.",
            "bor-06": "Interpreto prazo como retirada até as 18 horas.",
            "aur-05": "A bateria dura 8 horas, mas não sei como ligar.",
        }
        rows = []
        for case_id, answer in answers.items():
            case = cases[case_id]
            absent = case_id in {"aur-06", "bor-05"}
            ambiguous = case_id in {"aur-07", "bor-06"}
            abstention = _verdict(1.0 if absent else 0.0 if ambiguous else 0.5,
                                 "abstained" if absent else "answered",
                                 "answered" if case_id == "aur-06" else None)
            if case_id == "aur-06":
                abstention["model_score"] = 1.0
            rows.append({"case_id": case_id, "question": case["question"],
                         "document": case["document"], "expected": case["expected"],
                         "output": {"answer": answer, "source_pages": [2], "error_type": None},
                         "evidence_origin": "synthetic_pages_reconstructed",
                         "semantic": {
                             "answer_correctness": _verdict(None if not case["expected"]["answerable"] else 0.5),
                             "faithfulness": _verdict(1.0),
                             "abstention_correctness": abstention,
                         }, "metrics": {"fact_coverage_lexical": None}})
        self.report = {"dataset": cloud_dataset_name(self.dataset),
                       "dataset_version": self.dataset["version"],
                       "dataset_sha256": self.dataset["sha256"], "run_name": "test-run",
                       "model_configured": "rag-test", "judge_model": "judge-test",
                       "rubric_versions": {criterion: RUBRIC_VERSION for criterion in CRITERIA},
                       "semantic_summary": {criterion: {"mean_score": 1.0} for criterion in CRITERIA},
                       "cases": rows}

    def test_ambiguity_classification_is_review_aid_not_dataset_change(self):
        original = deepcopy(self.dataset)
        cases = {case["id"]: case for case in self.dataset["cases"]}
        aur = classify_case(cases["aur-07"], self.report["cases"][1]["output"]["answer"])
        bor = classify_case(cases["bor-06"], self.report["cases"][3]["output"]["answer"])
        self.assertEqual(aur["kind"], "ambiguous")
        self.assertTrue(aur["multi_interpretation_candidate"])
        self.assertFalse(bor["multi_interpretation_candidate"])
        self.assertEqual(self.dataset, original)

    def test_calibration_preserves_original_and_separates_correction(self):
        original = deepcopy(self.report)
        result = calibrate_report(self.report, self.dataset)
        self.assertEqual(self.report, original)
        self.assertEqual(result["rubric_versions"], original["rubric_versions"])
        self.assertEqual(result["rubric_versions_calibrated"], CALIBRATED_RUBRICS)
        self.assertEqual(result["calibration_version"], CALIBRATION_VERSION)
        aur = next(row for row in result["cases"] if row["case_id"] == "aur-06")
        self.assertEqual(aur["semantic"]["faithfulness"]["score"], 1.0)
        self.assertIsNone(aur["calibrated_semantic"]["faithfulness"]["score"])
        correction = aur["calibrated_semantic"]["abstention_correctness"]["deterministic_correction"]
        self.assertEqual(correction["model_behavior"], "answered")
        self.assertEqual(correction["final_behavior"], "abstained")
        self.assertTrue(correction["detector_confirmed"])
        for case_id in ("aur-07", "bor-06"):
            row = next(row for row in result["cases"] if row["case_id"] == case_id)
            self.assertEqual(row["semantic"]["abstention_correctness"]["score"], 0.0)
            self.assertIsNone(row["calibrated_semantic"]["abstention_correctness"]["score"])
        self.assertEqual(result["calibrated_summary"]["faithfulness"]["scored"], 0)

    def test_displayed_and_missing_evidence_are_not_complete(self):
        row = deepcopy(self.report["cases"][0])
        self.assertEqual(evidence_provenance(row)["completeness"], "incomplete")
        row["evidence_origin"] = "displayed_sources"
        row["output"]["displayed_source_previews"] = [{"text": "Trecho sintético"}]
        self.assertEqual(evidence_provenance(row)["completeness"], "incomplete")
        row["output"]["displayed_source_previews"] = []
        self.assertEqual(evidence_provenance(row)["completeness"], "unavailable")

    def test_human_template_blank_and_agreement_respects_not_evaluable(self):
        calibrated = calibrate_report(self.report, self.dataset)
        review = create_review_template(calibrated)
        self.assertEqual(len(review["cases"]), 5)
        self.assertTrue(all(decision["status"] is None and decision["score"] is None
                            for row in review["cases"] for decision in row["human"].values()))
        items = {row["case_id"]: row for row in review["cases"]}
        items["aur-06"]["human"]["abstention_correctness"].update(status="scored", score=1.0)
        items["aur-06"]["human"]["faithfulness"].update(status="not_evaluable")
        items["aur-07"]["human"]["abstention_correctness"].update(
            status="scored", score=1.0, observations="Cobriu interpretações suficientes.")
        compared = compare_human_review(calibrated, review)
        abstention = compared["human_review"]["summary"]["abstention_correctness"]
        self.assertEqual(abstention["reviewed"], 2)
        self.assertEqual(abstention["status_agreement_rate"], 0.5)
        self.assertEqual(abstention["score_agreement_rate"], 1.0)
        self.assertEqual(abstention["divergences"][0]["case_id"], "aur-07")
        self.assertEqual(compared["human_review"]["summary"]["faithfulness"]["both_not_evaluable"], 1)
        self.assertEqual(compared["human_review"]["original_summary"]["faithfulness"]["both_not_evaluable"], 0)
        self.assertIsNone(calibrated["human_review"])
        items["bor-06"]["human"]["abstention_correctness"].update(status="scored", score=1.5)
        with self.assertRaises(ValueError):
            compare_human_review(calibrated, review)

    def test_compare_rubric_versions_requires_same_run(self):
        calibrated = calibrate_report(self.report, self.dataset)
        comparison = compare_rubric_versions(self.report, calibrated)
        self.assertEqual(comparison["calibrated_rubrics"], CALIBRATED_RUBRICS)
        self.assertTrue(comparison["changed_decisions"])
        other = deepcopy(calibrated)
        other["run_name"] = "other"
        with self.assertRaises(ValueError):
            compare_rubric_versions(self.report, other)
        other = deepcopy(calibrated)
        other["cases"][0]["semantic"]["faithfulness"]["score"] = 0.0
        with self.assertRaises(ValueError):
            compare_rubric_versions(self.report, other)

    def test_versioned_baseline_recalibrates_without_model_calls(self):
        path = Path(__file__).resolve().parents[1] / "app/evaluation/baselines/baseline_3b_v103.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        calibrated = calibrate_report(original, self.dataset)
        self.assertEqual(len(original["cases"]), 18)
        self.assertEqual(original["rubric_versions"]["faithfulness"], "1.0.3")
        self.assertEqual(calibrated["calibrated_summary"]["faithfulness"]["not_evaluable"], 18)
        self.assertEqual(len(calibrated["calibration_changes"]), 20)
        self.assertNotIn("calibrated_semantic", original["cases"][0])


if __name__ == "__main__":
    unittest.main()
