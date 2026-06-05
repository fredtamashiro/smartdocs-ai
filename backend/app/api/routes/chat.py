import logging

from fastapi import APIRouter, HTTPException, Request

from app.graph.manual_graph import answer_question_with_manual_graph
from app.schemas.chat import ChatByCollectionRequest, ChatRequest, ChatResponse
from app.services.document_registry_service import find_registered_document_by_id
from app.services.rate_limit_service import check_chat_rate_limit
from app.services.theme_service import format_theme_rules, get_theme_or_default
from app.services.usage_log_service import (
    EVENT_CHAT_QUESTION,
    EVENT_RATE_LIMIT_BLOCKED,
    create_usage_log,
)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)

logger = logging.getLogger(__name__)


@router.post("/ask", response_model=ChatResponse)
def ask_question(
    request: Request,
    payload: ChatRequest,
):
    """Responde uma pergunta usando o documento registrado pelo document_id."""
    try:
        client_ip = request.client.host if request.client else "unknown"
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
                    "question": payload.question,
                },
            )
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

        create_usage_log(
            event_type=EVENT_CHAT_QUESTION,
            ip_address=client_ip,
            document_id=payload.document_id,
            metadata={
                "question": payload.question,
                "k": payload.k,
                "rate_limit": rate_limit,
            },
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

        if document.get("retrieval_mode") == "enriched" and document.get(
            "enriched_collection_name"
        ):
            primary_collection_name = document["enriched_collection_name"]

        result = answer_question_with_manual_graph(
            collection_name=primary_collection_name,
            question=payload.question,
            k=payload.k,
            document_id=payload.document_id,
            theme_id=theme["theme_id"],
            theme_name=theme["name"],
            query_rules=query_rules,
            answer_rules=answer_rules,
        )

        should_try_fallback = (
            primary_collection_name != original_collection_name
            and len(result.get("sources", [])) == 0
        )

        if should_try_fallback:
            result = answer_question_with_manual_graph(
                collection_name=original_collection_name,
                question=payload.question,
                k=payload.k,
                document_id=payload.document_id,
                theme_id=theme["theme_id"],
                theme_name=theme["name"],
                query_rules=query_rules,
                answer_rules=answer_rules,
            )

        return ChatResponse(
            question=result["question"],
            answer=result["answer"],
            sources=result["sources"],
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

@router.post("/ask-by-collection", response_model=ChatResponse)
def ask_question_by_collection(payload: ChatByCollectionRequest):
    """Responde uma pergunta usando diretamente o nome da collection vetorial."""
    try:
        result = answer_question_with_manual_graph(
            collection_name=payload.collection_name,
            question=payload.question,
            k=payload.k,
        )

        return ChatResponse(
            question=result["question"],
            answer=result["answer"],
            sources=result["sources"],
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
