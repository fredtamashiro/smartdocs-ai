from typing import Any, TypedDict
from app.config import get_settings

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from app.services.rag_service import build_context_from_chunks
from app.services.vector_store_service import search_similar_chunks


class ManualGraphState(TypedDict):
    collection_name: str
    question: str
    rewritten_question: str
    k: int
    chunks: list[dict[str, Any]]
    context: str
    answer: str
    sources: list[dict[str, Any]]
    has_context: bool
    min_score: float | None
    max_relevance_score: float

def rewrite_query(state: ManualGraphState) -> ManualGraphState:
    settings = get_settings()

    prompt = f"""
    Você é um assistente especializado em melhorar perguntas para busca semântica em manuais automotivos.

    Reescreva a pergunta do usuário para melhorar a recuperação de informações em um banco vetorial.

    Regras:
    - Preserve a intenção original da pergunta.
    - Inclua sinônimos e termos relacionados quando fizer sentido.
    - Não responda à pergunta.
    - Retorne apenas a pergunta reescrita, sem explicações.

    Pergunta original:
    {state["question"]}
    """

    llm = ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=0,
    )

    response = llm.invoke(prompt)

    rewritten_question = response.content.strip()

    if not rewritten_question:
        rewritten_question = state["question"]

    return {
        **state,
        "rewritten_question": rewritten_question,
    }

def retrieve_context(state: ManualGraphState) -> ManualGraphState:
    query = state["rewritten_question"] or state["question"]

    chunks = search_similar_chunks(
        collection_name=state["collection_name"],
        query=query,
        k=state["k"],
    )

    min_score = None

    if chunks:
        min_score = min(chunk["score"] for chunk in chunks)

    has_relevant_context = (
        min_score is not None
        and min_score <= state["max_relevance_score"]
    )

    context = build_context_from_chunks(chunks) if has_relevant_context else ""

    return {
        **state,
        "chunks": chunks,
        "context": context,
        "has_context": has_relevant_context,
        "min_score": min_score,
    }

def should_generate_answer(state: ManualGraphState) -> str:
    if state["has_context"]:
        return "generate_answer"

    return "answer_not_found"

def answer_not_found(state: ManualGraphState) -> ManualGraphState:
    return {
        **state,
        "answer": (
            "Não encontrei informações suficientemente relevantes no manual "
            "para responder essa pergunta com segurança."
        ),
    }

def generate_answer(state: ManualGraphState) -> ManualGraphState:
    settings = get_settings()

    prompt = f"""
Você é um assistente especializado em responder perguntas com base em manuais automotivos.

Responda à pergunta do usuário usando apenas as informações presentes no contexto abaixo.

Você receberá:
- A pergunta original do usuário
- Uma pergunta reescrita para melhorar a busca semântica
- Trechos recuperados do manual

Regras:
- Não invente informações.
- Não use conhecimento externo.
- Se o contexto trouxer termos equivalentes ou relacionados, use-os para responder.
- Se o usuário usar uma expressão informal, sinônimo ou termo aproximado, relacione com os termos técnicos encontrados no manual.
- Se o contexto não tiver nenhuma informação útil, diga que não encontrou essa informação no manual.
- Quando a informação existir de forma indireta, explique isso claramente.
- Seja claro e objetivo.
- Quando possível, mencione a página usada como fonte.

Exemplos de equivalência:
- "internet embarcada" pode estar relacionada a conexão de dados móveis, WLAN, serviços conectados, aplicativos online ou central multimídia conectada.
- "farol" pode estar relacionado a luz, iluminação, farol baixo, farol alto ou luz de posição.
- "celular" pode estar relacionado a Bluetooth, Android Auto, Apple CarPlay, chamadas ou conectividade.

Contexto recuperado do manual:
{state["context"]}

Pergunta original do usuário:
{state["question"]}

Pergunta otimizada para busca:
{state["rewritten_question"]}
"""

    llm = ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=0,
    )

    response = llm.invoke(prompt)

    return {
        **state,
        "answer": response.content,
    }


def format_sources(state: ManualGraphState) -> ManualGraphState:
    if not state["has_context"]:
        return {
            **state,
            "sources": [],
        }

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

    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("answer_not_found", answer_not_found)
    graph.add_node("format_sources", format_sources)

    graph.set_entry_point("rewrite_query")

    graph.add_edge("rewrite_query", "retrieve_context")

    graph.add_conditional_edges(
        "retrieve_context",
        should_generate_answer,
        {
            "generate_answer": "generate_answer",
            "answer_not_found": "answer_not_found",
        },
    )

    graph.add_edge("generate_answer", "format_sources")
    graph.add_edge("answer_not_found", "format_sources")
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

    settings = get_settings()

    result = graph.invoke(
        {
            "collection_name": collection_name,
            "question": question,
            "rewritten_question": "",
            "k": k,
            "chunks": [],
            "context": "",
            "answer": "",
            "sources": [],
            "has_context": False,
            "min_score": None,
            "max_relevance_score": settings.max_relevance_score,
        }
    )

    return {
        "question": result["question"],
        "answer": result["answer"],
        "sources": result["sources"],
    }
