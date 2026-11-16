"""Optional, content-free Langfuse observation for chat requests."""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from time import perf_counter
from typing import Iterator

from app.config import get_settings

logger = logging.getLogger(__name__)
OPERATION = "smartdocs.rag.query"
_generation_collector: ContextVar[list[dict] | None] = ContextVar("smartdocs_generation_collector", default=None)


@contextmanager
def collect_generation_usage() -> Iterator[list[dict]]:
    """Collect provider-reported usage for an explicit evaluation run only."""
    records: list[dict] = []
    token = _generation_collector.set(records)
    try:
        yield records
    finally:
        _generation_collector.reset(token)


@lru_cache(maxsize=1)
def _client():
    # Settings reads backend/.env too; get_client() only reads process environment.
    from langfuse import Langfuse
    from langfuse.span_filter import is_langfuse_span

    settings = get_settings()
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
        sample_rate=settings.langfuse_sample_rate,
        should_export_span=is_langfuse_span,
    )


@contextmanager
def observe_query(correlation_id: str, question_length: int, version: str) -> Iterator[object | None]:
    settings = get_settings()
    if not (settings.langfuse_tracing_enabled and settings.langfuse_public_key and settings.langfuse_secret_key):
        yield None
        return

    try:
        manager = _client().start_as_current_observation(
            as_type="span",
            name=OPERATION,
            metadata={
                "correlation_id": correlation_id,
                "operation": OPERATION,
                "environment": settings.app_env,
                "question_chars": question_length,
                "status": "running",
            },
            version=version,
        )
        observation = manager.__enter__()
    except Exception as error:
        logger.warning("Falha ao iniciar observacao Langfuse: %s", type(error).__name__)
        yield None
        return

    try:
        yield observation
    finally:
        # Close without passing the business exception: the SDK must not export
        # its message, which can contain a prompt or document text.
        try:
            manager.__exit__(None, None, None)
        except Exception as error:
            logger.warning("Falha ao finalizar observacao Langfuse: %s", type(error).__name__)


def finish_query(observation: object | None, started_at: float, status: str, answer_length: int = 0) -> None:
    if observation is None:
        return
    try:
        observation.update(metadata={
            "status": status,
            "duration_ms": round((perf_counter() - started_at) * 1000),
            "answer_chars": answer_length,
        }, level="ERROR" if status == "failure" else "DEFAULT")
    except Exception as error:
        logger.warning("Falha ao atualizar observacao Langfuse: %s", type(error).__name__)


@contextmanager
def observe_step(name: str, *, as_type: str = "span", metadata: dict | None = None, model: str | None = None) -> Iterator[object | None]:
    """Create a child only while tracing is enabled; never export business exceptions."""
    settings = get_settings()
    if not (settings.langfuse_tracing_enabled and settings.langfuse_public_key and settings.langfuse_secret_key):
        yield None
        return

    try:
        kwargs = {"name": name, "as_type": as_type, "metadata": metadata or {}}
        if model:
            kwargs["model"] = model
        manager = _client().start_as_current_observation(**kwargs)
        observation = manager.__enter__()
    except Exception as error:
        logger.warning("Falha ao iniciar observacao filha Langfuse: %s", type(error).__name__)
        yield None
        return

    try:
        yield observation
    finally:
        try:
            manager.__exit__(None, None, None)
        except Exception as error:
            logger.warning("Falha ao finalizar observacao filha Langfuse: %s", type(error).__name__)


def finish_step(observation: object | None, started_at: float, status: str, *, metadata: dict | None = None, model: str | None = None, usage: dict | None = None) -> None:
    if observation is None:
        return
    try:
        fields = {"metadata": {"status": status, "duration_ms": round((perf_counter() - started_at) * 1000), **(metadata or {})}, "level": "ERROR" if status == "failure" else "DEFAULT"}
        if model:
            fields["model"] = model
        if usage:
            fields["usage_details"] = usage
        observation.update(**fields)
    except Exception as error:
        logger.warning("Falha ao atualizar observacao filha Langfuse: %s", type(error).__name__)


def provider_usage(response: object) -> dict[str, int]:
    """Use provider totals once; cache and reasoning tokens are subsets, not additions."""
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        source = usage
        keys = {"input": "input_tokens", "output": "output_tokens", "total": "total_tokens"}
    else:
        metadata = getattr(response, "response_metadata", None) or {}
        source = metadata.get("token_usage", {}) if isinstance(metadata, dict) else {}
        keys = {"input": "prompt_tokens", "output": "completion_tokens", "total": "total_tokens"}
    return {
        target: source[key]
        for target, key in keys.items()
        if isinstance(source, dict) and isinstance(source.get(key), int) and not isinstance(source[key], bool) and source[key] >= 0
    }


def invoke_generation(llm: object, prompt: str, *, name: str, prompt_id: str):
    """Instrument a single existing LangChain call without passing prompt or response to Langfuse."""
    configured_model = getattr(llm, "model_name", None)
    started_at = perf_counter()
    from app.evaluation.evidence_capture import finish_generation_capture, record_generation_input

    captured = record_generation_input(name, prompt)
    with observe_step(name, as_type="generation", metadata={"prompt_id": prompt_id}, model=configured_model) as observation:
        try:
            response = llm.invoke(prompt)
        except BaseException as error:
            finish_generation_capture(captured, "failure")
            category = "interrupted" if not isinstance(error, Exception) else "llm_provider"
            finish_step(observation, started_at, "failure", metadata={"error_category": category})
            raise
        response_metadata = getattr(response, "response_metadata", None) or {}
        actual_model = response_metadata.get("model_name") if isinstance(response_metadata, dict) else None
        usage = provider_usage(response)
        collector = _generation_collector.get()
        if collector is not None:
            entry = {"name": name, "model": actual_model or configured_model, "usage": usage}
            if captured is not None:
                entry["generation_index"] = captured["generation_index"]
            collector.append(entry)
        finish_generation_capture(captured, "success")
        finish_step(observation, started_at, "success", model=actual_model or configured_model, usage=usage)
        return response
