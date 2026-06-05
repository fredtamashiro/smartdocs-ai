from typing import Any


def build_context_from_chunks(chunks: list[dict[str, Any]]) -> str:
    context_parts = []

    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk["metadata"]

        context_parts.append(
            f"""
Fonte {index}
Pagina: {metadata.get("page")}
Chunk: {metadata.get("chunk_index")}
Conteudo:
{chunk["content"]}
"""
        )

    return "\n---\n".join(context_parts)
