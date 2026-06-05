from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Representa a pergunta feita para um documento registrado."""
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
    """Representa a resposta do chat enviada para o cliente."""
    question: str
    answer: str
    sources: list[dict[str, Any]]

class ChatByCollectionRequest(BaseModel):
    """Representa a pergunta feita diretamente para uma collection vetorial."""
    collection_name: str = Field(
        ...,
        description="Identificador da collection legada.",
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
