import json
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.theme_service import format_theme_rules, get_theme_or_default


def load_enriched_chunks_file(enriched_chunks_file: str) -> dict[str, Any]:
    path = Path(enriched_chunks_file)

    if not path.exists():
        raise ValueError("Arquivo de chunks enriquecidos não encontrado.")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def generate_document_summary(
    enriched_chunks_file: str,
    theme_id: str | None = None,
    max_chunks: int = 30,
) -> dict[str, Any]:
    settings = get_settings()

    payload = load_enriched_chunks_file(enriched_chunks_file)

    theme = get_theme_or_default(theme_id or payload.get("theme_id"))
    answer_rules = format_theme_rules(theme, "answer_rules")

    chunks = payload.get("chunks", [])

    valid_chunks = []

    for chunk in chunks:
        enrichment = chunk.get("enrichment", {})
        is_valid = enrichment.get("is_valid", True)
        quality_score = float(enrichment.get("quality_score", 0))

        if not is_valid or quality_score < 0.5:
            continue

        valid_chunks.append(
            {
                "chunk_index": chunk.get("chunk_index"),
                "page": chunk.get("page"),
                "title": enrichment.get("title"),
                "summary": enrichment.get("summary"),
                "category": enrichment.get("category"),
                "keywords": enrichment.get("keywords", []),
                "possible_questions": enrichment.get("possible_questions", []),
            }
        )

    selected_chunks = valid_chunks[:max_chunks]

    llm = ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=settings.openai_chat_temperature,
    )

    prompt = f"""
Você é um assistente especializado em resumir documentos processados por sistemas RAG.

Analise os metadados dos chunks enriquecidos abaixo e retorne apenas um JSON válido, sem markdown e sem explicações.

O JSON deve ter exatamente esta estrutura:

{{
  "document_summary": "resumo objetivo do documento em até 5 frases",
  "document_type": "tipo provável do documento",
  "main_topics": ["tópico 1", "tópico 2", "tópico 3"],
  "suggested_questions": ["pergunta 1", "pergunta 2", "pergunta 3", "pergunta 4", "pergunta 5"],
  "limitations": ["limitação 1", "limitação 2"]
}}

Regras:
- Não invente informações que não estejam nos chunks.
- Use linguagem clara e objetiva.
- As perguntas sugeridas devem ser úteis para um usuário consultar o documento.
- Se o documento parecer incompleto, técnico, fragmentado ou baseado em tabela, indique em limitations.
- Preserve o tipo de documento conforme evidências dos chunks.
- Retorne apenas JSON válido.

Regras específicas do tema "{theme["name"]}":
{answer_rules}

Chunks enriquecidos:
{json.dumps(selected_chunks, ensure_ascii=False)}
"""

    response = llm.invoke(prompt)
    raw_content = response.content.strip()

    try:
        summary = json.loads(raw_content)
    except json.JSONDecodeError:
        summary = {
            "document_summary": "",
            "document_type": "unknown",
            "main_topics": [],
            "suggested_questions": [],
            "limitations": [
                "Não foi possível gerar resumo estruturado do documento."
            ],
        }

    return {
        "document_id": payload.get("document_id"),
        "theme_id": theme["theme_id"],
        "theme_name": theme["name"],
        "summary": summary,
    }
