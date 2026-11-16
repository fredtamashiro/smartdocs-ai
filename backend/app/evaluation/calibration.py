"""Offline, auditable calibration of saved synthetic judge results."""

from copy import deepcopy
from datetime import datetime, timezone
from statistics import mean

from app.evaluation.evidence_capture import verify_captured_record
from app.evaluation.judge import CRITERIA, RUBRIC_VERSION, RUBRIC_VERSIONS, validate_synthetic_report
from app.evaluation.metrics import _normalized, check_case

CALIBRATION_VERSION = "1.1.0"
CAPTURED_CALIBRATION_VERSION = "1.2.0"
CALIBRATED_RUBRICS = {
    "answer_correctness": RUBRIC_VERSION,
    "faithfulness": CALIBRATION_VERSION,
    "abstention_correctness": CALIBRATION_VERSION,
}
CALIBRATION_RUBRICS = {
    "missing_information": (
        "1: recusa explícita sem inventar o fato ausente; 0,5: recusa misturada a afirmação não "
        "sustentada; 0: fornece fato inexistente; null: contexto insuficiente para decidir."
    ),
    "clarification": (
        "1: solicita que o usuário escolha o sentido relevante antes de responder; 0,5: esclarece "
        "parcialmente enquanto assume um sentido; 0: escolhe um sentido sem solicitar esclarecimento."
    ),
    "multiple_interpretations": (
        "1: distingue e responde todas as interpretações materiais pertinentes com apoio nas fontes; "
        "0,5: cobre apenas parte delas; 0: escolhe uma interpretação sem sinalizar alternativas; "
        "null: interpretações ou evidências insuficientes, exigindo revisão humana."
    ),
    "faithfulness_evidence": (
        "Pontue somente com os chunks efetivamente usados na geração preservados integralmente; "
        "fontes exibidas, páginas reconstruídas e evidência ausente produzem null."
    ),
}

# Review aids, not new expected answers. Lexical hits never create an automatic pass.
AMBIGUITY_GUIDE = {
    "aur-07": {
        "interpretations": ["medição de temperatura", "medição de umidade", "retenção de dados"],
        "fact_hints": [["5 minutos"], ["10 minutos"], ["30 dias"]],
    },
    "bor-06": {
        "interpretations": ["horário limite de retirada", "disponibilidade em A", "disponibilidade em B"],
        "fact_hints": [["18 horas", "18h"], ["48 horas"], ["24 horas"]],
    },
}


def classify_case(case: dict, answer: str) -> dict:
    if case["category"] == "absent":
        return {"kind": "missing_information", "multi_interpretation_candidate": None,
                "interpretations_for_review": []}
    if case["category"] == "ambiguous":
        guide = AMBIGUITY_GUIDE.get(case["id"], {})
        normalized = f" {_normalized(answer)} "
        hits = [any(f" {_normalized(alias)} " in normalized for alias in aliases)
                for aliases in guide.get("fact_hints", [])]
        return {"kind": "ambiguous", "multi_interpretation_candidate": sum(hits) >= 2,
                "interpretations_for_review": guide.get("interpretations", []),
                "lexical_interpretations_seen": sum(hits)}
    return {"kind": "answerable", "multi_interpretation_candidate": None,
            "interpretations_for_review": []}


def evidence_provenance(row: dict, dataset: dict | None = None) -> dict:
    """Displayed sources and reconstructed pages do not prove generation context."""
    output = row["output"]
    if dataset is not None:
        for record in output.get("generation_evidence") or []:
            if verify_captured_record(record, dataset, row["case_id"], row["document"]):
                linked = any(item.get("generation_index") == record.get("generation_index")
                             and item.get("name") == record.get("generation_name")
                             for item in output.get("generations") or [])
                if linked:
                    return {"origin": "captured_generation_context", "completeness": "complete",
                            "chunks_recorded": len(record["chunks"]),
                            "context_sha256": record["context_sha256"],
                            "reason": "Contexto exato capturado na chamada de geração e verificado no fixture sintético."}
    origin = row.get("evidence_origin")
    if origin is None:
        origin = ("displayed_sources" if "displayed_source_previews" in output or "retrieved_evidence" in output
                  else "synthetic_pages_reconstructed")
    previews = output.get("displayed_source_previews", output.get("retrieved_evidence", []))
    count = len(previews or []) if origin == "displayed_sources" else len(output.get("source_pages") or [])
    if count == 0:
        return {"origin": "unavailable", "completeness": "unavailable", "chunks_recorded": 0,
                "reason": "Nenhuma evidência associada à resposta foi preservada."}
    if origin == "synthetic_pages_reconstructed":
        reason = "Páginas reconstituídas depois da execução; não comprovam o contexto enviado ao LLM."
    else:
        reason = "Fontes exibidas podem omitir chunks efetivamente usados na geração."
    return {"origin": origin, "completeness": "incomplete", "chunks_recorded": count,
            "reason": reason}


def _decision(status: str, score: float | None, reason: str, criterion: str,
              correction: dict | None = None) -> dict:
    return {"status": status, "score": score, "reason": reason,
            "rubric_version": CALIBRATED_RUBRICS[criterion], "deterministic_correction": correction}


def _summarize(rows: list[dict]) -> dict:
    summary = {}
    for criterion in CRITERIA:
        values = [row["calibrated_semantic"][criterion]["score"] for row in rows]
        scored = [value for value in values if value is not None]
        summary[criterion] = {"mean_score": mean(scored) if scored else None,
                              "scored": len(scored), "not_evaluable": len(values) - len(scored)}
    summary["abstention_by_case_type"] = {}
    for kind in ("missing_information", "ambiguous", "answerable"):
        values = [row["calibrated_semantic"]["abstention_correctness"]["score"]
                  for row in rows if row["case_analysis"]["kind"] == kind]
        scored = [value for value in values if value is not None]
        summary["abstention_by_case_type"][kind] = {
            "mean_score": mean(scored) if scored else None,
            "scored": len(scored), "not_evaluable": len(values) - len(scored),
        }
    return summary


def calibrate_report(report: dict, dataset: dict) -> dict:
    """Preserve 3B decisions and add separately versioned decisions without model calls."""
    validate_synthetic_report(report, dataset)
    legacy = {criterion: RUBRIC_VERSION for criterion in CRITERIA}
    versions = report.get("rubric_versions")
    if versions not in (legacy, RUBRIC_VERSIONS):
        raise ValueError("Versões das rubricas incompatíveis com a calibração")
    captured_version = versions == RUBRIC_VERSIONS
    calibrated_rubrics = {**CALIBRATED_RUBRICS,
                          "faithfulness": RUBRIC_VERSIONS["faithfulness"] if captured_version else CALIBRATION_VERSION}
    cases = {case["id"]: case for case in dataset["cases"]}
    result = deepcopy(report)
    changes = []
    for row in result["cases"]:
        case = cases[row["case_id"]]
        analysis = classify_case(case, row["output"].get("answer") or "")
        evidence = evidence_provenance(row, dataset)
        row["case_analysis"] = {**analysis, "evidence": evidence,
                                "partial_answer_candidate": row["semantic"]["answer_correctness"]["score"]
                                not in (None, 0.0, 1.0)}
        row["calibrated_semantic"] = {}
        original = row["semantic"]["answer_correctness"]
        row["calibrated_semantic"]["answer_correctness"] = _decision(
            original["status"], original["score"], original["reason"], "answer_correctness")

        original = row["semantic"]["faithfulness"]
        if evidence["completeness"] == "complete":
            row["calibrated_semantic"]["faithfulness"] = _decision(
                original["status"], original["score"], original["reason"], "faithfulness")
        else:
            reason = evidence["reason"] + " Score histórico preservado em semantic.faithfulness."
            row["calibrated_semantic"]["faithfulness"] = _decision(
                "not_evaluable", None, reason, "faithfulness",
                {"rule": "insufficient_generation_evidence", "previous_score": original["score"]})
        row["calibrated_semantic"]["faithfulness"]["rubric_version"] = calibrated_rubrics["faithfulness"]

        original = row["semantic"]["abstention_correctness"]
        if analysis["kind"] == "ambiguous" and original.get("response_behavior") in {"answered", "mixed"}:
            reason = ("Pergunta ambígua respondida: revisão humana deve distinguir resposta que cobre "
                      "as interpretações relevantes de escolha de um único sentido. Indícios lexicais "
                      "não determinam o score.")
            calibrated = _decision("not_evaluable", None, reason, "abstention_correctness",
                                   {"rule": "ambiguous_answer_requires_human_review",
                                    "previous_score": original["score"]})
        else:
            correction = None
            if original.get("model_behavior") != original.get("response_behavior"):
                correction = {"rule": "clear_refusal_3b", "model_behavior": original.get("model_behavior"),
                              "final_behavior": original.get("response_behavior"),
                              "detector_confirmed": check_case(case, row["output"])["abstention_detected"]}
            if original.get("model_score") != original["score"]:
                correction = {**(correction or {}), "model_score": original.get("model_score"),
                              "previous_score": original["score"]}
            calibrated = _decision(original["status"], original["score"], original["reason"],
                                   "abstention_correctness", correction)
        row["calibrated_semantic"]["abstention_correctness"] = calibrated
        for criterion in CRITERIA:
            old = row["semantic"][criterion]
            new = row["calibrated_semantic"][criterion]
            if old["status"] != new["status"] or old["score"] != new["score"]:
                changes.append({"case_id": row["case_id"], "criterion": criterion,
                                "before": {"status": old["status"], "score": old["score"]},
                                "after": {"status": new["status"], "score": new["score"]},
                                "rule": (new["deterministic_correction"] or {}).get("rule")})
    result["calibration_version"] = CAPTURED_CALIBRATION_VERSION if captured_version else CALIBRATION_VERSION
    result["rubric_versions_calibrated"] = calibrated_rubrics
    result["calibration_rubrics"] = CALIBRATION_RUBRICS.copy()
    result["calibrated_at"] = datetime.now(timezone.utc).isoformat()
    result["calibrated_summary"] = _summarize(result["cases"])
    result["calibration_changes"] = changes
    result["human_review"] = None
    return result


def compare_rubric_versions(original: dict, calibrated: dict) -> dict:
    if original["dataset_sha256"] != calibrated["dataset_sha256"] or original["run_name"] != calibrated["run_name"]:
        raise ValueError("Compare versões do mesmo dataset e da mesma execução RAG")
    if {row["case_id"] for row in original["cases"]} != {row["case_id"] for row in calibrated["cases"]}:
        raise ValueError("Os relatórios têm conjuntos de casos diferentes")
    if calibrated.get("calibration_version") not in {CALIBRATION_VERSION, CAPTURED_CALIBRATION_VERSION}:
        raise ValueError("Relatório calibrado incompatível")
    calibrated_rows = {row["case_id"]: row for row in calibrated["cases"]}
    for row in original["cases"]:
        copy = calibrated_rows[row["case_id"]]
        if (row["question"] != copy["question"] or row["output"] != copy["output"]
                or row["semantic"] != copy["semantic"]):
            raise ValueError("As decisões ou respostas originais foram alteradas")
    return {"run_name": original["run_name"], "original_rubrics": original["rubric_versions"],
            "calibrated_rubrics": calibrated["rubric_versions_calibrated"],
            "before": {criterion: original["semantic_summary"][criterion] for criterion in CRITERIA},
            "after": calibrated["calibrated_summary"],
            "changed_decisions": calibrated["calibration_changes"]}
