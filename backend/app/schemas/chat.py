from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    document_id: str = Field(
        ...,
        description="ID do documento/manual ingerido.",
        examples=["d759fa9d-c412-4ed2-be68-0448b5472102"],
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

class ChatByCollectionRequest(BaseModel):
    collection_name: str = Field(
        ...,
        description="Nome da collection no Chroma.",
    )

    question: str = Field(
        ...,
        min_length=3,
        description="Pergunta do usuário.",
    )

    k: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Quantidade de chunks recuperados.",
    )
