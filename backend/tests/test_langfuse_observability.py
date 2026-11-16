"""Telemetry tests need no external services or credentials."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.routes import chat
from app.config import Settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import langfuse_observability as telemetry


class ObservationTests(unittest.TestCase):
    def setUp(self):
        telemetry._client.cache_clear()
        self.settings = SimpleNamespace(
            langfuse_tracing_enabled=True, langfuse_public_key="test-public",
            langfuse_secret_key="test-secret", langfuse_base_url="https://cloud.langfuse.com",
            langfuse_sample_rate=1.0, app_env="test",
        )
        self.request = SimpleNamespace(app=SimpleNamespace(version="0.1.0"))
        self.payload = ChatRequest(document_id="document", question="private question")
        self.response = ChatResponse(question="private question", answer="private answer", sources=[])

    def _client_mock(self):
        client = MagicMock()
        client.start_as_current_observation.return_value.__enter__.return_value = MagicMock()
        return client

    def test_disabled_preserves_response_without_client(self):
        self.settings.langfuse_tracing_enabled = False
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client"
        ) as client, patch.object(chat, "_ask_question_impl", return_value=self.response):
            self.assertIs(chat.ask_question(self.request, self.payload), self.response)
            client.assert_not_called()

    def test_missing_credentials_keeps_integration_disabled(self):
        self.settings.langfuse_secret_key = ""
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client"
        ) as client, patch.object(chat, "_ask_question_impl", return_value=self.response):
            self.assertIs(chat.ask_question(self.request, self.payload), self.response)
            client.assert_not_called()

    def test_settings_defaults_and_sample_rate_validation(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None, openai_api_key="test")
            self.assertFalse(settings.langfuse_tracing_enabled)
            self.assertEqual(settings.langfuse_sample_rate, 1.0)
            with self.assertRaises(ValidationError):
                Settings(_env_file=None, openai_api_key="test", langfuse_sample_rate=1.5)

    def test_installed_sdk_exports_explicit_root_and_child_without_network(self):
        # A stale Docker image without langfuse must fail this test rather than
        # passing solely through the mocked client tests.
        from importlib.metadata import version

        from langfuse import Langfuse
        from langfuse.span_filter import is_langfuse_span
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        self.assertEqual(version("langfuse"), "5.2.0")
        exporter = InMemorySpanExporter()
        client = Langfuse(
            public_key="pk-lf-smartdocs-runtime-test",
            secret_key="sk-lf-smartdocs-runtime-test",
            base_url="https://invalid.local",
            tracer_provider=TracerProvider(),
            span_exporter=exporter,
            should_export_span=is_langfuse_span,
        )
        with client.start_as_current_observation(name="smartdocs.rag.query"):
            with client.start_as_current_observation(name="smartdocs.rag.retrieve"):
                pass
        client.flush()
        spans = exporter.get_finished_spans()
        self.assertEqual([span.name for span in spans], ["smartdocs.rag.retrieve", "smartdocs.rag.query"])
        self.assertEqual(spans[0].parent.span_id, spans[1].context.span_id)
        client.shutdown()

    def test_enabled_creates_root_once_per_query_without_content(self):
        client = self._client_mock()
        sdk = SimpleNamespace(Langfuse=MagicMock(return_value=client))
        span_filter = SimpleNamespace(is_langfuse_span=MagicMock())
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.dict(
            sys.modules, {"langfuse": sdk, "langfuse.span_filter": span_filter}
        ), patch.object(chat, "_ask_question_impl", return_value=self.response):
            self.assertIs(chat.ask_question(self.request, self.payload), self.response)
            self.assertIs(chat.ask_question(self.request, self.payload), self.response)
        sdk.Langfuse.assert_called_once_with(
            public_key="test-public", secret_key="test-secret",
            base_url="https://cloud.langfuse.com", sample_rate=1.0,
            should_export_span=span_filter.is_langfuse_span,
        )
        self.assertEqual(client.start_as_current_observation.call_count, 2)
        self.assertEqual(client.start_as_current_observation.return_value.__exit__.call_count, 2)
        for call in client.start_as_current_observation.call_args_list:
            self.assertEqual(call.kwargs["name"], telemetry.OPERATION)
            self.assertEqual(call.kwargs["metadata"]["question_chars"], len(self.payload.question))
            self.assertNotIn("private question", str(call))
        updates = client.start_as_current_observation.return_value.__enter__.return_value.update.call_args_list
        for call in updates:
            self.assertEqual(call.kwargs["metadata"]["status"], "success")
            self.assertEqual(call.kwargs["metadata"]["answer_chars"], len(self.response.answer))
            self.assertNotIn("private answer", str(call))

    def test_error_closes_root_without_exception_message(self):
        client = self._client_mock()
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=client
        ), patch.object(chat, "_ask_question_impl", side_effect=HTTPException(400, "private question")):
            with self.assertRaises(HTTPException):
                chat.ask_question(self.request, self.payload)
        client.start_as_current_observation.return_value.__exit__.assert_called_once_with(None, None, None)
        update = client.start_as_current_observation.return_value.__enter__.return_value.update
        self.assertEqual(update.call_args.kwargs["metadata"]["status"], "failure")
        self.assertNotIn("private question", str(update.call_args))

    def test_interrupted_query_closes_root(self):
        client = self._client_mock()
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=client
        ), patch.object(chat, "_ask_question_impl", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                chat.ask_question(self.request, self.payload)
        client.start_as_current_observation.return_value.__exit__.assert_called_once_with(None, None, None)
        update = client.start_as_current_observation.return_value.__enter__.return_value.update
        self.assertEqual(update.call_args.kwargs["metadata"]["status"], "failure")

    def test_export_failure_preserves_response(self):
        client = self._client_mock()
        client.start_as_current_observation.return_value.__exit__.side_effect = RuntimeError("export failed")
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=client
        ), patch.object(chat, "_ask_question_impl", return_value=self.response):
            self.assertIs(chat.ask_question(self.request, self.payload), self.response)

    def test_start_and_update_failures_preserve_response(self):
        client = self._client_mock()
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", return_value=client
        ), patch.object(chat, "_ask_question_impl", return_value=self.response):
            client.start_as_current_observation.side_effect = RuntimeError("start failed")
            self.assertIs(chat.ask_question(self.request, self.payload), self.response)
            client.start_as_current_observation.side_effect = None
            client.start_as_current_observation.return_value.__enter__.return_value.update.side_effect = RuntimeError("update failed")
            self.assertIs(chat.ask_question(self.request, self.payload), self.response)

    def test_initialization_error_logs_type_without_secret_details(self):
        with patch.object(telemetry, "get_settings", return_value=self.settings), patch.object(
            telemetry, "_client", side_effect=ModuleNotFoundError("private credential detail")
        ), patch.object(chat, "_ask_question_impl", return_value=self.response):
            with self.assertLogs(telemetry.logger, level="WARNING") as captured:
                self.assertIs(chat.ask_question(self.request, self.payload), self.response)
        self.assertIn("ModuleNotFoundError", captured.output[0])
        self.assertNotIn("private credential detail", captured.output[0])


if __name__ == "__main__":
    unittest.main()
