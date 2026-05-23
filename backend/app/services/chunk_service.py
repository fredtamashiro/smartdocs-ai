import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNKS_DIR = Path("app/storage/chunks")


def split_text_into_chunks(
    pages: list[dict[str, Any]],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[dict[str, Any]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser maior que zero.")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap não pode ser negativo.")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap deve ser menor que chunk_size.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "; ",
            ", ",
            " ",
            "",
        ],
    )

    chunks = []
    chunk_index = 1

    for page in pages:
        page_number = page["page"]
        text = page["text"].strip()

        if not text:
            continue

        page_chunks = splitter.split_text(text)

        for page_chunk in page_chunks:
            chunk_text = page_chunk.strip()

            if not chunk_text:
                continue

            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "page": page_number,
                    "content": chunk_text,
                    "char_count": len(chunk_text),
                    "chunk_strategy": "recursive_character",
                }
            )

            chunk_index += 1

    return chunks


def save_chunks_to_json(
    chunks: list[dict[str, Any]],
    source_file_path: str,
) -> dict[str, Any]:
    if not chunks:
        raise ValueError("Nenhum chunk foi gerado para salvar.")

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    document_id = str(uuid4())
    output_filename = f"{document_id}.json"
    output_path = CHUNKS_DIR / output_filename

    payload = {
        "document_id": document_id,
        "source_file_path": source_file_path,
        "chunk_strategy": "recursive_character",
        "total_chunks": len(chunks),
        "chunks": chunks,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    return {
        "document_id": document_id,
        "chunks_file": str(output_path),
        "total_chunks": len(chunks),
    }
