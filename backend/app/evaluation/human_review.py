"""Human review templates and agreement analysis; never infer human labels."""

from copy import deepcopy
from datetime import datetime, timezone

from app.evaluation.judge import CRITERIA

REVIEW_SCHEMA_VERSION = "1.0.0"
SCORE_TOLERANCE = 0.1


def create_review_template(calibrated: dict) -> dict:
    if not calibrated.get("calibration_version"):
        raise ValueError("Crie primeiro o relatório calibrado")
    return {
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "dataset": calibrated["dataset"],
        "dataset_version": calibrated["dataset_version"],
        "dataset_sha256": calibrated["dataset_sha256"],
        "run_name": calibrated["run_name"],
        "rag_model": calibrated.get("model_configured"),
        "judge_model": calibrated["judge_model"],
        "original_rubrics": calibrated["rubric_versions"],
        "calibrated_rubrics": calibrated["rubric_versions_calibrated"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases": [{
            "case_id": row["case_id"], "question": row["question"],
            "answer": row["output"].get("answer"),
            "case_analysis": row["case_analysis"],
            "automatic": {criterion: {
                "original_judge": {key: row["semantic"][criterion].get(key)
                                   for key in ("status", "model_score", "model_behavior", "model_reason")},
                "stage3b": {key: row["semantic"][criterion].get(key)
                            for key in ("status", "score", "response_behavior", "reason")},
                "calibrated": deepcopy(row["calibrated_semantic"][criterion]),
            } for criterion in CRITERIA},
            "human": {criterion: {"status": None, "score": None, "observations": ""}
                      for criterion in CRITERIA},
            "observations": "",
        } for row in calibrated["cases"]],
    }


def _validate_human_decision(decision: dict) -> bool:
    status, score = decision.get("status"), decision.get("score")
    if status is None and score is None:
        return False
    if status == "not_evaluable" and score is None:
        return True
    if status == "scored" and isinstance(score, (float, int)) and not isinstance(score, bool) and 0 <= score <= 1:
        return True
    raise ValueError("Decisão humana deve ser scored com score entre 0 e 1 ou not_evaluable com score null")


def _empty_summary() -> dict:
    return {criterion: {"reviewed": 0, "both_not_evaluable": 0,
                        "status_agreements": 0, "scored_comparisons": 0,
                        "score_agreements": 0, "divergences": []} for criterion in CRITERIA}


def _record_comparison(bucket: dict, human: dict, auto: dict, case_id: str) -> None:
    bucket["reviewed"] += 1
    if human["status"] == auto["status"]:
        bucket["status_agreements"] += 1
    if human["status"] == auto["status"] == "not_evaluable":
        bucket["both_not_evaluable"] += 1
        return
    if human["status"] == auto["status"] == "scored":
        bucket["scored_comparisons"] += 1
        if abs(human["score"] - auto["score"]) <= SCORE_TOLERANCE:
            bucket["score_agreements"] += 1
            return
    bucket["divergences"].append({"case_id": case_id,
                                  "automatic": {"status": auto["status"], "score": auto["score"]},
                                  "human": {"status": human["status"], "score": human["score"]},
                                  "observations": human.get("observations", "")})


def _finish_summary(summary: dict) -> None:
    for bucket in summary.values():
        bucket["status_agreement_rate"] = (bucket["status_agreements"] / bucket["reviewed"]
                                           if bucket["reviewed"] else None)
        bucket["score_agreement_rate"] = (bucket["score_agreements"] / bucket["scored_comparisons"]
                                          if bucket["scored_comparisons"] else None)


def compare_human_review(calibrated: dict, review: dict) -> dict:
    if (review.get("review_schema_version") != REVIEW_SCHEMA_VERSION
            or review.get("dataset_sha256") != calibrated.get("dataset_sha256")
            or review.get("run_name") != calibrated.get("run_name")
            or review.get("calibrated_rubrics") != calibrated.get("rubric_versions_calibrated")
            or review.get("original_rubrics") != calibrated.get("rubric_versions")
            or review.get("judge_model") != calibrated.get("judge_model")
            or review.get("rag_model") != calibrated.get("model_configured")):
        raise ValueError("Arquivo de revisão não corresponde ao relatório calibrado")
    rows = {row["case_id"]: row for row in calibrated["cases"]}
    reviewed_rows = review.get("cases", [])
    if len(reviewed_rows) != len(rows) or {row["case_id"] for row in reviewed_rows} != set(rows):
        raise ValueError("Arquivo de revisão tem casos ausentes ou duplicados")
    summary = _empty_summary()
    original_summary = _empty_summary()
    result = deepcopy(calibrated)
    result_rows = {row["case_id"]: row for row in result["cases"]}
    for item in reviewed_rows:
        source = rows[item["case_id"]]
        if item.get("question") != source["question"] or item.get("answer") != source["output"].get("answer"):
            raise ValueError("Pergunta ou resposta divergente na revisão humana")
        target = result_rows[item["case_id"]]
        target["human_decisions"] = deepcopy(item["human"])
        target["human_observations"] = item.get("observations", "")
        for criterion in CRITERIA:
            human = item["human"][criterion]
            if not _validate_human_decision(human):
                continue
            _record_comparison(summary[criterion], human, source["calibrated_semantic"][criterion],
                               item["case_id"])
            _record_comparison(original_summary[criterion], human, source["semantic"][criterion],
                               item["case_id"])
    _finish_summary(summary)
    _finish_summary(original_summary)
    result["human_review"] = {"schema_version": REVIEW_SCHEMA_VERSION,
                              "compared_at": datetime.now(timezone.utc).isoformat(),
                              "score_tolerance": SCORE_TOLERANCE, "summary": summary,
                              "original_summary": original_summary}
    return result
