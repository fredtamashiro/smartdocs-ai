import hashlib
import json
from pathlib import Path
from typing import Any

import chromadb
from app.config import get_settings

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings


VECTORSTORE_DIR = Path("app/storage/vectorstore")
OPENAI_API_KEY_PLACEHOLDER = "sua_chave_aqui"
EMBEDDING_BATCH_MAX_DOCUMENTS = 100
EMBEDDING_BATCH_MAX_CHARS = 200_000


def load_chunks_from_json(chunks_file: str) -> dict[str, Any]:
    path = Path(chunks_file)

    if not path.exists():
        raise ValueError("Arquivo de chunks nao encontrado.")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def create_documents_from_chunks(chunks_payload: dict[str, Any]) -> list[Document]:
    documents = []

    document_id = chunks_payload["document_id"]
    source_file_path = chunks_payload["source_file_path"]

    for chunk in chunks_payload["chunks"]:
        documents.append(
            Document(
                page_content=chunk["content"],
                metadata={
                    "document_id": document_id,
                    "source_file_path": source_file_path,
                    "chunk_index": chunk["chunk_index"],
                    "page": chunk["page"],
                    "char_count": chunk["char_count"],
                    "chunk_strategy": chunk.get("chunk_strategy", "unknown"),
                },
            )
        )

    return documents


def add_documents_in_embedding_batches(
    vectorstore: Chroma,
    documents: list[Document],
) -> None:
    batch = []
    batch_chars = 0

    for document in documents:
        document_chars = len(document.page_content)

        if batch and (
            len(batch) >= EMBEDDING_BATCH_MAX_DOCUMENTS
            or batch_chars + document_chars > EMBEDDING_BATCH_MAX_CHARS
        ):
            vectorstore.add_documents(batch)
            batch = []
            batch_chars = 0

        batch.append(document)
        batch_chars += document_chars

    if batch:
        vectorstore.add_documents(batch)


def validate_openai_api_key() -> str:
    try:
        settings = get_settings()
    except Exception as error:
        raise ValueError(
            "OPENAI_API_KEY nao configurada. Defina uma chave valida em backend/.env."
        ) from error

    api_key = settings.openai_api_key

    if not api_key or api_key == OPENAI_API_KEY_PLACEHOLDER:
        raise ValueError(
            "OPENAI_API_KEY nao configurada. Defina uma chave valida em backend/.env."
        )

    return api_key


def index_chunks_in_vectorstore(chunks_file: str) -> dict[str, Any]:
    chunks_payload = load_chunks_from_json(chunks_file)
    documents = create_documents_from_chunks(chunks_payload)

    if not documents:
        raise ValueError("Nenhum documento encontrado para indexacao.")

    api_key = validate_openai_api_key()

    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)

    settings = get_settings()

    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        openai_api_key=api_key,
    )

    collection_name = f"manual_{chunks_payload['document_id'].replace('-', '_')}"

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(VECTORSTORE_DIR),
    )

    try:
        add_documents_in_embedding_batches(vectorstore, documents)
    except Exception as error:
        raise ValueError(
            f"Falha ao indexar chunks no vector store: {error}"
        ) from error

    return {
        "document_id": chunks_payload["document_id"],
        "collection_name": collection_name,
        "total_documents": len(documents),
        "vectorstore_dir": str(VECTORSTORE_DIR),
    }

def search_similar_chunks(
    collection_name: str,
    query: str,
    k: int = 4,
) -> list[dict[str, Any]]:
    if not query.strip():
        raise ValueError("A pergunta não pode estar vazia.")

    if k <= 0:
        raise ValueError("O parâmetro k deve ser maior que zero.")

    api_key = validate_openai_api_key()
    settings = get_settings()

    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        openai_api_key=api_key,
    )
    
    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(VECTORSTORE_DIR),
    )

    results = vectorstore.similarity_search_with_score(
        query=query,
        k=k,
    )

    similar_chunks = []

    for document, score in results:
        content = document.metadata.get("original_content") or document.page_content

        similar_chunks.append(
            {
                "content": content,
                "retrieval_content": document.page_content,
                "metadata": document.metadata,
                "score": score,
            }
        )

    return similar_chunks

def index_enriched_chunks_in_vectorstore(enriched_chunks_file: str) -> dict[str, Any]:
    path = Path(enriched_chunks_file)

    if not path.exists():
        raise ValueError("Arquivo de chunks enriquecidos não encontrado.")

    with path.open("r", encoding="utf-8") as file:
        enriched_payload = json.load(file)

    chunks = enriched_payload.get("chunks", [])

    if not chunks:
        raise ValueError("Nenhum chunk enriquecido encontrado para indexação.")

    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)

    settings = get_settings()

    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
    )

    document_id = enriched_payload["document_id"]
    safe_document_id = document_id.replace("-", "_")
    offset = enriched_payload.get("offset")
    limit = enriched_payload.get("limit")
    enrichment_run_id = enriched_payload.get("enrichment_run_id")
    run_token = None
    if enrichment_run_id:
        run_token = enrichment_run_id.replace("-", "")[:8]

    base_collection_name = f"manual_enriched_{safe_document_id}"
    collection_name_prefix = "manual_enriched_"
    document_hash = hashlib.sha256(document_id.encode("utf-8")).hexdigest()[:8]

    if offset is not None and limit is not None:
        collection_suffix = f"_offset_{offset}_limit_{limit}"
        if run_token:
            collection_suffix = f"{collection_suffix}_run_{run_token}"

        max_document_id_length = (
            63 - len(collection_name_prefix) - len(collection_suffix)
        )

        if max_document_id_length <= 0:
            raise ValueError("Nome da collection experimental excede o limite do Chroma.")

        if max_document_id_length <= len(document_hash):
            short_document_id = document_hash[:max_document_id_length]
        else:
            prefix_length = max_document_id_length - len(document_hash) - 1
            short_document_id = f"{safe_document_id[:prefix_length]}_{document_hash}"

        collection_name = (
            f"{collection_name_prefix}{short_document_id}{collection_suffix}"
        )
    elif run_token:
        collection_suffix = f"_run_{run_token}"
        max_document_id_length = (
            63 - len(collection_name_prefix) - len(collection_suffix)
        )

        if max_document_id_length <= 0:
            raise ValueError("Nome da collection experimental excede o limite do Chroma.")

        if max_document_id_length <= len(document_hash):
            short_document_id = document_hash[:max_document_id_length]
        else:
            prefix_length = max_document_id_length - len(document_hash) - 1
            short_document_id = f"{safe_document_id[:prefix_length]}_{document_hash}"

        collection_name = (
            f"{collection_name_prefix}{short_document_id}{collection_suffix}"
        )
    else:
        collection_name = base_collection_name

    documents = []
    total_chunks = len(chunks)
    total_skipped_chunks = 0

    for chunk in chunks:
        enrichment = chunk.get("enrichment", {})
        is_valid = enrichment.get("is_valid", True)
        quality_score = float(enrichment.get("quality_score", 0))

        if is_valid is False or quality_score < 0.5:
            total_skipped_chunks += 1
            continue

        documents.append(
            Document(
                page_content=chunk.get("embedding_content") or chunk["content"],
                metadata={
                    "document_id": document_id,
                    "source_file_path": enriched_payload.get("source_file_path"),
                    "chunk_index": chunk["chunk_index"],
                    "page": chunk["page"],
                    "char_count": chunk["char_count"],
                    "chunk_strategy": chunk.get("chunk_strategy", "unknown"),
                    "retrieval_content_type": "enriched",
                    "original_content": chunk["content"],
                    "title": enrichment.get("title", ""),
                    "category": enrichment.get("category", ""),
                    "summary": enrichment.get("summary", ""),
                    "quality_score": enrichment.get("quality_score", 0),
                    "is_valid": enrichment.get("is_valid", True),
                },
            )
        )

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(VECTORSTORE_DIR),
    )

    try:
        add_documents_in_embedding_batches(vectorstore, documents)
    except Exception as error:
        raise ValueError(
            f"Falha ao indexar chunks enriquecidos no vector store: {error}"
        ) from error

    return {
        "document_id": document_id,
        "collection_name": collection_name,
        "total_chunks": total_chunks,
        "total_indexed_documents": len(documents),
        "total_skipped_chunks": total_skipped_chunks,
        "total_documents": len(documents),
        "vectorstore_dir": str(VECTORSTORE_DIR),
    }


def delete_vectorstore_collection(collection_name: str) -> dict[str, Any]:
    if not collection_name:
        raise ValueError("Nome da collection não informado.")

    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))

    try:
        client.delete_collection(name=collection_name)

        return {
            "collection_name": collection_name,
            "deleted": True,
            "message": "Collection removida com sucesso.",
        }

    except Exception as error:
        return {
            "collection_name": collection_name,
            "deleted": False,
            "message": str(error),
        }
