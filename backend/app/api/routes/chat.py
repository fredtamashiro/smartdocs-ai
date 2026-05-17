from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("/ask", response_model=ChatResponse)
def ask_question(payload: ChatRequest):
    return ChatResponse(
        question=payload.question,
        answer="Resposta mockada. Futuramente aqui entra o fluxo RAG.",
    )
