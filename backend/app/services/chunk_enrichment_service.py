import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from langchain_openai import ChatOpenAI
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from app.config import get_settings
from app.database.database import SessionLocal
from app.services.pgvector_index_service import load_chunks_from_json
from app.services.theme_service import format_theme_rules, get_theme_or_default

DB_ENRICHED_CHUNKS_URI_PREFIX = "db://enriched_chunks/"


def create_chat_model() -> ChatOpenAI:
    settings = get_settings()

    return ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=settings.openai_chat_temperature,
    )


def enrich_single_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    llm = create_chat_model()

    prompt = f"""
Você é um assistente especializado em análise de chunks para sistemas RAG com documentos em PDF.

Analise o chunk abaixo e retorne apenas um JSON válido, sem markdown e sem explicações.

O JSON deve ter exatamente esta estrutura:

{{
  "is_valid": true,
  "quality_score": 0.0,
  "title": "título curto do chunk",
  "summary": "resumo objetivo do conteúdo",
  "category": "categoria do conteúdo",
  "keywords": ["palavra-chave 1", "palavra-chave 2"],
  "possible_questions": ["pergunta provável 1", "pergunta provável 2"],
  "warnings": ["observação importante ou limitação"]
}}

Regras:
- is_valid deve ser false se o chunk for índice, rodapé, texto muito fragmentado ou sem contexto útil.
- quality_score deve variar de 0 a 1.
- title deve ser curto.
- summary deve explicar o conteúdo sem inventar informação.
- keywords devem incluir sinônimos úteis para busca.
- possible_questions devem representar formas naturais de um usuário perguntar sobre esse conteúdo.
- warnings deve indicar ambiguidades, limitações ou riscos de interpretação.
- Não invente recursos que não estejam no texto.
- Se o chunk for sobre conectividade, internet, serviços online, dados móveis, Wi-Fi, WLAN, central multimídia ou serviços conectados e não confirmar chip/eSIM/modem próprio, coloque essa limitação em warnings.
- Não adicione warnings sobre chip/eSIM/modem em chunks que não sejam relacionados a conectividade.
- Quando o chunk mencionar serviços online, rede, WLAN, dados móveis, OTA, dispositivos móveis, central multimídia ou conexão, inclua keywords e possible_questions relacionadas a internet no veículo, internet embarcada, conectividade e serviços conectados.
- Só mencione chip, eSIM ou modem próprio como fato se isso estiver claramente presente no texto.
- Se o texto não confirmar chip/eSIM/modem próprio, coloque essa limitação em warnings.

Chunk:
Página: {chunk.get("page")}
Chunk index: {chunk.get("chunk_index")}
Conteúdo:
{chunk.get("content")}
"""

    response = llm.invoke(prompt)
    raw_content = response.content.strip()

    try:
        enrichment = json.loads(raw_content)
    except json.JSONDecodeError:
        enrichment = {
            "is_valid": False,
            "quality_score": 0.0,
            "title": "Erro ao enriquecer chunk",
            "summary": "",
            "category": "unknown",
            "keywords": [],
            "possible_questions": [],
            "warnings": [
                "A resposta do modelo não retornou um JSON válido."
            ],
        }

    enriched_chunk = {
        **chunk,
        "enrichment": enrichment,
    }

    enriched_chunk["embedding_content"] = build_embedding_content(enriched_chunk)

    return enriched_chunk


def enrich_chunks_file(
    chunks_file: str,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    if offset < 0:
        raise ValueError("offset não pode ser negativo.")

    if limit <= 0:
        raise ValueError("limit deve ser maior que zero.")

    chunks_payload = load_chunks_from_json(chunks_file)

    chunks = chunks_payload.get("chunks", [])

    if not chunks:
        raise ValueError("Nenhum chunk encontrado para enriquecer.")

    selected_chunks = chunks[offset : offset + limit]

    enriched_chunks = []

    for chunk in selected_chunks:
        enriched_chunks.append(enrich_single_chunk(chunk))

    document_id = chunks_payload["document_id"]
    enrichment_run_id = str(uuid4())

    payload = {
        "document_id": document_id,
        "enrichment_run_id": enrichment_run_id,
        "source_file_path": chunks_payload.get("source_file_path"),
        "original_chunks_file": chunks_file,
        "total_original_chunks": len(chunks),
        "total_enriched_chunks": len(enriched_chunks),
        "enrichment_mode": "preview",
        "offset": offset,
        "limit": limit,
        "chunks": enriched_chunks,
    }

    enriched_chunks_reference = save_enriched_chunks_payload_to_db(payload)

    return {
        "document_id": document_id,
        "enriched_chunks_file": enriched_chunks_reference,
        "total_original_chunks": len(chunks),
        "total_enriched_chunks": len(enriched_chunks),
        "offset": offset,
        "limit": limit,
        "preview": enriched_chunks[:3],
    }

def build_embedding_content(enriched_chunk: dict[str, Any]) -> str:
    enrichment = enriched_chunk.get("enrichment", {})

    title = enrichment.get("title", "")
    summary = enrichment.get("summary", "")
    category = enrichment.get("category", "")
    keywords = enrichment.get("keywords", [])
    possible_questions = enrichment.get("possible_questions", [])
    original_content = enriched_chunk.get("content", "")

    return "\n".join(
        [
            f"Título: {title}",
            f"Categoria: {category}",
            f"Resumo: {summary}",
            f"Palavras-chave: {', '.join(keywords)}",
            f"Perguntas possíveis: {' | '.join(possible_questions)}",
            f"Conteúdo original: {original_content}",
        ]
    ).strip()


def save_enriched_chunks_payload_to_db(payload: dict[str, Any]) -> str:
    document_id = payload["document_id"]
    enrichment_run_id = payload.get("enrichment_run_id") or str(uuid4())
    enriched_chunks_reference = (
        f"{DB_ENRICHED_CHUNKS_URI_PREFIX}{document_id}/{enrichment_run_id}"
    )

    with SessionLocal() as db:
        db.execute(
            text(
                """
                UPDATE smartdocs.documents
                SET
                    enriched_chunks_file = :enriched_chunks_file,
                    total_chunks = :total_chunks,
                    theme_id = :theme_id,
                    theme_name = :theme_name,
                    updated_at = NOW()
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {
                "document_id": document_id,
                "enriched_chunks_file": enriched_chunks_reference,
                "total_chunks": payload.get("total_original_chunks", 0),
                "theme_id": payload.get("theme_id"),
                "theme_name": payload.get("theme_name"),
            },
        )

        insert_query = text(
            """
            INSERT INTO smartdocs.enriched_chunks (
                id,
                document_id,
                chunk_id,
                chunk_index,
                page,
                content,
                is_valid,
                quality_score,
                title,
                summary,
                category,
                keywords,
                possible_questions,
                warnings,
                embedding_content,
                metadata
            )
            VALUES (
                CAST(:id AS UUID),
                CAST(:document_id AS UUID),
                (
                    SELECT id
                    FROM smartdocs.chunks
                    WHERE document_id = CAST(:document_id AS UUID)
                      AND chunk_index = :chunk_index
                ),
                :chunk_index,
                :page,
                :content,
                :is_valid,
                :quality_score,
                :title,
                :summary,
                :category,
                :keywords,
                :possible_questions,
                :warnings,
                :embedding_content,
                :metadata
            )
            ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                chunk_id = EXCLUDED.chunk_id,
                page = EXCLUDED.page,
                content = EXCLUDED.content,
                is_valid = EXCLUDED.is_valid,
                quality_score = EXCLUDED.quality_score,
                title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                category = EXCLUDED.category,
                keywords = EXCLUDED.keywords,
                possible_questions = EXCLUDED.possible_questions,
                warnings = EXCLUDED.warnings,
                embedding_content = EXCLUDED.embedding_content,
                metadata = EXCLUDED.metadata
            """
        ).bindparams(
            bindparam("keywords", type_=JSONB),
            bindparam("possible_questions", type_=JSONB),
            bindparam("warnings", type_=JSONB),
            bindparam("metadata", type_=JSONB),
        )

        for chunk in payload.get("chunks", []):
            enrichment = chunk.get("enrichment", {})
            db.execute(
                insert_query,
                {
                    "id": str(uuid4()),
                    "document_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "page": chunk.get("page"),
                    "content": chunk["content"],
                    "is_valid": enrichment.get("is_valid", True),
                    "quality_score": enrichment.get("quality_score", 0),
                    "title": enrichment.get("title"),
                    "summary": enrichment.get("summary"),
                    "category": enrichment.get("category"),
                    "keywords": enrichment.get("keywords", []),
                    "possible_questions": enrichment.get("possible_questions", []),
                    "warnings": enrichment.get("warnings", []),
                    "embedding_content": chunk["embedding_content"],
                    "metadata": chunk.get("metadata", {}),
                },
            )

        db.commit()

    return enriched_chunks_reference

def enrich_chunk_batch(
    chunks: list[dict[str, Any]],
    theme_id: str | None = None,
) -> list[dict[str, Any]]:
    llm = create_chat_model()

    chunks_payload = []

    for chunk in chunks:
        chunks_payload.append(
            {
                "chunk_index": chunk.get("chunk_index"),
                "page": chunk.get("page"),
                "content": chunk.get("content"),
            }
        )

    theme = get_theme_or_default(theme_id)
    theme_rules = format_theme_rules(theme, "enrichment_rules")

    prompt = f"""
Você é um assistente especializado em análise de chunks para sistemas RAG com documentos em PDF.

Analise a lista de chunks abaixo e retorne apenas um JSON válido, sem markdown e sem explicações.

O retorno deve ser uma lista JSON. Cada item da lista deve ter exatamente esta estrutura:

{{
  "chunk_index": 1,
  "is_valid": true,
  "quality_score": 0.0,
  "title": "título curto do chunk",
  "summary": "resumo objetivo do conteúdo",
  "category": "categoria do conteúdo",
  "keywords": ["palavra-chave 1", "palavra-chave 2"],
  "possible_questions": ["pergunta provável 1", "pergunta provável 2"],
  "warnings": ["observação importante ou limitação"]
}}

Regras:
- Retorne um item para cada chunk recebido.
- Preserve o chunk_index original.
- is_valid deve ser false se o chunk for índice, rodapé, texto muito fragmentado ou sem contexto útil.
- quality_score deve variar de 0 a 1.
- title deve ser curto.
- summary deve explicar o conteúdo sem inventar informação.
- keywords devem incluir sinônimos úteis para busca.
- possible_questions devem representar formas naturais de um usuário perguntar sobre esse conteúdo.
- warnings deve indicar ambiguidades, limitações ou riscos de interpretação.
- Não invente recursos que não estejam no texto.

Regras específicas do tema "{theme["name"]}":
{theme_rules}

Chunks:
{json.dumps(chunks_payload, ensure_ascii=False)}
"""

    response = llm.invoke(prompt)
    raw_content = response.content.strip()

    try:
        enrichments = json.loads(raw_content)
    except json.JSONDecodeError:
        enrichments = []

    if not isinstance(enrichments, list):
        enrichments = []

    enrichment_by_chunk_index = {
        item.get("chunk_index"): item
        for item in enrichments
        if isinstance(item, dict)
    }

    enriched_chunks = []

    for chunk in chunks:
        chunk_index = chunk.get("chunk_index")

        enrichment = enrichment_by_chunk_index.get(chunk_index)

        if not enrichment:
            enrichment = {
                "is_valid": False,
                "quality_score": 0.0,
                "title": "Erro ao enriquecer chunk",
                "summary": "",
                "category": "unknown",
                "keywords": [],
                "possible_questions": [],
                "warnings": [
                    "O modelo não retornou enriquecimento válido para este chunk."
                ],
            }

        enriched_chunk = {
            **chunk,
            "enrichment": enrichment,
        }

        enriched_chunk["embedding_content"] = build_embedding_content(enriched_chunk)

        enriched_chunks.append(enriched_chunk)

    return enriched_chunks

def enrich_chunks_file_in_batches(
    chunks_file: str,
    limit: int = 20,
    offset: int = 0,
    batch_size: int = 5,
    theme_id: str | None = None,
) -> dict[str, Any]:
    if limit <= 0:
        raise ValueError("limit deve ser maior que zero.")

    if offset < 0:
        raise ValueError("offset não pode ser negativo.")

    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero.")

    chunks_payload = load_chunks_from_json(chunks_file)
    chunks = chunks_payload.get("chunks", [])
    theme = get_theme_or_default(theme_id)

    if not chunks:
        raise ValueError("Nenhum chunk encontrado para enriquecer.")

    selected_chunks = chunks[offset : offset + limit]

    if not selected_chunks:
        raise ValueError("Nenhum chunk encontrado para o intervalo informado.")

    enriched_chunks = []

    for start in range(0, len(selected_chunks), batch_size):
        batch = selected_chunks[start : start + batch_size]
        enriched_batch = enrich_chunk_batch(batch, theme_id=theme_id)
        enriched_chunks.extend(enriched_batch)

    document_id = chunks_payload["document_id"]
    enrichment_run_id = str(uuid4())

    payload = {
        "document_id": document_id,
        "enrichment_run_id": enrichment_run_id,
        "source_file_path": chunks_payload.get("source_file_path"),
        "original_chunks_file": chunks_file,
        "total_original_chunks": len(chunks),
        "total_enriched_chunks": len(enriched_chunks),
        "enrichment_mode": "batch_preview",
        "offset": offset,
        "limit": limit,
        "batch_size": batch_size,
        "chunks": enriched_chunks,
        "theme_id": theme["theme_id"],
        "theme_name": theme["name"],
    }

    enriched_chunks_reference = save_enriched_chunks_payload_to_db(payload)

    return {
        "document_id": document_id,
        "enrichment_run_id": enrichment_run_id,
        "enriched_chunks_file": enriched_chunks_reference,
        "total_original_chunks": len(chunks),
        "total_enriched_chunks": len(enriched_chunks),
        "offset": offset,
        "limit": limit,
        "batch_size": batch_size,
        "preview": enriched_chunks[:3],
    }

def enrich_all_chunks_file(
    chunks_file: str,
    batch_size: int = 10,
    theme_id: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero.")

    chunks_payload = load_chunks_from_json(chunks_file)
    chunks = chunks_payload.get("chunks", [])
    theme = get_theme_or_default(theme_id)

    if not chunks:
        raise ValueError("Nenhum chunk encontrado para enriquecer.")

    enrichment_run_id = str(uuid4())
    document_id = chunks_payload["document_id"]
    enriched_chunks = []
    enriched_chunks_reference = (
        f"{DB_ENRICHED_CHUNKS_URI_PREFIX}{document_id}/{enrichment_run_id}"
    )

    def save_partial_payload() -> None:
        payload = {
            "document_id": document_id,
            "source_file_path": chunks_payload.get("source_file_path"),
            "original_chunks_file": chunks_file,
            "total_original_chunks": len(chunks),
            "total_enriched_chunks": len(enriched_chunks),
            "enrichment_mode": "full",
            "enrichment_run_id": enrichment_run_id,
            "batch_size": batch_size,
            "theme_id": theme["theme_id"],
            "theme_name": theme["name"],
            "status": (
                "completed"
                if len(enriched_chunks) == len(chunks)
                else "processing"
            ),
            "chunks": enriched_chunks,
        }

        nonlocal enriched_chunks_reference
        enriched_chunks_reference = save_enriched_chunks_payload_to_db(payload)

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        enriched_batch = enrich_chunk_batch(batch, theme_id=theme["theme_id"])
        enriched_chunks.extend(enriched_batch)
        save_partial_payload()
        processed_chunks = min(start + batch_size, len(chunks))

        if progress_callback:
            progress_callback(processed_chunks, len(chunks))

    save_partial_payload()

    return {
        "document_id": document_id,
        "enriched_chunks_file": enriched_chunks_reference,
        "total_original_chunks": len(chunks),
        "total_enriched_chunks": len(enriched_chunks),
        "enrichment_mode": "full",
        "enrichment_run_id": enrichment_run_id,
        "batch_size": batch_size,
        "theme_id": theme["theme_id"],
        "theme_name": theme["name"],
        "preview": enriched_chunks[:3],
    }
