from typing import Any, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from app.services.rag_service import build_context_from_chunks
from app.services.vector_store_service import search_similar_chunks


class ManualGraphState(TypedDict):
    collection_name: str
    question: str
    k: int
    chunks: list[dict[str, Any]]
    context: str
    answer: str
    sources: list[dict[str, Any]]


def retrieve_context(state: ManualGraphState) -> ManualGraphState:
    chunks = search_similar_chunks(
        collection_name=state["collection_name"],
        query=state["question"],
        k=state["k"],
    )

    context = build_context_from_chunks(chunks)

    return {
        **state,
        "chunks": chunks,
        "context": context,
    }


def generate_answer(state: ManualGraphState) -> ManualGraphState:
    prompt = f"""
Você é um assistente especializado em responder perguntas com base em manuais automotivos.

Responda à pergunta do usuário usando apenas as informações presentes no contexto abaixo.

Regras:
- Não invente informações.
- Se o contexto não tiver a resposta, diga que não encontrou essa informação no manual.
- Seja claro e objetivo.
- Quando possível, mencione a página usada como fonte.

Contexto:
{state["context"]}

Pergunta:
{state["question"]}
"""

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    response = llm.invoke(prompt)

    return {
        **state,
        "answer": response.content,
    }


def format_sources(state: ManualGraphState) -> ManualGraphState:
    sources = []

    for chunk in state["chunks"]:
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
        **state,
        "sources": sources,
    }


def create_manual_graph():
    graph = StateGraph(ManualGraphState)

    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("format_sources", format_sources)

    graph.set_entry_point("retrieve_context")

    graph.add_edge("retrieve_context", "generate_answer")
    graph.add_edge("generate_answer", "format_sources")
    graph.add_edge("format_sources", END)

    return graph.compile()


def answer_question_with_manual_graph(
    collection_name: str,
    question: str,
    k: int = 4,
) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("A pergunta não pode estar vazia.")

    graph = create_manual_graph()

    result = graph.invoke(
        {
            "collection_name": collection_name,
            "question": question,
            "k": k,
            "chunks": [],
            "context": "",
            "answer": "",
            "sources": [],
        }
    )

    return {
        "question": result["question"],
        "answer": result["answer"],
        "sources": result["sources"],
    }
