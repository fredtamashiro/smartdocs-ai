from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag_service import answer_question_with_rag

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("/ask", response_model=ChatResponse)
def ask_question(payload: ChatRequest):
    try:
        result = answer_question_with_rag(
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
