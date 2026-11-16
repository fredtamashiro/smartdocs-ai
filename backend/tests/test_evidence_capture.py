"""Exact synthetic context capture, provenance, and privacy boundaries."""

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.evaluation.dataset import cloud_dataset_name, document_id, load_dataset
from app.evaluation.evidence_capture import (
    capture_synthetic_context, record_generation_input, verify_captured_record,
)
from app.evaluation.judge import RUBRIC_VERSIONS, judge_report
from app.evaluation.calibration import calibrate_report
from app.evaluation.runner import _task_factory
from app.services.langfuse_observability import collect_generation_usage, invoke_generation
from app.services.rag_service import build_context_from_chunks


class EvidenceCaptureTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.case = self.dataset["cases"][0]
        self.document = self.dataset["documents"][0]
        self.doc_id = document_id(self.dataset, self.document["ref"])
        chunks = [{"content": item["text"], "metadata": {"page": item["page"],
                    "chunk_index": index}} for index, item in enumerate(self.document["chunks"][:2])]
        self.context = build_context_from_chunks(chunks, max_chunks=2, max_chars_per_chunk=900)
        self.prompt = f"Pergunta: {self.case['question']}\nContexto:\n{self.context}\n"
        self.settings = SimpleNamespace(langfuse_tracing_enabled=False,
                                        langfuse_public_key="", langfuse_secret_key="",
                                        app_env="test")

    def _response(self):
        return SimpleNamespace(content="Pressione INICIAR por 3 segundos.",
                               usage_metadata={"input_tokens": 10, "output_tokens": 5,
                                               "total_tokens": 15}, response_metadata={"model_name": "test"})

    def test_captures_exact_context_order_ids_and_generation_link(self):
        seen_prompts = []
        def invoke(prompt):
            seen_prompts.append(prompt)
            return self._response()

        llm = SimpleNamespace(model_name="test", invoke=invoke)
        with patch("app.services.langfuse_observability.get_settings", return_value=self.settings):
            with capture_synthetic_context(self.dataset, self.case["id"], self.document["ref"], self.doc_id) as records:
                with collect_generation_usage() as usage:
                    invoke_generation(llm, "Classifique", name="smartdocs.rag.classify_batch", prompt_id="grader.v1")
                    invoke_generation(llm, self.prompt, name="smartdocs.rag.generate_answer", prompt_id="answer.v1")
        self.assertEqual(len(records), 2)
        self.assertEqual(seen_prompts, ["Classifique", self.prompt])
        answer = records[1]
        self.assertEqual(answer["generation_index"], 1)
        self.assertEqual(usage[1]["generation_index"], 1)
        self.assertEqual(answer["context_text"], self.context)
        self.assertEqual(answer["context_sha256"], hashlib.sha256(self.context.encode()).hexdigest())
        self.assertEqual([chunk["order"] for chunk in answer["chunks"]], [1, 2])
        self.assertEqual([chunk["chunk_index"] for chunk in answer["chunks"]], [0, 1])
        self.assertEqual(answer["llm_status"], "success")
        self.assertTrue(verify_captured_record(answer, self.dataset, self.case["id"], self.document["ref"]))
        with capture_synthetic_context(self.dataset, self.case["id"], self.document["ref"], self.doc_id) as repeated:
            second = record_generation_input("smartdocs.rag.generate_answer", self.prompt)
        self.assertEqual(second["context_sha256"], answer["context_sha256"])
        self.assertEqual([item["chunk_id"] for item in second["chunks"]],
                         [item["chunk_id"] for item in answer["chunks"]])

    def test_capture_is_off_by_default_and_rejects_foreign_text(self):
        self.assertIsNone(record_generation_input("smartdocs.rag.generate_answer", self.prompt))
        with self.assertRaises(ValueError):
            with capture_synthetic_context(self.dataset, self.case["id"], self.document["ref"], "wrong"):
                pass
        with capture_synthetic_context(self.dataset, self.case["id"], self.document["ref"], self.doc_id) as records:
            record_generation_input("smartdocs.rag.generate_answer", self.prompt.replace("3 segundos", "4 segundos"))
            record_generation_input("smartdocs.rag.generate_answer", "Contexto vazio")
        self.assertEqual([item["status"] for item in records], ["unavailable", "unavailable"])
        self.assertNotIn("context_text", records[0])

    def test_judge_requires_verified_context_and_calibration_preserves_score(self):
        with capture_synthetic_context(self.dataset, self.case["id"], self.document["ref"], self.doc_id) as records:
            record = record_generation_input("smartdocs.rag.generate_answer", self.prompt)
            record["llm_status"] = "success"
        row = {"case_id": self.case["id"], "question": self.case["question"],
               "document": self.case["document"], "expected": self.case["expected"],
               "output": {"answer": "Pressione INICIAR por 3 segundos.",
                          "generation_evidence": records,
                          "generations": [{"name": "smartdocs.rag.generate_answer", "generation_index": 0}],
                          "error_type": None},
               "metrics": {"fact_coverage_lexical": 1.0}, "trace_id": None}
        report = {"dataset": cloud_dataset_name(self.dataset), "dataset_version": self.dataset["version"],
                  "dataset_sha256": self.dataset["sha256"], "run_name": "captured-test",
                  "model_configured": "rag-test", "cases": [row]}
        fake = SimpleNamespace(invoke=lambda prompt: {
            "parsed": {"status": "scored", "score": 1.0, "reason": "Sustentada.",
                       "response_behavior": "answered"},
            "parsing_error": None, "raw": SimpleNamespace(usage_metadata={"total_tokens": 5})})
        with patch("app.config.get_settings", return_value=self.settings):
            judged = judge_report(report, self.dataset, model="judge-test", judge=fake, concurrency=1)
        self.assertEqual(judged["cases"][0]["evidence_origin"], "captured_generation_context")
        self.assertEqual(judged["cases"][0]["semantic"]["faithfulness"]["score"], 1.0)
        self.assertEqual(judged["rubric_versions"], RUBRIC_VERSIONS)
        calibrated = calibrate_report(judged, self.dataset)
        self.assertEqual(calibrated["calibration_version"], "1.2.0")
        self.assertEqual(calibrated["cases"][0]["calibrated_semantic"]["faithfulness"]["score"], 1.0)
        tampered = deepcopy(report)
        tampered["cases"][0]["output"]["generation_evidence"][0]["context_text"] += " conteúdo estranho"
        with patch("app.config.get_settings", return_value=self.settings):
            rejected = judge_report(tampered, self.dataset, model="judge-test", judge=fake)
        self.assertIsNone(rejected["cases"][0]["semantic"]["faithfulness"]["score"])

    def test_publish_task_does_not_return_document_text(self):
        case = self.case
        item = {"input": {"case_id": case["id"], "question": case["question"],
                          "document": case["document"]}}
        with patch("app.services.langfuse_observability.get_settings", return_value=self.settings), patch(
            "app.services.document_registry_service.find_registered_document_by_id",
            return_value={"status": "evaluation", "collection_name": "synthetic", "theme_id": None},
        ), patch("app.graph.manual_graph.answer_question_with_manual_graph", return_value={
            "answer": "Resposta sintética.", "sources": [{"page": 1, "preview": "texto do chunk"}],
        }):
            output = _task_factory(self.dataset, publish=True)(item=item)
        self.assertNotIn("displayed_source_previews", output)
        self.assertNotIn("generation_evidence", output)
        self.assertNotIn("texto do chunk", str(output))

    def test_versioned_summary_has_hashes_without_context_text(self):
        path = Path(__file__).resolve().parents[1] / "app/evaluation/baselines/baseline_3d_summary.json"
        summary = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(summary["dataset_sha256"], self.dataset["sha256"])
        self.assertEqual(len(summary["cases"]), 18)
        self.assertEqual(summary["rubric_versions"]["faithfulness"], "1.2.0")
        self.assertTrue(all(len(item["context_sha256"]) == 64 for item in summary["cases"]))
        self.assertNotIn("context_text", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
