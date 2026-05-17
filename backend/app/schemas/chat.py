from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        description="Pergunta do usuário sobre o manual do veículo.",
        examples=["Qual óleo devo usar no motor?"],
    )


class ChatResponse(BaseModel):
    question: str
    answer: str
