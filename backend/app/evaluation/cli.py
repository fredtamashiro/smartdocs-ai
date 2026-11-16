"""Standalone evaluation CLI: prepare, run locally, publish, and compare."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import METRICS_VERSION, check_case, summarize


def compare_reports(before: dict, after: dict) -> dict:
    if before["dataset_sha256"] != after["dataset_sha256"]:
        raise ValueError("Os relatórios usam versões diferentes do dataset")
    if before.get("metrics_version") != after.get("metrics_version"):
        raise ValueError("Recalcule os relatórios com a mesma versão de métricas antes de comparar")
    fields = ("execution_success_rate", "abstention_pass_rate", "citation_pass_rate",
              "mean_fact_coverage_lexical", "mean_latency_ms")
    changes = {}
    for field in fields:
        old, new = before["summary"].get(field), after["summary"].get(field)
        changes[field] = {"before": old, "after": new,
                          "delta": new - old if old is not None and new is not None else None}
    comparison = {"dataset": before["dataset"], "before_run": before["run_name"],
                  "after_run": after["run_name"], "changes": changes}
    if "semantic_summary" in before and "semantic_summary" in after:
        if before.get("decision_rule_versions") != after.get("decision_rule_versions"):
            raise ValueError("Use a mesma versao das regras de decisao antes de comparar")
        if before["rubric_versions"] != after["rubric_versions"] or before["judge_model"] != after["judge_model"]:
            raise ValueError("Use a mesma versão de rubricas e o mesmo modelo avaliador")
        comparison["semantic_changes"] = {}
        for criterion in before["semantic_summary"]:
            if "mean_score" not in before["semantic_summary"][criterion]:
                continue
            old = before["semantic_summary"][criterion]["mean_score"]
            new = after["semantic_summary"][criterion]["mean_score"]
            comparison["semantic_changes"][criterion] = {
                "before": old, "after": new,
                "delta": new - old if old is not None and new is not None else None,
                "before_scored": before["semantic_summary"][criterion]["scored"],
                "after_scored": after["semantic_summary"][criterion]["scored"],
            }
        if "expected_abstention_cases" in before["semantic_summary"] and "expected_abstention_cases" in after["semantic_summary"]:
            old = before["semantic_summary"]["expected_abstention_cases"]["pass_rate"]
            new = after["semantic_summary"]["expected_abstention_cases"]["pass_rate"]
            comparison["semantic_changes"]["expected_abstention_pass_rate"] = {
                "before": old, "after": new,
                "delta": new - old if old is not None and new is not None else None,
            }
    return comparison


def rescore_report(report: dict, dataset: dict) -> dict:
    """Recompute deterministic checks from saved outputs; never call the model."""
    if report["dataset_sha256"] != dataset["sha256"]:
        raise ValueError("O relatório não corresponde ao dataset versionado")
    cases = {case["id"]: case for case in dataset["cases"]}
    case_ids = [row["case_id"] for row in report["cases"]]
    if len(case_ids) != len(set(case_ids)) or any(case_id not in cases for case_id in case_ids):
        raise ValueError("IDs de casos inválidos no relatório")
    rescored = {**report, "cases": [{**row, "metrics": check_case(cases[row["case_id"]], row["output"])}
                                     for row in report["cases"]]}
    rescored["metrics_version"] = METRICS_VERSION
    rescored["summary"] = summarize(rescored["cases"])
    return rescored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avaliação sintética do RAG SmartDocs")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="Registra e indexa documentos sintéticos locais")
    run = sub.add_parser("run", help="Executa o grafo RAG e grava relatório JSON")
    run.add_argument("--publish", action="store_true", help="Envia dataset sintético e experimento ao Langfuse")
    run.add_argument("--run-name", help="Nome único da execução para comparação")
    run.add_argument("--limit", type=int, help="Quantidade inicial de casos para smoke test")
    run.add_argument("--case-id", action="append", dest="case_ids",
                     help="Executa somente o ID informado; repetivel")
    run.add_argument("--diagnose-retrieval", action="store_true",
                     help="Registra selecao local com --capture-context, sem publicacao")
    run.add_argument("--report", type=Path, help="Caminho do relatório JSON")
    run.add_argument("--capture-context", action="store_true",
                     help="Captura o contexto sintético exato somente em experimento local")
    compare = sub.add_parser("compare", help="Compara dois relatórios do mesmo dataset")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    rescore = sub.add_parser("rescore", help="Recalcula métricas de um relatório sem executar o RAG")
    rescore.add_argument("report", type=Path)
    rescore.add_argument("--output", type=Path)
    judge = sub.add_parser("judge", help="Avalia semanticamente um relatório sintético salvo")
    judge.add_argument("report", type=Path)
    judge.add_argument("--output", type=Path)
    judge.add_argument("--model", help="Modelo OpenAI avaliador")
    judge.add_argument("--concurrency", type=int, default=2)
    audit_decisions = sub.add_parser("audit-decisions", help="Reprocessa decisoes salvas sem modelos")
    audit_decisions.add_argument("report", type=Path)
    audit_decisions.add_argument("--output", type=Path)
    judge.add_argument("--publish", action="store_true", help="Associa scores aos traces já publicados")
    calibrate = sub.add_parser("calibrate", help="Recalibra relatório 3B sem chamadas ao modelo")
    calibrate.add_argument("report", type=Path)
    calibrate.add_argument("--output", type=Path)
    rubric_compare = sub.add_parser("compare-rubrics", help="Compara decisões 3B e 3C da mesma execução")
    rubric_compare.add_argument("original", type=Path)
    rubric_compare.add_argument("calibrated", type=Path)
    review_template = sub.add_parser("review-template", help="Cria formulário humano com decisões em branco")
    review_template.add_argument("report", type=Path)
    review_template.add_argument("--output", type=Path)
    review_compare = sub.add_parser("review-compare", help="Compara decisões humanas e automáticas")
    review_compare.add_argument("report", type=Path)
    review_compare.add_argument("review", type=Path)
    review_compare.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if args.command == "compare":
        before = json.loads(args.before.read_text(encoding="utf-8"))
        after = json.loads(args.after.read_text(encoding="utf-8"))
        print(json.dumps(compare_reports(before, after), ensure_ascii=False, indent=2))
        return 0
    if args.command == "compare-rubrics":
        from app.evaluation.calibration import compare_rubric_versions

        original = json.loads(args.original.read_text(encoding="utf-8"))
        calibrated = json.loads(args.calibrated.read_text(encoding="utf-8"))
        print(json.dumps(compare_rubric_versions(original, calibrated), ensure_ascii=False, indent=2))
        return 0
    if args.command == "review-template":
        from app.evaluation.human_review import create_review_template

        report = json.loads(args.report.read_text(encoding="utf-8"))
        review = create_review_template(report)
        path = args.output or args.report.with_name(args.report.stem + ".review.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"review": str(path), "cases": len(review["cases"])}, ensure_ascii=False))
        return 0
    if args.command == "review-compare":
        from app.evaluation.human_review import compare_human_review

        report = json.loads(args.report.read_text(encoding="utf-8"))
        review = json.loads(args.review.read_text(encoding="utf-8"))
        compared = compare_human_review(report, review)
        path = args.output or args.report.with_name(args.report.stem + ".reviewed.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(compared, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(path), "human_review": compared["human_review"]}, ensure_ascii=False))
        return 0

    dataset = load_dataset()
    if args.command == "audit-decisions":
        from app.evaluation.decision_audit import audit_report

        report = json.loads(args.report.read_text(encoding="utf-8"))
        audited = audit_report(report, dataset)
        path = args.output or args.report.with_name(args.report.stem + ".audited.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(audited, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(path), "decision_audit_version": audited["decision_audit_version"],
                          "summary": audited["decision_audit_summary"]}, ensure_ascii=False))
        return 0
    if args.command == "calibrate":
        from app.evaluation.calibration import calibrate_report

        report = json.loads(args.report.read_text(encoding="utf-8"))
        calibrated = calibrate_report(report, dataset)
        path = args.output or args.report.with_name(args.report.stem + ".calibrated.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(calibrated, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(path), "calibrated_summary": calibrated["calibrated_summary"],
                          "changed_decisions": len(calibrated["calibration_changes"])}, ensure_ascii=False))
        return 0
    if args.command == "judge":
        from app.config import get_settings
        from app.evaluation.judge import judge_report

        settings = get_settings()
        report = json.loads(args.report.read_text(encoding="utf-8"))
        judged = judge_report(report, dataset, model=args.model or settings.evaluation_judge_model,
                              timeout_seconds=settings.evaluation_judge_timeout_seconds,
                              concurrency=args.concurrency, publish=args.publish)
        path = args.output or args.report.with_name(args.report.stem + ".judged.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(judged, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(path), "judge_model": judged["judge_model"],
                          "scores_published": judged["scores_published"],
                          "semantic_summary": judged["semantic_summary"],
                          "error_analysis": judged["error_analysis"]}, ensure_ascii=False))
        return 0
    if args.command == "rescore":
        report = json.loads(args.report.read_text(encoding="utf-8"))
        rescored = rescore_report(report, dataset)
        path = args.output or args.report.with_name(args.report.stem + ".rescored.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rescored, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(path), "metrics_version": METRICS_VERSION,
                          "summary": rescored["summary"]}, ensure_ascii=False))
        return 0
    if args.command == "prepare":
        from app.evaluation.prepare import prepare_local_documents
        prepared = prepare_local_documents(dataset)
        print(json.dumps({"dataset_version": dataset["version"], "documents": prepared}, ensure_ascii=False))
        return 0

    if args.limit is not None and args.limit < 1:
        parser.error("--limit deve ser positivo")
    if args.case_ids and args.limit:
        parser.error("Use --case-id ou --limit")
    if args.diagnose_retrieval and (not args.capture_context or args.publish):
        parser.error("--diagnose-retrieval exige --capture-context e sem --publish")
    from app.evaluation.runner import run_evaluation
    report = run_evaluation(dataset, publish=args.publish, run_name=args.run_name,
                            limit=args.limit, capture_context=args.capture_context,
                            case_ids=args.case_ids, diagnose_retrieval=args.diagnose_retrieval)
    path = args.report or Path(__file__).resolve().parent / "reports" / (
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), "run_name": report["run_name"],
                      "published": report["published"], "summary": report["summary"],
                      "experiment_url": report["experiment_url"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
