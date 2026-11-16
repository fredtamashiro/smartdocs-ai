import json
import logging
from time import perf_counter
from typing import Any, Callable, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.services.langfuse_observability import finish_step, invoke_generation, observe_step
from app.services.pgvector_search_service import search_similar_chunks_pgvector
from app.services.query_strategy_service import (
    decide_query_generation_strategy,
    is_vague_question,
)
from app.services.rag_service import build_context_from_chunks
from app.services.theme_service import format_theme_rules, get_theme_or_default

logger = logging.getLogger(__name__)

GRAPH_TIMING_KEYS = (
    "query_generation_ms",
    "embedding_ms",
    "retrieval_ms",
    "relevance_grader_ms",
    "answer_generation_ms",
)
SOURCE_PREVIEW_MAX_CHARS = 900


class ManualGraphState(TypedDict):
    collection_name: str
    document_id: str | None
    retrieval_backend: str
    question: str
    rewritten_question: str
    search_queries: list[str]
    k: int
    chunks: list[dict[str, Any]]
    context: str
    answer: str
    sources: list[dict[str, Any]]
    has_context: bool
    min_score: float | None
    max_relevance_score: float
    theme_id: str | None
    theme_name: str | None
    query_rules: str
    answer_rules: str
    timings: dict[str, int]
    query_generation_strategy: str
    search_queries_count: int
    max_search_queries: int
    retrieved_chunks_count: int
    deduplicated_chunks_count: int
    graded_chunks_count: int
    grader_mode: str
    grader_enabled: bool
    grader_skipped_reason: str | None
    question_embedding: list[float] | None
    embedding_reused_from_cache: bool
    document_terms: list[str]
    matched_document_terms_count: int
    question_specificity_reason: str
    skip_grader_enabled: bool
    high_confidence_vector_distance_threshold: float
    min_high_confidence_chunks: int
    top_vector_distance: float | None
    best_vector_distance: float | None
    high_confidence_chunks_count: int
    skip_grader_decision: bool
    skip_grader_reason: str | None


def _append_timing(
    state: ManualGraphState,
    name: str,
    duration_ms: int,
) -> ManualGraphState:
    timings = dict(state.get("timings") or {})
    timings[name] = timings.get(name, 0) + duration_ms
    return {
        **state,
        "timings": timings,
    }


def _measure_step(
    state: ManualGraphState,
    name: str,
    callback: Callable[[], ManualGraphState],
) -> ManualGraphState:
    started_at = perf_counter()
    next_state = callback()
    duration_ms = int((perf_counter() - started_at) * 1000)
    return _append_timing(next_state, name, duration_ms)


def _truncate_text_safely(text: str, max_chars: int) -> str:
    normalized_text = " ".join((text or "").split())

    if len(normalized_text) <= max_chars:
        return normalized_text

    truncated_text = normalized_text[:max_chars].rstrip()
    last_space_index = truncated_text.rfind(" ")

    if last_space_index >= max_chars // 2:
        truncated_text = truncated_text[:last_space_index].rstrip()

    return f"{truncated_text}..."


def create_chat_model() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=settings.openai_chat_temperature,
    )


def _build_answer_context(chunks: list[dict[str, Any]]) -> str:
    settings = get_settings()
    return build_context_from_chunks(
        chunks,
        max_chunks=max(settings.max_answer_context_chunks, 1),
        max_chars_per_chunk=max(settings.max_answer_context_chars_per_chunk, 200),
    )


def _deduplication_key(metadata: dict[str, Any]) -> tuple[Any, Any]:
    """Prefer a real chunk index, including zero; fall back to page only if absent."""
    chunk_index = metadata.get("chunk_index")
    return metadata.get("document_id"), chunk_index if chunk_index is not None else metadata.get("page")


def _is_objective_question(question: str) -> bool:
    normalized_question = question.strip().lower()

    if is_vague_question(question):
        return False

    objective_starters = (
        "qual ",
        "quais ",
        "quando ",
        "onde ",
        "quanto ",
        "como devem ",
        "como deve ",
        "o que deve ",
        "o que devem ",
    )

    return normalized_question.startswith(objective_starters)


def rewrite_query(state: ManualGraphState) -> ManualGraphState:
    def _run() -> ManualGraphState:
        settings = get_settings()
        strategy_decision = decide_query_generation_strategy(
            question=state["question"],
            document_terms=state.get("document_terms") or None,
        )

        if not settings.enable_multi_query or settings.max_search_queries <= 1:
            strategy_decision = {
                **strategy_decision,
                "should_generate": False,
                "reason": "multi_query_disabled",
            }

        if not strategy_decision["should_generate"]:
            return {
                **state,
                "rewritten_question": state["question"],
                "query_generation_strategy": "original_only",
                "matched_document_terms_count": strategy_decision["matched_document_terms_count"],
                "question_specificity_reason": strategy_decision["reason"],
            }

        prompt = f"""
Voce melhora perguntas para busca semantica em documentos PDF.

Reescreva a pergunta do usuario para melhorar a recuperacao de informacoes.

Regras:
- Preserve a intencao original.
- Inclua sinonimos e termos relacionados quando fizer sentido.
- Nao responda a pergunta.
- Retorne apenas a pergunta reescrita.

Pergunta original:
{state["question"]}
"""

        llm = create_chat_model()
        response = invoke_generation(llm, prompt, name="smartdocs.rag.query_rewrite", prompt_id="query_rewrite.v1")
        rewritten_question = response.content.strip() or state["question"]

        return {
            **state,
            "rewritten_question": rewritten_question,
            "query_generation_strategy": "original_plus_rewrite",
            "matched_document_terms_count": strategy_decision["matched_document_terms_count"],
            "question_specificity_reason": strategy_decision["reason"],
        }

    return _measure_step(state, "query_generation_ms", _run)


def generate_search_queries(state: ManualGraphState) -> ManualGraphState:
    def _run() -> ManualGraphState:
        settings = get_settings()
        max_search_queries = max(settings.max_search_queries, 1)
        final_queries = [state["question"]]
        strategy = state.get("query_generation_strategy") or "original_only"

        if strategy != "original_only" and max_search_queries > 1:
            rewritten_question = (state.get("rewritten_question") or "").strip()
            if rewritten_question:
                final_queries.append(rewritten_question)

        deduplicated_queries = list(
            dict.fromkeys(query.strip() for query in final_queries if query.strip())
        )
        limited_queries = deduplicated_queries[:max_search_queries]

        return {
            **state,
            "search_queries": limited_queries,
            "search_queries_count": len(limited_queries),
            "max_search_queries": max_search_queries,
            "query_generation_strategy": strategy,
        }

    return _measure_step(state, "query_generation_ms", _run)


def retrieve_context(state: ManualGraphState) -> ManualGraphState:
    started_at = perf_counter()
    with observe_step("smartdocs.rag.retrieve", metadata={
        "query_count": len(state.get("search_queries") or [state["question"]]),
        "result_limit": state["k"],
        "score_kind": "cosine_distance",
    }) as observation:
        try:
            result, vector_search_failures = _retrieve_context_impl(state)
        except BaseException as error:
            category = "interrupted" if not isinstance(error, Exception) else "retrieval"
            finish_step(observation, started_at, "failure", metadata={"error_category": category})
            raise
        distances = [chunk["score"] for chunk in result["chunks"] if isinstance(chunk.get("score"), (int, float))]
        finish_step(observation, started_at, "success", metadata={
            "retrieved_chunks_count": result["retrieved_chunks_count"],
            "deduplicated_chunks_count": result["deduplicated_chunks_count"],
            "candidate_chunks_count": len(result["chunks"]),
            "vector_search_failures": vector_search_failures,
            "has_context": result["has_context"],
            "best_cosine_distance": min(distances) if distances else None,
        })
        return result


def _retrieve_context_impl(state: ManualGraphState) -> tuple[ManualGraphState, int]:
    from app.evaluation.evidence_capture import record_retrieval_stage, retrieval_stages

    settings = get_settings()
    max_chunks_to_grade = max(settings.max_chunks_to_grade, 1)
    search_queries = state.get("search_queries") or [state["question"]]
    candidates_by_key: dict[tuple[Any, Any], dict[str, Any]] = {}
    raw_candidates: list[dict[str, Any]] = []
    raw_winners: dict[tuple[Any, Any], dict[str, Any]] = {}
    raw_keys: dict[int, tuple[Any, Any]] = {}
    timings = dict(state.get("timings") or {})
    retrieved_chunks_count = 0
    embedding_reused_from_cache = False
    vector_search_failures = 0

    def register_timing(name: str, duration_ms: int) -> None:
        timings[name] = timings.get(name, 0) + duration_ms

    for query in search_queries:
        chunks: list[dict[str, Any]] = []

        if state.get("document_id"):
            try:
                query_embedding = None

                if query == state["question"] and state.get("question_embedding") is not None:
                    query_embedding = state["question_embedding"]
                    embedding_reused_from_cache = True

                chunks = search_similar_chunks_pgvector(
                    document_id=state["document_id"],
                    query=query,
                    k=state["k"],
                    query_embedding=query_embedding,
                    on_timing=register_timing,
                )
            except Exception:
                logger.exception("Erro ao buscar com pgvector")
                vector_search_failures += 1
                chunks = []

        retrieved_chunks_count += len(chunks)
        if retrieval_stages() is not None:
            raw_candidates.extend(chunks)

        for chunk in chunks:
            chunk_index = chunk.get("chunk_index")
            metadata = {
                **chunk.get("metadata", {}),
                "document_id": (
                    state.get("document_id")
                    or chunk.get("metadata", {}).get("document_id")
                ),
                "page": chunk.get("page") or chunk.get("metadata", {}).get("page"),
                "chunk_index": (chunk_index if chunk_index is not None
                                else chunk.get("metadata", {}).get("chunk_index")),
            }

            preview_text = (
                chunk.get("metadata", {}).get("summary")
                or chunk.get("content", "")
            )[:1000]

            normalized_chunk = {
                "content": chunk["content"],
                "retrieval_content": (
                    chunk.get("embedding_content")
                    or chunk.get("retrieval_content")
                    or chunk["content"]
                ),
                "metadata": metadata,
                "score": chunk["score"],
                "title": chunk.get("metadata", {}).get("title"),
                "summary": chunk.get("metadata", {}).get("summary"),
                "preview_for_grader": preview_text,
            }

            key = _deduplication_key(metadata)
            if retrieval_stages() is not None:
                raw_keys[id(chunk)] = key
            existing_chunk = candidates_by_key.get(key)

            if existing_chunk is None or chunk["score"] < existing_chunk["score"]:
                candidates_by_key[key] = {
                    **normalized_chunk,
                    "matched_query": query,
                }
                if retrieval_stages() is not None:
                    raw_winners[key] = chunk

    all_candidates = list(candidates_by_key.values())
    all_candidates.sort(key=lambda item: item["score"])
    graded_candidates = all_candidates[:max_chunks_to_grade]
    if retrieval_stages() is not None:
        discard_reasons = {}
        for chunk in raw_candidates:
            winner = raw_winners[raw_keys[id(chunk)]]
            if winner is chunk:
                continue
            discard_reasons[id(chunk)] = (
                "dedup_key_collision_different_chunk"
                if (chunk.get("chunk_index"), chunk.get("page")) !=
                   (winner.get("chunk_index"), winner.get("page"))
                else "duplicate_replaced_or_not_better"
            )
        record_retrieval_stage("B_after_deduplication", raw_candidates,
                               selected=list(raw_winners.values()),
                               parameters={"dedup_key": "document_id_and_chunk_index_or_page",
                                           "ranking": "cosine_distance_ascending"},
                               discarded_reason="duplicate_replaced_or_not_better",
                               discard_reasons=discard_reasons)
        record_retrieval_stage("C_grader_candidates", all_candidates,
                               selected=graded_candidates,
                               parameters={"max_chunks_to_grade": max_chunks_to_grade,
                                           "max_relevance_cosine_distance": state["max_relevance_score"],
                                           "minimum_cosine_distance": min((c["score"] for c in graded_candidates), default=None)},
                               discarded_reason="max_chunks_to_grade")
    min_score = min((chunk["score"] for chunk in graded_candidates), default=None)
    has_relevant_context = (
        min_score is not None
        and min_score <= state["max_relevance_score"]
    )
    context = _build_answer_context(graded_candidates) if has_relevant_context else ""

    return {
        **state,
        "chunks": graded_candidates,
        "context": context,
        "has_context": has_relevant_context,
        "min_score": min_score,
        "timings": timings,
        "retrieved_chunks_count": retrieved_chunks_count,
        "deduplicated_chunks_count": len(all_candidates),
        "graded_chunks_count": len(graded_candidates),
        "embedding_reused_from_cache": (
            state.get("embedding_reused_from_cache", False)
            or embedding_reused_from_cache
        ),
    }, vector_search_failures


def _parse_grader_response(raw_content: str) -> list[dict[str, Any]]:
    cleaned_content = raw_content.strip()

    if cleaned_content.startswith("```"):
        cleaned_content = cleaned_content.strip("`").strip()
        if cleaned_content.startswith("json"):
            cleaned_content = cleaned_content[4:].strip()

    try:
        grades = json.loads(cleaned_content)
    except json.JSONDecodeError:
        grades = []

    if not isinstance(grades, list):
        return []

    return [grade for grade in grades if isinstance(grade, dict)]


def _apply_grades_to_chunks(
    state: ManualGraphState,
    chunks: list[dict[str, Any]],
    grades: list[dict[str, Any]],
    fallback_on_failure: bool,
) -> ManualGraphState:
    from app.evaluation.evidence_capture import record_grader_discard_reason

    grades_by_key = {}

    for grade in grades:
        chunk_index = grade.get("chunk_index")
        page = grade.get("page")
        grades_by_key[(str(chunk_index), str(page))] = grade

    filtered_chunks = []

    for index, chunk in enumerate(chunks):
        metadata = chunk["metadata"]
        chunk_index = metadata.get("chunk_index", index)
        page = metadata.get("page")
        grade = grades_by_key.get((str(chunk_index), str(page)))

        if not grade or grade.get("is_relevant") is not True:
            record_grader_discard_reason(chunk, "grader_result_missing" if not grade else "grader_marked_not_relevant")
            continue

        enriched_metadata = {
            **metadata,
            "relevance_score": grade.get("relevance_score"),
            "relevance_reason": grade.get("reason"),
        }

        filtered_chunks.append(
            {
                **chunk,
                "metadata": enriched_metadata,
            }
        )

    if not filtered_chunks and fallback_on_failure:
        filtered_chunks = chunks

    if not filtered_chunks:
        return {
            **state,
            "chunks": [],
            "context": "",
            "has_context": False,
        }

    return {
        **state,
        "chunks": filtered_chunks,
        "context": _build_answer_context(filtered_chunks),
        "has_context": True,
    }


def _grade_chunks_batch(state: ManualGraphState, chunks: list[dict[str, Any]]) -> ManualGraphState:
    payload = []

    for index, chunk in enumerate(chunks):
        metadata = chunk["metadata"]
        payload.append(
            {
                "chunk_index": metadata.get("chunk_index", index),
                "page": metadata.get("page"),
                "title": chunk.get("title"),
                "preview": (chunk.get("preview_for_grader") or "")[:1000],
            }
        )

    prompt = f"""
Voce avalia relevancia de trechos recuperados de documentos.

Retorne apenas JSON valido.
Nao use markdown.
O JSON deve ser uma lista de objetos com:
- chunk_index
- page
- is_relevant
- relevance_score
- reason

Regras:
- Marque como relevante apenas trechos que ajudem diretamente a responder a pergunta.
- O campo reason deve ser curto, com no maximo 120 caracteres.
- Nao explique alem do necessario.

Pergunta:
{state["question"]}

Tema:
{state.get("theme_name") or "Nenhum tema informado."}

Regras do tema para busca:
{state.get("query_rules") or "Nenhuma."}

Chunks:
{json.dumps(payload, ensure_ascii=False)}
"""

    llm = create_chat_model()
    response = invoke_generation(llm, prompt, name="smartdocs.rag.classify_batch", prompt_id="relevance_batch.v1")
    grades = _parse_grader_response(response.content)

    if not grades:
        logger.warning("Batch relevance grader retornou payload invalido; usando fallback vetorial.")
        return {
            **state,
            "chunks": chunks,
            "context": _build_answer_context(chunks),
            "has_context": True,
            "grader_skipped_reason": "grader_failed_fallback",
        }

    return _apply_grades_to_chunks(
        state=state,
        chunks=chunks,
        grades=grades,
        fallback_on_failure=True,
    )


def _grade_single_chunk(
    state: ManualGraphState,
    chunk: dict[str, Any],
    default_index: int,
) -> dict[str, Any] | None:
    metadata = chunk["metadata"]
    payload = {
        "chunk_index": metadata.get("chunk_index", default_index),
        "page": metadata.get("page"),
        "title": chunk.get("title"),
        "preview": (chunk.get("preview_for_grader") or "")[:1000],
    }

    prompt = f"""
Retorne apenas JSON valido em lista com um objeto:
- chunk_index
- page
- is_relevant
- relevance_score
- reason

Reason curto, maximo 120 caracteres.

Pergunta:
{state["question"]}

Chunk:
{json.dumps(payload, ensure_ascii=False)}
"""

    llm = create_chat_model()
    response = invoke_generation(llm, prompt, name="smartdocs.rag.classify_chunk", prompt_id="relevance_chunk.v1")
    grades = _parse_grader_response(response.content)
    return grades[0] if grades else None


def _grade_chunks_per_chunk(state: ManualGraphState, chunks: list[dict[str, Any]]) -> ManualGraphState:
    grades = []

    for index, chunk in enumerate(chunks):
        try:
            grade = _grade_single_chunk(state, chunk, index)
        except Exception:
            logger.exception("Falha ao avaliar chunk individualmente; usando fallback vetorial.")
            return {
                **state,
                "chunks": chunks,
                "context": _build_answer_context(chunks),
                "has_context": True,
                "grader_skipped_reason": "grader_failed_fallback",
            }

        if grade:
            grades.append(grade)

    if not grades:
        return {
            **state,
            "chunks": chunks,
            "context": _build_answer_context(chunks),
            "has_context": True,
            "grader_skipped_reason": "grader_failed_fallback",
        }

    return _apply_grades_to_chunks(
        state=state,
        chunks=chunks,
        grades=grades,
        fallback_on_failure=True,
    )


def _should_skip_grader_for_high_confidence(chunks: list[dict[str, Any]]) -> bool:
    settings = get_settings()

    if not settings.skip_grader_for_high_confidence_retrieval:
        return False

    confident_chunks = [
        chunk
        for chunk in chunks
        if chunk.get("score") is not None
        and chunk["score"] <= settings.high_confidence_vector_distance_threshold
    ]

    return len(confident_chunks) >= settings.min_high_confidence_chunks


def _build_skip_grader_observability(
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    settings = get_settings()
    scores = [
        float(chunk["score"])
        for chunk in chunks
        if chunk.get("score") is not None
    ]
    best_vector_distance = min(scores, default=None)
    top_vector_distance = scores[0] if scores else None
    high_confidence_chunks_count = sum(
        1
        for score in scores
        if score <= settings.high_confidence_vector_distance_threshold
    )

    decision = False
    reason = None

    if not settings.skip_grader_for_high_confidence_retrieval:
        reason = "skip_disabled"
    elif not scores:
        reason = "missing_vector_distance"
    elif high_confidence_chunks_count < settings.min_high_confidence_chunks:
        if top_vector_distance is not None and (
            top_vector_distance > settings.high_confidence_vector_distance_threshold
        ):
            reason = "top_distance_above_threshold"
        else:
            reason = "insufficient_high_confidence_chunks"
    else:
        decision = True
        reason = "high_confidence_vector_retrieval"

    return {
        "skip_grader_enabled": settings.skip_grader_for_high_confidence_retrieval,
        "high_confidence_vector_distance_threshold": (
            settings.high_confidence_vector_distance_threshold
        ),
        "min_high_confidence_chunks": settings.min_high_confidence_chunks,
        "top_vector_distance": top_vector_distance,
        "best_vector_distance": best_vector_distance,
        "high_confidence_chunks_count": high_confidence_chunks_count,
        "skip_grader_decision": decision,
        "skip_grader_reason": reason,
    }


def grade_retrieved_chunks(state: ManualGraphState) -> ManualGraphState:
    def _run() -> ManualGraphState:
        settings = get_settings()
        chunks = state.get("chunks") or []
        default_mode = "batch" if settings.enable_batch_relevance_grader else "per_chunk"
        skip_observability = _build_skip_grader_observability(chunks)

        if not chunks:
            return {
                **state,
                "grader_mode": default_mode,
                "grader_enabled": False,
                "graded_chunks_count": 0,
                "grader_skipped_reason": "no_chunks",
                **skip_observability,
                "skip_grader_decision": False,
                "skip_grader_reason": "missing_vector_distance",
            }

        if skip_observability["skip_grader_decision"]:
            return {
                **state,
                "chunks": chunks,
                "context": _build_answer_context(chunks),
                "has_context": True,
                "grader_mode": "skipped_high_confidence",
                "grader_enabled": False,
                "graded_chunks_count": 0,
                "grader_skipped_reason": "high_confidence_vector_retrieval",
                **skip_observability,
            }

        base_state = {
            **state,
            "grader_mode": default_mode,
            "grader_enabled": True,
            "graded_chunks_count": len(chunks),
            "grader_skipped_reason": skip_observability["skip_grader_reason"],
            **skip_observability,
        }

        if settings.enable_batch_relevance_grader:
            return _grade_chunks_batch(base_state, chunks)

        return _grade_chunks_per_chunk(base_state, chunks)

    result = _measure_step(state, "relevance_grader_ms", _run)
    from app.evaluation.evidence_capture import grader_discard_reasons, record_retrieval_stage, retrieval_stages
    if retrieval_stages() is not None:
        record_retrieval_stage("D_relevance_grader", state.get("chunks") or [],
                               selected=result.get("chunks") or [],
                               match_by_chunk_id=True,
                               parameters={"grader_mode": result.get("grader_mode"),
                                           "grader_enabled": result.get("grader_enabled"),
                                           "grader_skipped_reason": result.get("grader_skipped_reason"),
                                           "skip_grader_decision": result.get("skip_grader_decision")},
                               discarded_reason="grader_not_selected",
                               discard_reasons=grader_discard_reasons())
    return result


def should_generate_answer(state: ManualGraphState) -> str:
    return "generate_answer" if state["has_context"] else "answer_not_found"


def answer_not_found(state: ManualGraphState) -> ManualGraphState:
    from app.evaluation.evidence_capture import record_retrieval_stage, retrieval_stages
    if retrieval_stages() is not None:
        record_retrieval_stage("E_final_context_selection", state.get("chunks") or [], selected=[],
                               parameters={"route": "answer_not_found", "context_chars": len(state.get("context") or "")},
                               discarded_reason="no_relevant_context")
    return {
        **state,
        "answer": (
            "Nao encontrei informacoes suficientemente relevantes no documento "
            "para responder essa pergunta com seguranca."
        ),
    }


def generate_answer(state: ManualGraphState) -> ManualGraphState:
    def _run() -> ManualGraphState:
        from app.evaluation.evidence_capture import record_retrieval_stage, retrieval_stages
        if retrieval_stages() is not None:
            settings = get_settings()
            chunks = state.get("chunks") or []
            cap = max(settings.max_answer_context_chunks, 1)
            record_retrieval_stage("E_final_context_selection", chunks,
                                   selected=chunks[:cap],
                                   parameters={"max_answer_context_chunks": cap,
                                               "max_answer_context_chars_per_chunk": max(settings.max_answer_context_chars_per_chunk, 200),
                                               "context_chars": len(state["context"])},
                                   discarded_reason="max_answer_context_chunks")
        concise_instruction = ""

        if _is_objective_question(state["question"]):
            concise_instruction = """
- Esta pergunta e objetiva. Prefira resposta curta e direta.
- Se o contexto permitir, responda em ate 5 bullets curtos ou 3 paragrafos curtos.
- Evite repeticao e explicacoes longas.
"""

        prompt = f"""
Voce responde perguntas com base exclusivamente no contexto recuperado de documentos.

Responda a pergunta do usuario usando apenas o contexto abaixo.

Regras gerais:
- Responda em linguagem natural, clara e profissional.
- Comece direto pela resposta.
- Nao invente informacoes.
- Se a resposta nao estiver no contexto, diga claramente isso.
- Quando fizer uma inferencia, identifique com "Inferencia:".
- Cite apenas paginas no formato "(p. 3)" ou "(p. 3 e 8)".
- Nao mencione "chunk" na resposta final.
- Use linhas em branco entre secoes quando ajudar.
- Para perguntas com multiplas partes, organize com subtitulos.
- Use lista numerada para etapas e procedimentos.
- Use bullets para grupos de itens.
{concise_instruction}

Regras especificas do tema para resposta:
{state.get("answer_rules") or "Nenhuma regra especifica de resposta foi configurada."}

Pergunta:
{state["question"]}

Contexto:
{state["context"]}
"""

        llm = create_chat_model()
        response = invoke_generation(llm, prompt, name="smartdocs.rag.generate_answer", prompt_id="answer.v1")
        return {
            **state,
            "answer": response.content,
        }

    return _measure_step(state, "answer_generation_ms", _run)


def format_sources(state: ManualGraphState) -> ManualGraphState:
    if not state["has_context"]:
        return {
            **state,
            "sources": [],
        }

    settings = get_settings()
    chunks = state["chunks"]

    if not chunks:
        return {
            **state,
            "sources": [],
        }

    best_score = min(chunk["score"] for chunk in chunks)
    max_allowed_score = min(
        settings.max_display_source_score,
        best_score + settings.display_source_score_margin,
    )

    sources = []

    for chunk in chunks:
        if chunk["score"] > max_allowed_score:
            continue

        metadata = chunk["metadata"]
        source = {
            "page": metadata.get("page"),
            "chunk_index": metadata.get("chunk_index"),
            "score": chunk["score"],
            "matched_query": chunk.get("matched_query"),
            "preview": _truncate_text_safely(
                chunk.get("content", ""),
                SOURCE_PREVIEW_MAX_CHARS,
            ),
        }

        if "relevance_score" in metadata:
            source["relevance_score"] = metadata.get("relevance_score")

        if "relevance_reason" in metadata:
            source["relevance_reason"] = metadata.get("relevance_reason")

        sources.append(source)

    return {
        **state,
        "sources": sources,
    }


def create_manual_graph():
    graph = StateGraph(ManualGraphState)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("generate_search_queries", generate_search_queries)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("grade_retrieved_chunks", grade_retrieved_chunks)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("answer_not_found", answer_not_found)
    graph.add_node("format_sources", format_sources)

    graph.set_entry_point("rewrite_query")
    graph.add_edge("rewrite_query", "generate_search_queries")
    graph.add_edge("generate_search_queries", "retrieve_context")
    graph.add_edge("retrieve_context", "grade_retrieved_chunks")
    graph.add_conditional_edges(
        "grade_retrieved_chunks",
        should_generate_answer,
        {
            "generate_answer": "generate_answer",
            "answer_not_found": "answer_not_found",
        },
    )
    graph.add_edge("generate_answer", "format_sources")
    graph.add_edge("answer_not_found", "format_sources")
    graph.add_edge("format_sources", END)

    return graph.compile()


def answer_question_with_manual_graph(
    collection_name: str,
    question: str,
    k: int = 4,
    document_id: str | None = None,
    theme_id: str | None = None,
    theme_name: str | None = None,
    query_rules: str = "",
    answer_rules: str = "",
    question_embedding: list[float] | None = None,
    document_terms: list[str] | None = None,
) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("A pergunta nao pode estar vazia.")

    graph = create_manual_graph()
    settings = get_settings()
    theme = get_theme_or_default(theme_id)
    resolved_theme_id = theme_id or theme["theme_id"]
    resolved_theme_name = theme_name or theme["name"]
    resolved_query_rules = query_rules or format_theme_rules(theme, "query_rules")
    resolved_answer_rules = answer_rules or format_theme_rules(theme, "answer_rules")

    result = graph.invoke(
        {
            "collection_name": collection_name,
            "document_id": document_id,
            "retrieval_backend": "pgvector",
            "question": question,
            "rewritten_question": "",
            "search_queries": [],
            "k": k,
            "chunks": [],
            "context": "",
            "answer": "",
            "sources": [],
            "has_context": False,
            "min_score": None,
            "max_relevance_score": settings.max_relevance_score,
            "theme_id": resolved_theme_id,
            "theme_name": resolved_theme_name,
            "query_rules": resolved_query_rules,
            "answer_rules": resolved_answer_rules,
            "timings": {name: 0 for name in GRAPH_TIMING_KEYS},
            "query_generation_strategy": "original_only",
            "search_queries_count": 0,
            "max_search_queries": max(settings.max_search_queries, 1),
            "retrieved_chunks_count": 0,
            "deduplicated_chunks_count": 0,
            "graded_chunks_count": 0,
            "grader_mode": (
                "batch" if settings.enable_batch_relevance_grader else "per_chunk"
            ),
            "grader_enabled": False,
            "grader_skipped_reason": None,
            "question_embedding": question_embedding,
            "embedding_reused_from_cache": question_embedding is not None,
            "document_terms": document_terms or [],
            "matched_document_terms_count": 0,
            "question_specificity_reason": "unknown",
            "skip_grader_enabled": settings.skip_grader_for_high_confidence_retrieval,
            "high_confidence_vector_distance_threshold": (
                settings.high_confidence_vector_distance_threshold
            ),
            "min_high_confidence_chunks": settings.min_high_confidence_chunks,
            "top_vector_distance": None,
            "best_vector_distance": None,
            "high_confidence_chunks_count": 0,
            "skip_grader_decision": False,
            "skip_grader_reason": None,
        }
    )

    return {
        "question": result["question"],
        "answer": result["answer"],
        "sources": result["sources"],
        "timings": result.get("timings", {}),
        "retrieval": {
            "query_generation_strategy": result.get("query_generation_strategy"),
            "search_queries_count": result.get("search_queries_count", 0),
            "max_search_queries": result.get("max_search_queries", 0),
            "retrieved_chunks_count": result.get("retrieved_chunks_count", 0),
            "deduplicated_chunks_count": result.get("deduplicated_chunks_count", 0),
            "graded_chunks_count": result.get("graded_chunks_count", 0),
            "matched_document_terms_count": result.get("matched_document_terms_count", 0),
            "question_specificity_reason": result.get("question_specificity_reason"),
        },
        "grader": {
            "mode": result.get("grader_mode"),
            "enabled": result.get("grader_enabled", False),
            "skipped_reason": result.get("grader_skipped_reason"),
            "skip_grader_enabled": result.get("skip_grader_enabled", False),
            "high_confidence_vector_distance_threshold": result.get(
                "high_confidence_vector_distance_threshold"
            ),
            "min_high_confidence_chunks": result.get("min_high_confidence_chunks"),
            "top_vector_distance": result.get("top_vector_distance"),
            "best_vector_distance": result.get("best_vector_distance"),
            "high_confidence_chunks_count": result.get("high_confidence_chunks_count", 0),
            "skip_grader_decision": result.get("skip_grader_decision", False),
            "skip_grader_reason": result.get("skip_grader_reason"),
        },
        "embedding_reused_from_cache": result.get("embedding_reused_from_cache", False),
    }
