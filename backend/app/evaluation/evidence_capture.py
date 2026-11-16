"""Opt-in capture of exact answer-generation context for synthetic evaluations only."""

import hashlib
import re
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import NAMESPACE_URL, uuid5

from app.evaluation.dataset import document_id

CAPTURE_VERSION = "1.0.0"
_active: ContextVar[dict | None] = ContextVar("smartdocs_synthetic_evidence_capture", default=None)
_SOURCE = re.compile(r"\nFonte (\d+)\nPagina: ([^\n]+)\nChunk: ([^\n]+)\nConteudo:\n(.*)\n\Z", re.DOTALL)
_ANSWER_GENERATION = "smartdocs.rag.generate_answer"


@contextmanager
def capture_synthetic_context(dataset: dict, case_id: str, document_ref: str, actual_document_id: str):
    """Scope text capture to one approved case and its versioned synthetic document."""
    case = next((item for item in dataset["cases"] if item["id"] == case_id), None)
    document = next((item for item in dataset["documents"] if item["ref"] == document_ref), None)
    if (case is None or document is None or case["document"] != document_ref
            or actual_document_id != document_id(dataset, document_ref)):
        raise ValueError("Captura permitida apenas para caso e documento sintéticos versionados")
    state = {"case_id": case_id, "document_ref": document_ref,
             "document_id": actual_document_id, "document": document, "records": [],
             "retrieval_stages": [], "grader_discard_reasons": {}}
    token = _active.set(state)
    try:
        yield state["records"]
    finally:
        _active.reset(token)


def _parse_context(context: str, state: dict) -> list[dict]:
    if not context:
        raise ValueError("EmptyContext")
    chunks = []
    for order, part in enumerate(context.split("\n---\n"), start=1):
        match = _SOURCE.fullmatch(part)
        if not match or int(match.group(1)) != order:
            raise ValueError("InvalidContextFormat")
        page = int(match.group(2))
        label = match.group(3)
        text = match.group(4)
        if not text:
            raise ValueError("EmptyChunk")
        matches = [(index, item) for index, item in enumerate(state["document"]["chunks"])
                   if item["page"] == page and item["text"].startswith(text)]
        if len(matches) != 1:
            raise ValueError("SyntheticChunkMismatch")
        index, _ = matches[0]
        if label != "None" and int(label) != index:
            raise ValueError("ChunkIndexMismatch")
        chunk_id = str(uuid5(NAMESPACE_URL, f"{state['document_id']}/chunk/{index}"))
        chunks.append({"order": order, "chunk_id": chunk_id,
                       "chunk_index": index, "page": page,
                       "document_id": state["document_id"], "content": text})
    return chunks


def record_generation_input(name: str, prompt: str) -> dict | None:
    """Called at the invocation boundary; never writes prompt or text to telemetry."""
    state = _active.get()
    if state is None:
        return None
    record = {"generation_index": len(state["records"]), "generation_name": name,
              "case_id": state["case_id"], "document_ref": state["document_ref"],
              "document_id": state["document_id"], "capture_version": CAPTURE_VERSION,
              "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
              "status": "no_answer_context", "llm_status": "started"}
    if name == _ANSWER_GENERATION:
        marker = "\nContexto:\n"
        if prompt.count(marker) != 1 or not prompt.endswith("\n"):
            record["status"] = "unavailable"
        else:
            context = prompt.split(marker, 1)[1][:-1]
            try:
                chunks = _parse_context(context, state)
                record.update(status="captured_verified", context_text=context,
                              context_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
                              chunks=chunks)
            except (ValueError, TypeError):
                record["status"] = "unavailable"
    state["records"].append(record)
    return record


def finish_generation_capture(record: dict | None, status: str) -> None:
    if record is not None:
        record["llm_status"] = status


def retrieval_stages() -> list[dict] | None:
    """Return the active local collector; absent for normal API traffic."""
    state = _active.get()
    return state["retrieval_stages"] if state is not None else None


def record_grader_discard_reason(chunk: dict, reason: str) -> None:
    state = _active.get()
    if state is not None:
        state["grader_discard_reasons"][id(chunk)] = reason


def grader_discard_reasons() -> dict[int, str]:
    state = _active.get()
    return state["grader_discard_reasons"] if state is not None else {}


def _candidate(chunk: dict, rank: int) -> dict:
    state = _active.get()
    metadata = chunk.get("metadata") or {}
    page = chunk.get("page") if chunk.get("page") is not None else metadata.get("page")
    index = chunk.get("chunk_index") if chunk.get("chunk_index") is not None else metadata.get("chunk_index")
    if index is None and state is not None:
        matches = [i for i, item in enumerate(state["document"]["chunks"])
                   if item["page"] == page and item["text"] == chunk.get("content")]
        index = matches[0] if len(matches) == 1 else None
    score = chunk.get("score")
    return {"chunk_id": (str(uuid5(NAMESPACE_URL, f"{state['document_id']}/chunk/{index}"))
                         if state is not None and index is not None else None),
            "document_id": state["document_id"] if state is not None else metadata.get("document_id"),
            "page": page, "chunk_index": index, "rank": rank,
            "cosine_distance": float(score) if isinstance(score, (int, float)) else None}


def record_retrieval_stage(stage: str, chunks: list[dict], *, selected: list[dict] | None = None,
                           parameters: dict | None = None, discarded_reason: str | None = None,
                           match_by_chunk_id: bool = False,
                           discard_reasons: dict[int, str] | None = None) -> None:
    """Record technical identifiers only. Never serialize chunk content or queries."""
    records = retrieval_stages()
    if records is None:
        return
    selected_ids = None if selected is None else {id(chunk) for chunk in selected}
    selected_chunks = ({_candidate(chunk, 0)["chunk_id"] for chunk in selected}
                       if selected is not None and match_by_chunk_id else set())
    candidates = []
    for rank, chunk in enumerate(chunks, 1):
        item = _candidate(chunk, rank)
        kept = (selected_ids is None or id(chunk) in selected_ids
                or (match_by_chunk_id and item["chunk_id"] is not None
                    and item["chunk_id"] in selected_chunks))
        item.update(status="selected" if kept else "discarded",
                    discard_reason=None if kept else (discard_reasons or {}).get(id(chunk), discarded_reason))
        candidates.append(item)
    records.append({"stage": stage, "parameters": parameters or {}, "candidates": candidates})


def record_vector_results(query: str, document_id_value: str, k: int, chunks: list[dict]) -> None:
    state = _active.get()
    if state is None or document_id_value != state["document_id"]:
        return
    record_retrieval_stage("A_vector_search", chunks,
                           parameters={"query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
                                       "result_limit": k, "score_kind": "cosine_distance"})


def verify_captured_record(record: dict, dataset: dict, case_id: str, document_ref: str) -> bool:
    """Reject edited or foreign text before sending any captured context to the judge."""
    document = next((item for item in dataset["documents"] if item["ref"] == document_ref), None)
    if document is None:
        return False
    expected_id = document_id(dataset, document_ref)
    if (record.get("status") != "captured_verified" or record.get("llm_status") != "success"
            or record.get("generation_name") != _ANSWER_GENERATION
            or record.get("case_id") != case_id or record.get("document_ref") != document_ref
            or record.get("document_id") != expected_id or record.get("capture_version") != CAPTURE_VERSION):
        return False
    context = record.get("context_text")
    if not isinstance(context, str) or hashlib.sha256(context.encode("utf-8")).hexdigest() != record.get("context_sha256"):
        return False
    try:
        parsed = _parse_context(context, {"document": document, "document_id": expected_id})
    except (ValueError, TypeError):
        return False
    return parsed == record.get("chunks")
