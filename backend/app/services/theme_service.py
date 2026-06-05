from typing import Any

from sqlalchemy import text

from app.database.database import SessionLocal

FALLBACK_THEME = {
    "theme_id": "generic_pdf",
    "name": "PDF genérico",
    "description": "Tema padrão para documentos PDF.",
    "enrichment_rules": [],
    "query_rules": [],
    "answer_rules": [],
}


def serialize_theme(row) -> dict[str, Any]:
    mapping = row._mapping if hasattr(row, "_mapping") else row

    return {
        "theme_id": mapping["id"],
        "name": mapping["name"],
        "description": mapping["description"],
        "enrichment_rules": mapping["enrichment_rules"] or [],
        "query_rules": mapping["query_rules"] or [],
        "answer_rules": mapping["answer_rules"] or [],
    }


def list_themes() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    name,
                    description,
                    enrichment_rules,
                    query_rules,
                    answer_rules
                FROM smartdocs.themes
                WHERE is_active = TRUE
                ORDER BY name
                """
            )
        ).fetchall()

    return [serialize_theme(row) for row in rows]


def find_theme_by_id(theme_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT
                    id,
                    name,
                    description,
                    enrichment_rules,
                    query_rules,
                    answer_rules
                FROM smartdocs.themes
                WHERE id = :theme_id
                  AND is_active = TRUE
                """
            ),
            {"theme_id": theme_id},
        ).fetchone()

    if row is None:
        return None

    return serialize_theme(row)


def get_theme_or_default(theme_id: str | None) -> dict[str, Any]:
    if theme_id:
        theme = find_theme_by_id(theme_id)

        if theme:
            return theme

    default_theme = find_theme_by_id("generic_pdf")

    if default_theme:
        return default_theme

    return FALLBACK_THEME.copy()


def format_theme_rules(theme: dict[str, Any], rules_key: str) -> str:
    rules = theme.get(rules_key, [])

    if not rules:
        return "Nenhuma regra específica configurada."

    return "\n".join(f"- {rule}" for rule in rules)
