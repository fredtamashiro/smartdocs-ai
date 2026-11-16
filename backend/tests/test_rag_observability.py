"""Exercise child observations without an exporter, database, or LLM connection."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from app.api.routes import chat
from app.graph import manual_graph
from app.schemas.chat import ChatRequest
from app.services import langfuse_observability as telemetry
from app.services import pgvector_search_service as vector_search


class RecordingObservation:
    def __init__(self, client, fields):
        self.client = client
        self.fields = fields
        self.parent = client.stack[-1] if client.stack else None
        self.updates = []
        self.closed = False

    def __enter__(self):
        self.client.stack.append(self.fields["name"])
        return self

    def __exit__(self, *_):
        self.closed = True
        self.client.stack.pop()

    def update(self, **fields):
        self.updates.append(fields)


class RecordingClient:
    def __init__(self):
        self.stack = []
        self.observations = []

    def start_as_current_observation(self, **fields):
        observation = RecordingObservation(self, fields)
        self.observations.append(observation)
        return observation


class GenerationModel:
    model_name = "configured-model"

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def invoke(self, prompt):
        if self.error:
            raise self.error
        return self.response


class RagObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.client = RecordingClient()
        self.settings = SimpleNamespace(
            langfuse_tracing_enabled=True, langfuse_public_key="test-public",
            langfuse_secret_key="test-secret", app_env="test",
        )

    def test_hierarchy_retrieval_distances_and_generation_usage(self):
        chunk = {"score": 0.12, "content": "private chunk", "metadata": {}}
        state = {"question": "private question", "search_queries": ["private question"], "k": 4}
        result = {**state, "chunks": [chunk], "retrieved_chunks_count": 1,
                  "deduplicated_chunks_count": 1, "has_context": True}

        def retrieve_impl(_):
            vector_search.search_similar_chunks_pgvector("private document", "private question", 4)
            return result, 0

        response = SimpleNamespace(
            content="private answer",
            usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
                            "input_token_details": {"cache_read": 30},
                            "output_token_details": {"reasoning": 5}},
            response_metadata={"model_name": "actual-model"},
        )
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=self.client
        ), patch.object(manual_graph, "_retrieve_context_impl", side_effect=retrieve_impl), patch.object(
            vector_search, "_search_similar_chunks_pgvector_impl", return_value=[chunk]
        ):
            with telemetry.observe_query("correlation", 16, "0.1.0") as root:
                self.assertIs(manual_graph.retrieve_context(state), result)
                self.assertIs(telemetry.invoke_generation(
                    GenerationModel(response), "private prompt", name="smartdocs.rag.generate_answer",
                    prompt_id="answer.v1",
                ), response)
                telemetry.finish_query(root, 0, "success", len(response.content))

        root, retrieve, vector, generation = self.client.observations
        self.assertEqual([item.parent for item in self.client.observations],
                         [None, "smartdocs.rag.query", "smartdocs.rag.retrieve", "smartdocs.rag.query"])
        self.assertTrue(all(item.closed for item in self.client.observations))
        self.assertEqual(vector.updates[0]["metadata"]["cosine_distances"], [0.12])
        self.assertEqual(vector.fields["metadata"]["score_kind"], "cosine_distance")
        self.assertEqual(retrieve.updates[0]["metadata"]["retrieved_chunks_count"], 1)
        self.assertEqual(generation.fields["as_type"], "generation")
        self.assertEqual(generation.updates[0]["model"], "actual-model")
        self.assertEqual(generation.updates[0]["usage_details"], {"input": 100, "output": 20, "total": 120})
        self.assertEqual(generation.fields["metadata"]["prompt_id"], "answer.v1")
        self.assertNotIn("private", str([(item.fields, item.updates) for item in self.client.observations]))

    def test_empty_retrieval_and_provider_error(self):
        state = {"question": "private question", "search_queries": [], "k": 4}
        result = {**state, "chunks": [], "retrieved_chunks_count": 0,
                  "deduplicated_chunks_count": 0, "has_context": False}
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=self.client
        ), patch.object(manual_graph, "_retrieve_context_impl", return_value=(result, 1)):
            with telemetry.observe_query("correlation", 16, "0.1.0"):
                self.assertIs(manual_graph.retrieve_context(state), result)
                with self.assertRaisesRegex(RuntimeError, "private failure"):
                    telemetry.invoke_generation(GenerationModel(error=RuntimeError("private failure")),
                                                "private prompt", name="smartdocs.rag.classify_batch",
                                                prompt_id="relevance_batch.v1")
        _, retrieve, generation = self.client.observations
        self.assertEqual(retrieve.updates[0]["metadata"]["vector_search_failures"], 1)
        self.assertIsNone(retrieve.updates[0]["metadata"]["best_cosine_distance"])
        self.assertEqual(generation.updates[0]["metadata"]["error_category"], "llm_provider")
        self.assertEqual(generation.updates[0]["level"], "ERROR")
        self.assertTrue(generation.closed)
        self.assertNotIn("private failure", str(generation.updates))

    def test_provider_usage_fallback_and_missing_data(self):
        response = SimpleNamespace(usage_metadata=None, response_metadata={
            "token_usage": {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11,
                            "prompt_tokens_details": {"cached_tokens": 2}}})
        self.assertEqual(telemetry.provider_usage(response), {"input": 8, "output": 3, "total": 11})
        self.assertEqual(telemetry.provider_usage(SimpleNamespace()), {})

    def test_evaluation_collector_uses_provider_counts_without_export(self):
        self.settings.langfuse_tracing_enabled = False
        response = SimpleNamespace(content="synthetic", usage_metadata={
            "input_tokens": 10, "output_tokens": 4, "total_tokens": 14,
            "input_token_details": {"cache_read": 2},
        }, response_metadata={"model_name": "actual-model"})
        with patch.object(telemetry, "get_settings", return_value=self.settings):
            with telemetry.collect_generation_usage() as generations:
                telemetry.invoke_generation(GenerationModel(response), "synthetic prompt",
                                            name="smartdocs.rag.generate_answer", prompt_id="answer.v1")
        self.assertEqual(generations, [{"name": "smartdocs.rag.generate_answer",
                                        "model": "actual-model",
                                        "usage": {"input": 10, "output": 4, "total": 14}}])

    def test_interrupted_generation_closes_child_and_marks_failure(self):
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=self.client
        ):
            with telemetry.observe_query("correlation", 16, "0.1.0"):
                with self.assertRaises(KeyboardInterrupt):
                    telemetry.invoke_generation(GenerationModel(error=KeyboardInterrupt()),
                                                "private prompt", name="smartdocs.rag.generate_answer",
                                                prompt_id="answer.v1")
        generation = self.client.observations[-1]
        self.assertTrue(generation.closed)
        self.assertEqual(generation.updates[0]["metadata"]["error_category"], "interrupted")

    def test_vector_database_error_is_categorized_and_raised(self):
        error = OperationalError("SELECT", {}, Exception("private database detail"))
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=self.client
        ), patch.object(vector_search, "_search_similar_chunks_pgvector_impl", side_effect=error):
            with telemetry.observe_query("correlation", 16, "0.1.0"):
                with self.assertRaises(OperationalError):
                    vector_search.search_similar_chunks_pgvector("private document", "private query", 4)
        vector = self.client.observations[-1]
        self.assertEqual(vector.updates[0]["metadata"]["error_category"], "vector_database")
        self.assertTrue(vector.closed)
        self.assertNotIn("private", str((vector.fields, vector.updates)))

    def test_retrieval_without_document_has_no_search_or_generation(self):
        self.settings.max_chunks_to_grade = 3
        state = {"question": "private question", "search_queries": ["private question"],
                 "k": 4, "document_id": None, "max_relevance_score": 1.2}
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=self.client
        ):
            with telemetry.observe_query("correlation", 16, "0.1.0"):
                result = manual_graph.retrieve_context(state)
                self.assertEqual(manual_graph.should_generate_answer(result), "answer_not_found")
        self.assertEqual([item.fields["name"] for item in self.client.observations],
                         ["smartdocs.rag.query", "smartdocs.rag.retrieve"])
        self.assertEqual(result["retrieved_chunks_count"], 0)

    def test_cached_answer_keeps_api_response_without_llm_generation(self):
        self.settings.chat_answer_cache_enabled = True
        self.settings.chat_answer_cache_semantic_enabled = False
        request = SimpleNamespace(app=SimpleNamespace(version="0.1.0"),
                                  client=SimpleNamespace(host="test"))
        payload = ChatRequest(document_id="private document", question="private question")
        cached = {"id": "cache-id", "question": "private question",
                  "answer": "private answer", "sources": []}
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=self.client
        ), patch.object(chat, "get_settings", return_value=self.settings), patch.object(
            chat, "check_chat_rate_limit", return_value={"allowed": True}
        ), patch.object(chat, "validate_question_safety", return_value={
            "allowed": True, "sanitized_question": "private question"
        }), patch.object(chat, "find_exact_cached_answer", return_value=cached), patch.object(
            chat, "mark_cache_hit"
        ), patch.object(chat, "create_usage_log"), patch.object(
            chat, "answer_question_with_manual_graph"
        ) as graph:
            response = chat.ask_question(request, payload)
        self.assertEqual(response.answer, "private answer")
        self.assertEqual(response.sources, [])
        graph.assert_not_called()
        self.assertEqual([item.fields["name"] for item in self.client.observations],
                         ["smartdocs.rag.query"])

    def test_disabled_does_not_create_children(self):
        self.settings.langfuse_tracing_enabled = False
        response = SimpleNamespace(content="private answer", usage_metadata=None, response_metadata={})
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=self.client
        ):
            self.assertIs(telemetry.invoke_generation(GenerationModel(response), "private prompt",
                                                      name="smartdocs.rag.generate_answer", prompt_id="answer.v1"), response)
        self.assertEqual(self.client.observations, [])


if __name__ == "__main__":
    unittest.main()
