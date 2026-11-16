"""No model, database, or Cloud connection is used by these tests."""

import json
import os
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.evaluation.cli import compare_reports, rescore_report
from app.evaluation.dataset import cloud_dataset_name, cloud_item_id, document_id, load_dataset
from app.evaluation.metrics import check_case, summarize
from app.evaluation.runner import _aggregate_provider_usage, _task_factory, prepare_cloud_dataset, run_evaluation
from app.services import langfuse_observability as telemetry


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()

    def test_fixture_has_stable_ids_and_required_categories(self):
        self.assertEqual(len(self.dataset["cases"]), 18)
        self.assertEqual(len(self.dataset["documents"]), 2)
        self.assertEqual({case["category"] for case in self.dataset["cases"]},
                         {"factual", "distributed", "multi_chunk", "absent", "ambiguous", "citation"})
        self.assertEqual(document_id(self.dataset, "estacao_aurora"),
                         document_id(load_dataset(), "estacao_aurora"))
        self.assertEqual(cloud_item_id(self.dataset, "aur-01"), cloud_item_id(load_dataset(), "aur-01"))

    def test_metrics_are_lexical_checks_not_factual_judgment(self):
        case = next(case for case in self.dataset["cases"] if case["id"] == "aur-08")
        output = {"answer": "Limpe a cada 14 dias sem água (p. 5).", "latency_ms": 25,
                  "reported_tokens": {"input": 10, "output": 5, "total": 15},
                  "usage_complete": True, "reported_cost_usd": None}
        metrics = check_case(case, output)
        self.assertTrue(metrics["execution_success"])
        self.assertTrue(metrics["citation_pass"])
        self.assertEqual(metrics["fact_coverage_lexical"], 1.0)
        self.assertEqual(metrics["reported_tokens"]["total"], 15)
        self.assertEqual(summarize([{"metrics": metrics}])["citation_pass_rate"], 1.0)
        output["answer"] = "Limpe a cada 14 dias sem água."
        self.assertFalse(check_case(case, output)["citation_pass"])
        autonomy = next(case for case in self.dataset["cases"] if case["id"] == "aur-03")
        self.assertEqual(check_case(autonomy, {"answer": "18 horas"})["fact_coverage_lexical"], 0.0)

    def test_abstention_and_failure_metrics(self):
        case = next(case for case in self.dataset["cases"] if case["id"] == "aur-06")
        self.assertTrue(check_case(case, {"answer": "Não encontrei informações suficientes."})["abstention_pass"])
        self.assertTrue(check_case(case, {"answer": "Não há informação sobre Bluetooth no manual."})["abstention_pass"])
        self.assertTrue(check_case(case, {"answer": "Isso não está presente no contexto fornecido."})["abstention_pass"])
        self.assertFalse(check_case(case, {"answer": "Bluetooth 5.0"})["abstention_pass"])
        failed = check_case(case, {"answer": "", "error_type": "RuntimeError"})
        self.assertFalse(failed["execution_success"])
        self.assertFalse(failed["abstention_pass"])

    def test_cloud_preparation_reuses_stable_items(self):
        case = self.dataset["cases"][0]
        client = MagicMock()
        remote_items = {}
        client.get_dataset.return_value = SimpleNamespace(items=[])

        def create_item(**kwargs):
            remote_items[kwargs["id"]] = SimpleNamespace(id=kwargs["id"], input=kwargs["input"],
                                                          expected_output=kwargs["expected_output"],
                                                          metadata=kwargs["metadata"])
            client.get_dataset.return_value = SimpleNamespace(items=list(remote_items.values()))

        client.create_dataset_item.side_effect = create_item
        selected = prepare_cloud_dataset(client, self.dataset, [case])
        self.assertEqual(selected[0].id, cloud_item_id(self.dataset, case["id"]))
        prepare_cloud_dataset(client, self.dataset, [case])
        client.create_dataset_item.assert_called_once()
        self.assertEqual(client.create_dataset.call_args.kwargs["name"], cloud_dataset_name(self.dataset))

    def test_task_reuses_graph_and_masks_errors(self):
        case = self.dataset["cases"][0]
        item = {"input": {"case_id": case["id"], "question": case["question"], "document": case["document"]}}
        settings = SimpleNamespace(langfuse_tracing_enabled=False, langfuse_public_key="", langfuse_secret_key="")
        with patch.object(telemetry, "get_settings", return_value=settings), patch(
            "app.services.document_registry_service.find_registered_document_by_id",
            return_value={"status": "evaluation", "collection_name": "synthetic", "theme_id": None},
        ), patch("app.graph.manual_graph.answer_question_with_manual_graph", return_value={
            "answer": "Resposta sintética (p. 1).", "sources": [{"page": 1,
                "chunk_index": 0, "preview": "Trecho sintético."}],
        }) as graph:
            task = _task_factory(self.dataset)
            output = task(item=item)
            self.assertEqual(output["answer"], "Resposta sintética (p. 1).")
            self.assertEqual(output["source_pages"], [1])
            self.assertEqual(output["displayed_source_previews"], [{"page": 1, "chunk_index": 0,
                                                              "text": "Trecho sintético."}])
            self.assertIsNone(output["reported_tokens"])
            graph.assert_called_once()
        with patch.object(telemetry, "get_settings", return_value=settings), patch(
            "app.services.document_registry_service.find_registered_document_by_id",
            side_effect=RuntimeError("private error detail"),
        ):
            output = _task_factory(self.dataset)(item=item)
            self.assertEqual(output["error_type"], "RuntimeError")
            self.assertNotIn("private error detail", json.dumps(output))

    def test_comparison_rejects_different_dataset_versions(self):
        base = {"dataset": "synthetic", "dataset_sha256": "a", "run_name": "first",
                "summary": {"execution_success_rate": 0.5}}
        other = deepcopy(base)
        other["run_name"] = "second"
        other["summary"]["execution_success_rate"] = 1.0
        self.assertEqual(compare_reports(base, other)["changes"]["execution_success_rate"]["delta"], 0.5)
        other["dataset_sha256"] = "b"
        with self.assertRaises(ValueError):
            compare_reports(base, other)
        other["dataset_sha256"] = "a"
        other["metrics_version"] = "different"
        with self.assertRaises(ValueError):
            compare_reports(base, other)

    def test_rescore_uses_saved_output_and_same_dataset(self):
        case = next(case for case in self.dataset["cases"] if case["id"] == "aur-06")
        report = {"dataset_sha256": self.dataset["sha256"], "summary": {}, "cases": [
            {"case_id": case["id"], "output": {"answer": "Não há informação sobre Bluetooth."},
             "metrics": {"abstention_pass": False}},
        ]}
        rescored = rescore_report(report, self.dataset)
        self.assertTrue(rescored["cases"][0]["metrics"]["abstention_pass"])
        self.assertEqual(rescored["summary"]["abstention_pass_rate"], 1.0)
        self.assertFalse(report["cases"][0]["metrics"]["abstention_pass"])
        with self.assertRaises(ValueError):
            rescore_report({**report, "dataset_sha256": "other"}, self.dataset)

    def test_provider_usage_does_not_invent_missing_tokens(self):
        usage, complete = _aggregate_provider_usage([
            {"usage": {"input": 10, "output": 5, "total": 15}},
            {"usage": {"input": 3}},
        ])
        self.assertEqual(usage, {"input": 13, "output": None, "total": None})
        self.assertFalse(complete)
        self.assertEqual(_aggregate_provider_usage([]), (None, None))

    def test_local_runner_uses_real_sdk_without_publishing(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test", "APP_ENV": "test",
                                  "LANGFUSE_TRACING_ENABLED": "true"}), patch(
            "app.evaluation.prepare.assert_prepared"
        ), patch("app.services.document_registry_service.find_registered_document_by_id",
                 return_value={"status": "evaluation", "collection_name": "synthetic", "theme_id": None}), patch(
            "app.graph.manual_graph.answer_question_with_manual_graph",
            return_value={"answer": "Resposta sintética (p. 1).", "sources": [{"page": 1}]},
        ):
            report = run_evaluation(self.dataset, publish=False, run_name="offline-test", limit=1)
            self.assertEqual(os.environ["LANGFUSE_TRACING_ENABLED"], "true")
        self.assertFalse(report["published"])
        self.assertIsNone(report["experiment_url"])
        self.assertIsNone(report["cases"][0]["trace_id"])
        self.assertEqual(report["summary"]["execution_success_rate"], 1.0)

    def test_local_runner_restores_tracing_after_preflight_failure(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test", "APP_ENV": "test",
                                  "LANGFUSE_TRACING_ENABLED": "true"}), patch(
            "app.evaluation.prepare.assert_prepared", side_effect=RuntimeError("missing fixture")
        ):
            with self.assertRaises(RuntimeError):
                run_evaluation(self.dataset, publish=False, limit=1)
            self.assertEqual(os.environ["LANGFUSE_TRACING_ENABLED"], "true")

    def test_publish_path_links_trace_without_real_cloud_connection(self):
        case = self.dataset["cases"][0]
        item = {"input": {"case_id": case["id"], "question": case["question"],
                          "document": case["document"]}}
        client = MagicMock()
        client.run_experiment.return_value = SimpleNamespace(
            item_results=[SimpleNamespace(item=item, output={"answer": "3 segundos",
                "error_type": None, "latency_ms": 5, "reported_tokens": None,
                "usage_complete": None, "reported_cost_usd": None}, trace_id="a" * 32)],
            experiment_id="experiment-test", experiment_url="https://example.invalid/experiment-test",
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test", "APP_ENV": "test",
                                  "LANGFUSE_TRACING_ENABLED": "true", "LANGFUSE_PUBLIC_KEY": "test",
                                  "LANGFUSE_SECRET_KEY": "test", "LANGFUSE_SAMPLE_RATE": "1.0"}), patch(
            "app.evaluation.prepare.assert_prepared"
        ), patch.object(telemetry, "_client", return_value=client), patch(
            "app.evaluation.runner.prepare_cloud_dataset", return_value=[item]
        ):
            report = run_evaluation(self.dataset, publish=True, run_name="cloud-test", limit=1)
        self.assertTrue(report["published"])
        self.assertEqual(report["cases"][0]["trace_id"], "a" * 32)
        self.assertEqual(report["experiment_id"], "experiment-test")
        client.run_experiment.assert_called_once()
        client.flush.assert_called_once()

    def test_text_capture_cannot_be_published(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test", "APP_ENV": "test",
                                  "LANGFUSE_TRACING_ENABLED": "true"}):
            with self.assertRaisesRegex(ValueError, "Captura textual"):
                run_evaluation(self.dataset, publish=True, capture_context=True, limit=1)


if __name__ == "__main__":
    unittest.main()
