"""Versioned, offline audit of abstention decisions on synthetic reports."""

from copy import deepcopy
from datetime import datetime, timezone

from app.evaluation.metrics import check_case

DECISION_RULE_VERSION = "2.0.0"


def _rubric_score(answerable: bool, behavior: str) -> float | None:
    if behavior == "mixed":
        return 0.5
    if behavior == "answered":
        return 1.0 if answerable else 0.0
    if behavior in {"abstained", "asked_clarification"}:
        return 0.0 if answerable else 1.0
    return None


def resolve_abstention(case: dict, output: dict, verdict: dict) -> dict:
    """Keep consistent model verdicts; send score/behavior conflicts for human review.

    The lexical detector is recorded as an audit signal, never used as proof of
    semantic abstention. This avoids turning a partial answer into a pass.
    """
    status = verdict.get("status")
    model_score = verdict.get("model_score")
    model_behavior = verdict.get("model_behavior")
    original_reason = verdict.get("model_reason") or verdict.get("reason") or ""
    result = {"status": status, "score": model_score,
              "response_behavior": model_behavior,
              "reason": original_reason,
              "decision_rule_version": DECISION_RULE_VERSION,
              "deterministic_correction": None}
    if status != "scored":
        return {**result, "score": None}

    expected = _rubric_score(case["expected"]["answerable"], model_behavior)
    ambiguous_answer = case["category"] == "ambiguous" and model_behavior in {"answered", "mixed"}
    if expected is None or model_score != expected or ambiguous_answer:
        if ambiguous_answer:
            rule = "ambiguous_answer_requires_human_review"
        elif expected is None:
            rule = "missing_response_behavior"
        else:
            rule = "judge_score_behavior_conflict_requires_human_review"
        signal = check_case(case, output)["abstention_detected"]
        correction = {"rule": rule, "previous_score": verdict.get("score"),
                      "model_score": model_score, "model_behavior": model_behavior,
                      "rubric_score_for_behavior": expected,
                      "lexical_abstention_signal": signal,
                      "human_review_required": True}
        return {**result, "status": "not_evaluable", "score": None,
                "response_behavior": model_behavior,
                "reason": "Decisao do juiz e rubrica/comportamento em conflito; revisao humana necessaria.",
                "deterministic_correction": correction}
    return result


def audit_report(report: dict, dataset: dict) -> dict:
    """Reprocess saved judge fields only; retain all historical scores verbatim."""
    from app.evaluation.judge import validate_synthetic_report

    validate_synthetic_report(report, dataset)
    cases = {case["id"]: case for case in dataset["cases"]}
    audited = deepcopy(report)
    changes = []
    for row in audited["cases"]:
        old = row["semantic"]["abstention_correctness"]
        raw = {"status": old.get("status"), "score": old.get("score"),
               "model_score": old.get("model_score"),
               "model_behavior": old.get("model_behavior"),
               "model_reason": old.get("model_reason") or old.get("reason")}
        decision = resolve_abstention(cases[row["case_id"]], row["output"], raw)
        row["decision_audit"] = {"abstention_correctness": decision}
        if (old.get("status"), old.get("score")) != (decision["status"], decision["score"]):
            changes.append({"case_id": row["case_id"],
                            "before": {"status": old.get("status"), "score": old.get("score")},
                            "after": {"status": decision["status"], "score": decision["score"]},
                            "rule": (decision["deterministic_correction"] or {}).get("rule")})
    audited["decision_audit_version"] = DECISION_RULE_VERSION
    audited["decision_audited_at"] = datetime.now(timezone.utc).isoformat()
    audited["decision_audit_changes"] = changes
    audited["decision_audit_summary"] = {
        "cases": len(audited["cases"]),
        "changed": len(changes),
        "human_review_required": sum(bool(row["decision_audit"]["abstention_correctness"]
                                         ["deterministic_correction"])
                                     for row in audited["cases"]),
    }
    return audited
