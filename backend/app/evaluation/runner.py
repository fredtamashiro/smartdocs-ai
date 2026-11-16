"""Run the production RAG graph on synthetic fixtures, with optional Cloud publication."""

import os
from contextlib import nullcontext
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from app.evaluation.dataset import cloud_dataset_name, cloud_item_id, document_id
from app.evaluation.metrics import METRICS_VERSION, check_case, summarize


def _item_input(item) -> dict:
    return item["input"] if isinstance(item, dict) else item.input


def _aggregate_provider_usage(generations: list[dict]) -> tuple[dict | None, bool | None]:
    if not generations:
        return None, None
    fields = ("input", "output", "total")
    totals = {field: sum(entry["usage"][field] for entry in generations)
              if all(field in entry["usage"] for entry in generations) else None
              for field in fields}
    return totals, all(value is not None for value in totals.values())


def prepare_cloud_dataset(client, dataset: dict, cases: list[dict]) -> list:
    """Upsert only changed synthetic items by stable ID; return exact items to run."""
    name = cloud_dataset_name(dataset)
    client.create_dataset(name=name, description="SmartDocs synthetic RAG evaluation",
                          metadata={"version": dataset["version"], "sha256": dataset["sha256"]})
    existing = {item.id: item for item in client.get_dataset(name).items}
    for case in cases:
        item_id = cloud_item_id(dataset, case["id"])
        input_data = {"case_id": case["id"], "question": case["question"], "document": case["document"]}
        metadata = {"category": case["category"], "version": dataset["version"]}
        current = existing.get(item_id)
        if current and current.input == input_data and current.expected_output == case["expected"] and current.metadata == metadata:
            continue
        client.create_dataset_item(dataset_name=name, id=item_id, input=input_data,
                                   expected_output=case["expected"], metadata=metadata)
    refreshed = {item.id: item for item in client.get_dataset(name).items}
    selected = []
    for case in cases:
        item = refreshed[cloud_item_id(dataset, case["id"])]
        if (_item_input(item) != {"case_id": case["id"], "question": case["question"], "document": case["document"]}
                or item.expected_output != case["expected"]
                or item.metadata != {"category": case["category"], "version": dataset["version"]}):
            raise RuntimeError("Item remoto divergente do dataset sintético versionado")
        selected.append(item)
    return selected


def _task_factory(dataset: dict, *, capture_context: bool = False, publish: bool = False,
                  diagnose_retrieval: bool = False):
    from app.graph.manual_graph import answer_question_with_manual_graph
    from app.services.document_registry_service import find_registered_document_by_id
    from app.services.langfuse_observability import collect_generation_usage, finish_query, observe_query
    from app.services.query_strategy_service import extract_document_search_terms
    from app.evaluation.evidence_capture import capture_synthetic_context, retrieval_stages

    def task(*, item, **_kwargs) -> dict:
        payload = _item_input(item)
        question = payload["question"]
        doc_id = document_id(dataset, payload["document"])
        started_at = perf_counter()
        generation_evidence = []
        diagnostics = []
        with collect_generation_usage() as generations:
            with observe_query(str(uuid4()), len(question), f"eval/{dataset['version']}") as root:
                try:
                    document = find_registered_document_by_id(doc_id)
                    if not document or document["status"] != "evaluation":
                        raise RuntimeError("Documento sintético não preparado")
                    capture = (capture_synthetic_context(dataset, payload["case_id"], payload["document"], doc_id)
                               if capture_context else nullcontext(generation_evidence))
                    with capture as generation_evidence:
                        try:
                            result = answer_question_with_manual_graph(
                                collection_name=document["collection_name"], question=question,
                                document_id=doc_id, k=4, theme_id=document["theme_id"],
                                document_terms=extract_document_search_terms(document),
                            )
                        finally:
                            if diagnose_retrieval:
                                diagnostics = list(retrieval_stages() or [])
                    answer = result["answer"]
                    pages = sorted({source["page"] for source in result["sources"] if source.get("page") is not None})
                    evidence = [{"page": source.get("page"), "chunk_index": source.get("chunk_index"),
                                 "text": source.get("preview", "")} for source in result["sources"]]
                    finish_query(root, started_at, "success", len(answer))
                    error_type = None
                except Exception as error:
                    answer, pages, evidence, error_type = "", [], [], type(error).__name__
                    finish_query(root, started_at, "failure")

        reported_tokens, usage_complete = _aggregate_provider_usage(generations)
        output = {
            "answer": answer, "source_pages": pages,
            "error_type": error_type,
            "latency_ms": round((perf_counter() - started_at) * 1000),
            "generations": generations, "reported_tokens": reported_tokens,
            "usage_complete": usage_complete,
            "reported_cost_usd": None,
        }
        if not publish:
            output["displayed_source_previews"] = evidence
        if capture_context:
            output["generation_evidence"] = generation_evidence
        if diagnose_retrieval:
            answer_records = [record for record in generation_evidence
                              if record["generation_name"] == "smartdocs.rag.generate_answer"]
            diagnostics.append({"stage": "F_llm_generation_input",
                                "parameters": [{"generation_index": record["generation_index"],
                                                "status": record["status"],
                                                "context_sha256": record.get("context_sha256")}
                                               for record in answer_records],
                                "candidates": [{key: chunk[key] for key in
                                                ("chunk_id", "document_id", "page", "chunk_index", "order")}
                                               for record in answer_records for chunk in record.get("chunks", [])]})
            output["retrieval_diagnostics"] = diagnostics
        return output
    return task


def run_evaluation(dataset: dict, *, publish: bool = False, run_name: str | None = None,
                   limit: int | None = None, capture_context: bool = False,
                   case_ids: list[str] | None = None, diagnose_retrieval: bool = False) -> dict:
    """Use SDK 5.2 Experiment Runner; local mode disables all Langfuse exports."""
    previous_tracing = os.environ.get("LANGFUSE_TRACING_ENABLED")
    if not publish:
        os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
    from app.config import get_settings
    try:
        get_settings.cache_clear()
        settings = get_settings()
        if settings.app_env.lower() not in {"local", "development", "test"}:
            raise ValueError("Avaliação sintética permitida apenas em ambiente local/development/test")
        if publish and capture_context:
            raise ValueError("Captura textual permitida somente em experimentos locais sem publicação")

        if diagnose_retrieval and (not capture_context or publish):
            raise ValueError("Diagnostico exige captura local explicita sem publicacao")
        if case_ids and limit:
            raise ValueError("Use --case-id ou --limit")
        known_ids = {case["id"] for case in dataset["cases"]}
        if case_ids and (len(case_ids) != len(set(case_ids)) or set(case_ids) - known_ids):
            raise ValueError("IDs de caso desconhecidos ou duplicados")

        from app.evaluation.prepare import assert_prepared
        assert_prepared(dataset)
        cases = ([case for case in dataset["cases"] if case["id"] in case_ids] if case_ids
                 else dataset["cases"][:limit] if limit else dataset["cases"])
        if not cases:
            raise ValueError("Nenhum caso selecionado")
        run_name = run_name or f"{dataset['name']}-{dataset['version']}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"

        if publish:
            if not (settings.langfuse_tracing_enabled and settings.langfuse_public_key and settings.langfuse_secret_key):
                raise ValueError("Publicação requer Langfuse habilitado e credenciais")
            if settings.langfuse_sample_rate != 1.0:
                raise ValueError("Publicação requer LANGFUSE_SAMPLE_RATE=1.0 para não perder casos")
            from app.services.langfuse_observability import _client
            client = _client()
            items = prepare_cloud_dataset(client, dataset, cases)
        else:
            from langfuse import Langfuse
            client = Langfuse(public_key="local-evaluation", secret_key="local-evaluation",
                              base_url="https://invalid.local", tracing_enabled=False)
            items = [{"input": {"case_id": case["id"], "question": case["question"], "document": case["document"]},
                      "expected_output": case["expected"], "metadata": {"category": case["category"]}}
                     for case in cases]
    except BaseException:
        if not publish:
            if previous_tracing is None:
                os.environ.pop("LANGFUSE_TRACING_ENABLED", None)
            else:
                os.environ["LANGFUSE_TRACING_ENABLED"] = previous_tracing
            get_settings.cache_clear()
        raise

    try:
        experiment = client.run_experiment(
            name=dataset["name"], run_name=run_name,
            description=f"Synthetic SmartDocs RAG dataset {dataset['version']}",
            data=items, task=_task_factory(dataset, capture_context=capture_context,
                                            publish=publish, diagnose_retrieval=diagnose_retrieval), max_concurrency=1,
            metadata={"dataset_version": dataset["version"], "dataset_sha256": dataset["sha256"]},
        )
        results_by_id = {_item_input(item_result.item)["case_id"]: item_result for item_result in experiment.item_results}
        rows = []
        for case in cases:
            item_result = results_by_id.get(case["id"])
            output = item_result.output if item_result and isinstance(item_result.output, dict) else {
                "answer": "", "error_type": "ExperimentRunnerError", "latency_ms": None,
                "reported_tokens": None, "usage_complete": None, "reported_cost_usd": None,
            }
            trace_id = item_result.trace_id if item_result else None
            if trace_id == "0" * 32:
                trace_id = None
            rows.append({"case_id": case["id"], "document": case["document"],
                         "category": case["category"], "question": case["question"],
                         "expected": case["expected"], "output": output,
                         "metrics": check_case(case, output), "trace_id": trace_id})
        return {
            "dataset": cloud_dataset_name(dataset), "dataset_version": dataset["version"],
            "dataset_sha256": dataset["sha256"], "metrics_version": METRICS_VERSION,
            "context_capture_enabled": capture_context,
            "retrieval_diagnostics_enabled": diagnose_retrieval,
            "run_name": run_name,
            "published": publish, "experiment_id": experiment.experiment_id if publish else None,
            "experiment_url": experiment.experiment_url if publish else None,
            "model_configured": settings.openai_chat_model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "summary": summarize(rows), "cases": rows,
        }
    finally:
        if publish:
            client.flush()  # short-lived CLI only
        else:
            client.shutdown()
            if previous_tracing is None:
                os.environ.pop("LANGFUSE_TRACING_ENABLED", None)
            else:
                os.environ["LANGFUSE_TRACING_ENABLED"] = previous_tracing
            get_settings.cache_clear()
