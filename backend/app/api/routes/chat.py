import logging
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.graph.manual_graph import answer_question_with_manual_graph
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_answer_cache_service import (
    find_exact_cached_answer,
    find_semantic_cached_answer,
    get_question_embedding,
    mark_cache_hit,
    save_cached_answer,
)
from app.services.document_registry_service import find_registered_document_by_id
from app.services.langfuse_observability import finish_query, observe_query
from app.services.question_guard_service import validate_question_safety
from app.services.query_strategy_service import extract_document_search_terms
from app.services.rate_limit_service import check_chat_rate_limit
from app.services.theme_service import format_theme_rules, get_theme_or_default
from app.services.usage_log_service import (
    EVENT_CHAT_QUESTION,
    EVENT_CHAT_QUESTION_BLOCKED,
    EVENT_RATE_LIMIT_BLOCKED,
    create_usage_log,
)
from app.utils.timing import RequestTimer

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)

logger = logging.getLogger(__name__)

CHAT_TIMING_KEYS = (
    "rate_limit_ms",
    "question_guard_ms",
    "cache_lookup_ms",
    "cache_embedding_ms",
    "graph_total_ms",
    "query_generation_ms",
    "embedding_ms",
    "retrieval_ms",
    "relevance_grader_ms",
    "answer_generation_ms",
)

CACHE_SCOPE = "document"


def _build_empty_cache_metadata() -> dict[str, object]:
    return {
        "hit": False,
        "type": None,
        "scope": CACHE_SCOPE,
        "cache_id": None,
        "matched_question": None,
        "distance": None,
    }


def _build_empty_retrieval_metadata() -> dict[str, object]:
    return {
        "query_generation_strategy": "cache_hit",
        "search_queries_count": 0,
        "max_search_queries": 0,
        "retrieved_chunks_count": 0,
        "deduplicated_chunks_count": 0,
        "graded_chunks_count": 0,
    }


def _build_empty_grader_metadata() -> dict[str, object]:
    return {
        "mode": "batch",
        "enabled": False,
        "skipped_reason": None,
    }


def _should_cache_answer(answer: str, sources: list[dict], sources_count: int) -> bool:
    normalized_answer = answer.strip().lower()
    not_found_fragments = (
        "não encontrei informação",
        "nao encontrei informacao",
        "não encontrei informações",
        "nao encontrei informacoes",
        "não encontrei",
        "nao encontrei",
    )
    return (
        sources_count > 0
        and len(answer) > 100
        and bool(normalized_answer)
        and not any(fragment in normalized_answer for fragment in not_found_fragments)
        and isinstance(sources, list)
    )


@router.post("/ask", response_model=ChatResponse)
def ask_question(
    request: Request,
    payload: ChatRequest,
):
    started_at = perf_counter()
    with observe_query(str(uuid4()), len(payload.question.strip()), request.app.version) as observation:
        try:
            response = _ask_question_impl(request, payload)
        except BaseException:
            finish_query(observation, started_at, "failure")
            raise
        finish_query(observation, started_at, "success", len(response.answer))
        return response


def _ask_question_impl(request: Request, payload: ChatRequest):
    """Responde uma pergunta usando o documento registrado pelo document_id."""
    try:
        settings = get_settings()
        timer = RequestTimer()
        client_ip = request.client.host if request.client else "unknown"
        question_length = len(payload.question.strip())
        cache_metadata = _build_empty_cache_metadata()
        retrieval_metadata = _build_empty_retrieval_metadata()
        grader_metadata = _build_empty_grader_metadata()
        embedding_reused_from_cache = False
        with timer.track("rate_limit_ms"):
            rate_limit = check_chat_rate_limit(client_ip)

        if not rate_limit["allowed"]:
            logger.warning(
                "Rate limit do chat excedido: ip=%s reason=%s ip_count=%s/%s global_count=%s/%s",
                client_ip,
                rate_limit["reason"],
                rate_limit["ip_count"],
                rate_limit["ip_limit"],
                rate_limit["global_count"],
                rate_limit["global_limit"],
            )
            try:
                create_usage_log(
                    event_type=EVENT_RATE_LIMIT_BLOCKED,
                    ip_address=client_ip,
                    document_id=payload.document_id,
                    metadata={
                        "reason": rate_limit["reason"],
                        "ip_count": rate_limit["ip_count"],
                        "ip_limit": rate_limit["ip_limit"],
                        "global_count": rate_limit["global_count"],
                        "global_limit": rate_limit["global_limit"],
                        "question_length": question_length,
                        **timer.to_dict(),
                    },
                )
            except Exception:
                logger.exception("Falha ao registrar usage_log de rate_limit_blocked")
            raise HTTPException(
                status_code=429,
                detail={
                    "message": (
                        "Limite diário de uso do chat atingido. "
                        "Tente novamente amanhã."
                    ),
                    "reason": rate_limit["reason"],
                    "ip_count": rate_limit["ip_count"],
                    "ip_limit": rate_limit["ip_limit"],
                    "global_count": rate_limit["global_count"],
                    "global_limit": rate_limit["global_limit"],
                },
            )

        try:
            with timer.track("question_guard_ms"):
                question_safety = validate_question_safety(payload.question)
        except Exception:
            logger.exception("Falha ao validar seguranca da pergunta")
            try:
                blocked_timings = {name: 0 for name in CHAT_TIMING_KEYS}
                blocked_timings.update(timer.timings)
                create_usage_log(
                    event_type=EVENT_CHAT_QUESTION_BLOCKED,
                    ip_address=client_ip,
                    document_id=payload.document_id,
                    metadata={
                        "reason": "question_guard_failed",
                        "question_length": question_length,
                        "has_sensitive_data": True,
                        "duration_ms": timer.elapsed_ms(),
                        "timings": blocked_timings,
                    },
                )
            except Exception:
                logger.exception(
                    "Falha ao registrar usage_log de question_guard_failed"
                )
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "Nao foi possivel validar a seguranca da pergunta. "
                        "Tente novamente."
                    ),
                    "reason": "question_guard_failed",
                },
            )

        if not question_safety["allowed"]:
            try:
                blocked_timings = {name: 0 for name in CHAT_TIMING_KEYS}
                blocked_timings.update(timer.timings)
                create_usage_log(
                    event_type=EVENT_CHAT_QUESTION_BLOCKED,
                    ip_address=client_ip,
                    document_id=payload.document_id,
                    metadata={
                        "reason": question_safety["reason"],
                        "question_length": question_length,
                        "has_sensitive_data": True,
                        "duration_ms": timer.elapsed_ms(),
                        "timings": blocked_timings,
                    },
                )
            except Exception:
                logger.exception("Falha ao registrar usage_log de chat_question_blocked")

            raise HTTPException(
                status_code=400,
                detail={
                    "message": question_safety["message"],
                    "reason": question_safety["reason"],
                },
            )

        sanitized_question = str(question_safety["sanitized_question"])
        cached_result = None
        question_embedding = None

        if settings.chat_answer_cache_enabled:
            try:
                with timer.track("cache_lookup_ms"):
                    cached_result = find_exact_cached_answer(
                        document_id=payload.document_id,
                        question=sanitized_question,
                    )
                if cached_result:
                    cache_metadata = {
                        "hit": True,
                        "type": "exact",
                        "scope": CACHE_SCOPE,
                        "cache_id": str(cached_result["id"]),
                        "matched_question": cached_result["question"],
                        "distance": 0.0,
                    }
            except Exception:
                logger.exception("Falha ao consultar cache exato do chat")

            if (
                cached_result is None
                and settings.chat_answer_cache_semantic_enabled
            ):
                try:
                    with timer.track("cache_embedding_ms"):
                        question_embedding = get_question_embedding(sanitized_question)
                    with timer.track("cache_lookup_ms"):
                        cached_result = find_semantic_cached_answer(
                            document_id=payload.document_id,
                            question_embedding=question_embedding,
                            threshold=settings.chat_answer_cache_similarity_threshold,
                        )
                    if cached_result:
                        cache_metadata = {
                            "hit": True,
                            "type": "semantic",
                            "scope": CACHE_SCOPE,
                            "cache_id": str(cached_result["id"]),
                            "matched_question": cached_result["question"],
                            "distance": cached_result.get("distance"),
                        }
                except Exception:
                    logger.exception("Falha ao consultar cache semantico do chat")

        if cached_result:
            try:
                mark_cache_hit(str(cached_result["id"]))
            except Exception:
                logger.exception("Falha ao atualizar hit do cache do chat")

            final_timings = {name: 0 for name in CHAT_TIMING_KEYS}
            final_timings.update(timer.timings)

            try:
                create_usage_log(
                    event_type=EVENT_CHAT_QUESTION,
                    ip_address=client_ip,
                    document_id=payload.document_id,
                    metadata={
                        "question_length": len(sanitized_question),
                        "question": sanitized_question,
                        "k": payload.k,
                        "rate_limit": rate_limit,
                        "duration_ms": timer.elapsed_ms(),
                        "timings": final_timings,
                        "cache": cache_metadata,
                        "retrieval": retrieval_metadata,
                        "grader": grader_metadata,
                        "embedding_reused_from_cache": False,
                        "result": {
                            "sources_count": len(cached_result.get("sources") or []),
                            "answer_chars": len(cached_result.get("answer", "")),
                        },
                    },
                )
            except Exception:
                logger.exception("Falha ao registrar usage_log de chat_question")

            return ChatResponse(
                question=sanitized_question,
                answer=cached_result["answer"],
                sources=cached_result.get("sources") or [],
            )

        document = find_registered_document_by_id(payload.document_id)

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Documento não encontrado.",
            )

        original_collection_name = document["collection_name"]

        primary_collection_name = original_collection_name

        theme = get_theme_or_default(document.get("theme_id"))
        query_rules = format_theme_rules(theme, "query_rules")
        answer_rules = format_theme_rules(theme, "answer_rules")
        document_terms = extract_document_search_terms(document)

        if document.get("retrieval_mode") == "enriched" and document.get(
            "enriched_collection_name"
        ):
            primary_collection_name = document["enriched_collection_name"]

        with timer.track("graph_total_ms"):
            result = answer_question_with_manual_graph(
                collection_name=primary_collection_name,
                question=sanitized_question,
                k=payload.k,
                document_id=payload.document_id,
                theme_id=theme["theme_id"],
                theme_name=theme["name"],
                query_rules=query_rules,
                answer_rules=answer_rules,
                question_embedding=question_embedding,
                document_terms=document_terms,
            )

            should_try_fallback = (
                primary_collection_name != original_collection_name
                and len(result.get("sources", [])) == 0
            )

            if should_try_fallback:
                fallback_result = answer_question_with_manual_graph(
                    collection_name=original_collection_name,
                    question=sanitized_question,
                    k=payload.k,
                    document_id=payload.document_id,
                    theme_id=theme["theme_id"],
                    theme_name=theme["name"],
                    query_rules=query_rules,
                    answer_rules=answer_rules,
                    question_embedding=question_embedding,
                    document_terms=document_terms,
                )
                merged_graph_timings = dict(result.get("timings", {}))
                for name, duration_ms in fallback_result.get("timings", {}).items():
                    merged_graph_timings[name] = (
                        merged_graph_timings.get(name, 0) + duration_ms
                    )
                result = {
                    **fallback_result,
                    "timings": merged_graph_timings,
                }

        retrieval_metadata = result.get("retrieval", retrieval_metadata)
        grader_metadata = result.get("grader", grader_metadata)
        embedding_reused_from_cache = result.get("embedding_reused_from_cache", False)
        sources = result.get("sources", [])
        answer = result.get("answer", "")
        sources_count = len(sources)
        answer_chars = len(answer)

        if settings.chat_answer_cache_enabled and _should_cache_answer(
            answer=answer,
            sources=sources,
            sources_count=sources_count,
        ):
            try:
                if question_embedding is None:
                    with timer.track("cache_embedding_ms"):
                        question_embedding = get_question_embedding(sanitized_question)
                saved_cache = save_cached_answer(
                    document_id=payload.document_id,
                    question=sanitized_question,
                    question_embedding=question_embedding,
                    answer=answer,
                    sources=sources,
                    model=settings.openai_chat_model,
                    metadata={
                        "theme_id": theme["theme_id"],
                        "theme_name": theme["name"],
                        "k": payload.k,
                    },
                )
                cache_metadata = {
                    "hit": False,
                    "type": None,
                    "scope": CACHE_SCOPE,
                    "cache_id": str(saved_cache["id"]),
                    "matched_question": saved_cache["question"],
                    "distance": None,
                }
            except Exception:
                logger.exception("Falha ao salvar resposta no cache do chat")

        final_timings = {name: 0 for name in CHAT_TIMING_KEYS}
        final_timings.update(timer.timings)
        for name, duration_ms in result.get("timings", {}).items():
            final_timings[name] = final_timings.get(name, 0) + duration_ms

        try:
            create_usage_log(
                event_type=EVENT_CHAT_QUESTION,
                ip_address=client_ip,
                document_id=payload.document_id,
                metadata={
                    "question_length": len(sanitized_question),
                    "question": sanitized_question,
                    "k": payload.k,
                    "rate_limit": rate_limit,
                    "duration_ms": timer.elapsed_ms(),
                    "timings": final_timings,
                    "cache": cache_metadata,
                    "retrieval": retrieval_metadata,
                    "grader": grader_metadata,
                    "embedding_reused_from_cache": embedding_reused_from_cache,
                    "result": {
                        "sources_count": sources_count,
                        "answer_chars": answer_chars,
                    },
                },
            )
        except Exception:
            logger.exception("Falha ao registrar usage_log de chat_question")

        return ChatResponse(
            question=result["question"],
            answer=result["answer"],
            sources=result["sources"],
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
