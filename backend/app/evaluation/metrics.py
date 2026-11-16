"""Deterministic checks; lexical coverage is not factual correctness."""

import re
import unicodedata
from statistics import mean

METRICS_VERSION = "1.0.1"

_CITATION = re.compile(r"\(p\.\s*\d+(?:\s*(?:e|,|-)\s*\d+)*\)", re.IGNORECASE)


def _normalized(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w]+", " ", folded).split())


def check_case(case: dict, output: dict) -> dict:
    expected = case["expected"]
    answer = output.get("answer") or ""
    normalized = _normalized(answer)
    abstained = any(phrase in normalized for phrase in (
        "nao encontrei", "nao ha informacoes", "nao e possivel determinar",
        "informacoes insuficientes", "nao tenho informacoes",
        "nao ha informacao", "nao esta presente", "nao consta",
        "documento nao informa",
    ))
    fact_groups = expected["facts"]
    found = [any(f" {_normalized(alias)} " in f" {normalized} " for alias in aliases) for aliases in fact_groups]
    citation_present = bool(_CITATION.search(answer))
    success = output.get("error_type") is None and bool(answer.strip())
    return {
        "execution_success": success,
        "abstention_expected": not expected["answerable"],
        "abstention_detected": abstained,
        "abstention_pass": (abstained == (not expected["answerable"])) if success else False,
        "citation_required": expected["citation_required"],
        "citation_present": citation_present,
        "citation_pass": citation_present if expected["citation_required"] and success else None,
        "fact_coverage_lexical": sum(found) / len(found) if found and success else (0.0 if fact_groups else None),
        "facts_found": sum(found),
        "facts_expected": len(fact_groups),
        "latency_ms": output.get("latency_ms"),
        "reported_tokens": output.get("reported_tokens"),
        "usage_complete": output.get("usage_complete"),
        "reported_cost_usd": output.get("reported_cost_usd"),
    }


def summarize(rows: list[dict]) -> dict:
    metrics = [row["metrics"] for row in rows]
    def rate(selected, field):
        return sum(bool(item[field]) for item in selected) / len(selected) if selected else None
    latencies = [item["latency_ms"] for item in metrics if item["latency_ms"] is not None]
    coverage = [item["fact_coverage_lexical"] for item in metrics if item["fact_coverage_lexical"] is not None]
    return {
        "cases": len(rows),
        "execution_success_rate": rate(metrics, "execution_success"),
        "abstention_pass_rate": rate([m for m in metrics if m["abstention_expected"]], "abstention_pass"),
        "citation_pass_rate": rate([m for m in metrics if m["citation_required"]], "citation_pass"),
        "mean_fact_coverage_lexical": mean(coverage) if coverage else None,
        "mean_latency_ms": mean(latencies) if latencies else None,
    }
