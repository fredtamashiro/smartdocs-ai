from typing import Any

from langchain_openai import ChatOpenAI

from app.services.vector_store_service import search_similar_chunks


def build_context_from_chunks(chunks: list[dict[str, Any]]) -> str:
    context_parts = []

    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk["metadata"]

        context_parts.append(
            f"""
Fonte {index}
Página: {metadata.get("page")}
Chunk: {metadata.get("chunk_index")}
Conteúdo:
{chunk["content"]}
"""
        )

    return "\n---\n".join(context_parts)


def answer_question_with_rag(
    collection_name: str,
    question: str,
    k: int = 4,
) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("A pergunta não pode estar vazia.")

    chunks = search_similar_chunks(
        collection_name=collection_name,
        query=question,
        k=k,
    )

    if not chunks:
        raise ValueError("Nenhum contexto relevante foi encontrado.")

    context = build_context_from_chunks(chunks)

    prompt = f"""
Você é um assistente especializado em responder perguntas com base em manuais automotivos.

Responda à pergunta do usuário usando apenas as informações presentes no contexto abaixo.

Regras:
- Não invente informações.
- Se o contexto não tiver a resposta, diga que não encontrou essa informação no manual.
- Seja claro e objetivo.
- Quando possível, mencione a página usada como fonte.

Contexto:
{context}

Pergunta:
{question}
"""

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    response = llm.invoke(prompt)

    sources = []

    for chunk in chunks:
        metadata = chunk["metadata"]

        sources.append(
            {
                "page": metadata.get("page"),
                "chunk_index": metadata.get("chunk_index"),
                "score": chunk["score"],
                "preview": chunk["content"][:300],
            }
        )

    return {
        "question": question,
        "answer": response.content,
        "sources": sources,
    }
