"""Opt-in retrieval trail for synthetic cases; no model or database required."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.evaluation.dataset import document_id, load_dataset
from app.evaluation.evidence_capture import (
    capture_synthetic_context, record_retrieval_stage, record_vector_results,
    retrieval_stages,
)
from app.graph.manual_graph import _apply_grades_to_chunks, _deduplication_key, _retrieve_context_impl, answer_not_found, grade_retrieved_chunks, generate_answer
from app.evaluation.cli import main


class RetrievalDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.document = self.dataset["documents"][0]
        self.doc_id = document_id(self.dataset, self.document["ref"])
        self.case = next(case for case in self.dataset["cases"] if case["document"] == self.document["ref"])
        self.settings = SimpleNamespace(
            max_chunks_to_grade=2, max_answer_context_chunks=1,
            max_answer_context_chars_per_chunk=900,
            enable_batch_relevance_grader=True,
            skip_grader_for_high_confidence_retrieval=False,
            high_confidence_vector_distance_threshold=0.1,
            min_high_confidence_chunks=2,
        )

    def chunk(self, index, distance):
        item = self.document["chunks"][index]
        return {"page": item["page"], "chunk_index": index, "content": item["text"],
                "score": distance, "metadata": {}}

    def test_ranking_deduplication_limits_and_no_text(self):
        first = [self.chunk(0, 0.4), self.chunk(1, 0.2), self.chunk(2, 0.5)]
        second = [self.chunk(1, 0.3), self.chunk(3, 0.6)]
        state = {"question": "q", "search_queries": ["q", "q2"],
                 "document_id": self.doc_id, "k": 4, "max_relevance_score": 1.2}

        def search(document_id, query, k, query_embedding, on_timing):
            result = first if query == "q" else second
            record_vector_results(query, document_id, k, result)
            return result

        with capture_synthetic_context(self.dataset, self.case["id"], self.document["ref"], self.doc_id):
            with patch("app.graph.manual_graph.get_settings", return_value=self.settings), patch(
                "app.graph.manual_graph.search_similar_chunks_pgvector", side_effect=search
            ):
                result, failures = _retrieve_context_impl(state)
            stages = list(retrieval_stages())
        self.assertEqual(failures, 0)
        self.assertEqual(result["retrieved_chunks_count"], 5)
        self.assertEqual(result["deduplicated_chunks_count"], 4)
        self.assertEqual([c["metadata"]["page"] for c in result["chunks"]],
                         [self.document["chunks"][1]["page"], self.document["chunks"][0]["page"]])
        self.assertEqual(result["chunks"][1]["metadata"]["chunk_index"], 0)
        self.assertEqual([s["stage"] for s in stages],
                         ["A_vector_search", "A_vector_search", "B_after_deduplication", "C_grader_candidates"])
        dedup = stages[2]["candidates"]
        self.assertEqual([c["status"] for c in dedup],
                         ["selected", "selected", "selected", "discarded", "selected"])
        self.assertEqual(dedup[0]["chunk_index"], 0)
        self.assertEqual(dedup[3]["discard_reason"], "duplicate_replaced_or_not_better")
        limited = stages[3]["candidates"]
        self.assertEqual([c["status"] for c in limited],
                         ["selected", "selected", "discarded", "discarded"])
        self.assertEqual(limited[2]["discard_reason"], "max_chunks_to_grade")
        self.assertEqual(limited[0]["cosine_distance"], 0.2)
        trail = json.dumps(stages, ensure_ascii=False)
        self.assertNotIn(self.document["chunks"][0]["text"], trail)
        self.assertNotIn('"query":', trail)

    def test_deduplication_key_distinguishes_zero_one_documents_and_missing(self):
        zero = {"document_id": "a", "chunk_index": 0, "page": 1}
        one = {"document_id": "a", "chunk_index": 1, "page": 2}
        missing = {"document_id": "a", "page": 3}
        explicit_none = {"document_id": "a", "chunk_index": None, "page": 3}
        other_document = {"document_id": "b", "chunk_index": 0, "page": 1}
        self.assertEqual(_deduplication_key(zero), ("a", 0))
        self.assertEqual(_deduplication_key(one), ("a", 1))
        self.assertNotEqual(_deduplication_key(zero), _deduplication_key(one))
        self.assertEqual(_deduplication_key(missing), ("a", 3))
        self.assertEqual(_deduplication_key(explicit_none), _deduplication_key(missing))
        self.assertNotEqual(_deduplication_key(zero), _deduplication_key(other_document))

    def test_metadata_fallback_preserves_zero_and_true_duplicate_prefers_lower_distance(self):
        zero = self.chunk(0, 0.6)
        zero.pop("chunk_index")
        zero["metadata"]["chunk_index"] = 0
        improved = self.chunk(0, 0.2)
        one = self.chunk(1, 0.3)
        state = {"question": "q", "search_queries": ["q"], "document_id": self.doc_id,
                 "k": 4, "max_relevance_score": 1.2}
        with patch("app.graph.manual_graph.get_settings", return_value=self.settings), patch(
            "app.graph.manual_graph.search_similar_chunks_pgvector", return_value=[zero, one, improved]
        ):
            result, failures = _retrieve_context_impl(state)
        self.assertEqual(failures, 0)
        self.assertEqual(result["deduplicated_chunks_count"], 2)
        self.assertEqual([chunk["metadata"]["chunk_index"] for chunk in result["chunks"]], [0, 1])
        self.assertEqual([chunk["score"] for chunk in result["chunks"]], [0.2, 0.3])

    def test_grader_selection_and_generation_context_limit_preserve_answer(self):
        chunks = [{"content": item["text"], "metadata": {"page": item["page"],
                   "chunk_index": index, "document_id": self.doc_id}, "score": score}
                  for index, (item, score) in enumerate(zip(self.document["chunks"], [0.1, 0.2, 0.3]))]
        state = {"question": "Como funciona?", "chunks": chunks,
                 "context": "", "has_context": True}
        def fake_grade(base, candidates):
            return _apply_grades_to_chunks(base, candidates, [
                {"chunk_index": 0, "page": candidates[0]["metadata"]["page"], "is_relevant": False},
                {"chunk_index": 1, "page": candidates[1]["metadata"]["page"], "is_relevant": True},
                {"chunk_index": 2, "page": candidates[2]["metadata"]["page"], "is_relevant": True},
            ], fallback_on_failure=True)
        with capture_synthetic_context(self.dataset, self.case["id"], self.document["ref"], self.doc_id):
            with patch("app.graph.manual_graph.get_settings", return_value=self.settings), patch(
                "app.graph.manual_graph._grade_chunks_batch", side_effect=fake_grade
            ):
                graded = grade_retrieved_chunks(state)
                with patch("app.graph.manual_graph.create_chat_model", return_value=object()), patch(
                    "app.graph.manual_graph.invoke_generation", return_value=SimpleNamespace(content="resposta original")
                ):
                    result = generate_answer(graded)
            stages = list(retrieval_stages())
        self.assertEqual(result["answer"], "resposta original")
        self.assertEqual([c["status"] for c in stages[0]["candidates"]],
                         ["discarded", "selected", "selected"])
        self.assertEqual(stages[0]["candidates"][0]["discard_reason"], "grader_marked_not_relevant")
        self.assertEqual([c["status"] for c in stages[1]["candidates"]],
                         ["selected", "discarded"])
        self.assertEqual(stages[1]["candidates"][1]["discard_reason"], "max_answer_context_chunks")

    def test_inactive_collector_cannot_capture_production(self):
        self.assertIsNone(retrieval_stages())
        record_vector_results("pergunta privada", self.doc_id, 4, [self.chunk(0, 0.1)])
        record_retrieval_stage("A_vector_search", [self.chunk(0, 0.1)])
        self.assertIsNone(retrieval_stages())

    def test_no_context_route_records_empty_final_selection(self):
        with capture_synthetic_context(self.dataset, self.case["id"], self.document["ref"], self.doc_id):
            result = answer_not_found({"chunks": [], "context": "", "has_context": False})
            stages = list(retrieval_stages())
        self.assertIn("Nao encontrei informacoes", result["answer"])
        self.assertEqual(stages[0]["stage"], "E_final_context_selection")
        self.assertEqual(stages[0]["candidates"], [])

    def test_cli_selects_only_explicit_cases_and_rejects_publication(self):
        fake_report = {"run_name": "test", "published": False, "summary": {"cases": 2},
                       "experiment_url": None}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with patch("app.evaluation.runner.run_evaluation", return_value=fake_report) as run:
                self.assertEqual(main(["run", "--case-id", "aur-05", "--case-id", "bor-06",
                                       "--capture-context", "--diagnose-retrieval", "--report", str(path)]), 0)
                self.assertEqual(run.call_args.kwargs["case_ids"], ["aur-05", "bor-06"])
                self.assertTrue(run.call_args.kwargs["diagnose_retrieval"])
                self.assertFalse(run.call_args.kwargs["publish"])
                self.assertTrue(path.exists())
            with self.assertRaises(SystemExit):
                main(["run", "--publish", "--capture-context", "--diagnose-retrieval"])


if __name__ == "__main__":
    unittest.main()
