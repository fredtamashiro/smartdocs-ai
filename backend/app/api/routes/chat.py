from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import require_api_key
from app.graph.manual_graph import answer_question_with_manual_graph
from app.schemas.chat import ChatByCollectionRequest, ChatRequest, ChatResponse
from app.services.document_registry_service import find_registered_document_by_id

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("/ask", response_model=ChatResponse)
def ask_question(
    payload: ChatRequest,
    _auth: None = Depends(require_api_key),
):
    try:
        document = find_registered_document_by_id(payload.document_id)

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Documento não encontrado.",
            )

        result = answer_question_with_manual_graph(
            collection_name=document["collection_name"],
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

@router.post("/ask-by-collection", response_model=ChatResponse)
def ask_question_by_collection(payload: ChatByCollectionRequest):
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
