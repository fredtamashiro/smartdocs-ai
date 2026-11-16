"""Versioned, synthetic fixtures and deterministic identifiers."""

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

FIXTURE_PATH = Path(__file__).with_name("synthetic_rag_v1.json")


def load_dataset(path: Path = FIXTURE_PATH) -> dict:
    raw = path.read_bytes()
    dataset = json.loads(raw)
    refs = {document["ref"] for document in dataset["documents"]}
    ids = [case["id"] for case in dataset["cases"]]
    if len(refs) != len(dataset["documents"]) or len(ids) != len(set(ids)):
        raise ValueError("Documentos ou casos duplicados no dataset")
    if not 15 <= len(ids) <= 20:
        raise ValueError("O dataset inicial deve conter entre 15 e 20 casos")
    for document in dataset["documents"]:
        if not document["chunks"] or any(not chunk["text"].strip() for chunk in document["chunks"]):
            raise ValueError("Documento sintético sem chunks válidos")
    for case in dataset["cases"]:
        expected = case["expected"]
        if case["document"] not in refs or not case["question"].strip():
            raise ValueError("Referência ou pergunta inválida no dataset")
        if not isinstance(expected["answerable"], bool) or not isinstance(expected["citation_required"], bool):
            raise ValueError("Critérios inválidos no dataset")
        if any(not aliases or any(not alias for alias in aliases) for aliases in expected["facts"]):
            raise ValueError("Fato esperado sem expressão válida")
    dataset["sha256"] = hashlib.sha256(raw).hexdigest()
    return dataset


def document_id(dataset: dict, ref: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"smartdocs/eval/{dataset['version']}/{dataset['sha256']}/{ref}"))


def cloud_dataset_name(dataset: dict) -> str:
    return f"{dataset['name']}-{dataset['version']}-{dataset['sha256'][:8]}"


def cloud_item_id(dataset: dict, case_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{cloud_dataset_name(dataset)}/{case_id}"))
