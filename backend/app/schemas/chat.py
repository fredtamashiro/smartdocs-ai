from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    collection_name: str = Field(
        ...,
        description="Nome da coleção no Chroma relacionada ao manual indexado.",
        examples=["manual_a8f09cc3_7baa_4575_be64_fd6fa59a7b38"],
    )

    question: str = Field(
        ...,
        min_length=3,
        description="Pergunta do usuário sobre o manual do veículo.",
        examples=["Como ligo a luz do veículo?"],
    )

    k: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Quantidade de chunks recuperados para montar o contexto.",
    )


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict[str, Any]]
