import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.api.admin_auth import require_admin_user
from app.api.dependencies import require_api_key
from app.services.chunk_enrichment_service import (
    enrich_all_chunks_file,
    enrich_chunks_file,
    enrich_chunks_file_in_batches,
)
from app.services.chunk_service import save_chunks_to_json, split_text_into_chunks
from app.services.document_registry_service import (
    delete_registered_document,
    find_registered_document_by_id,
    list_registered_documents,
    register_document,
)
from app.services.document_service import extract_text_from_pdf, save_uploaded_file
from app.services.document_summary_service import generate_document_summary
from app.services.theme_service import find_theme_by_id
from app.services.pgvector_index_service import index_enriched_chunks_in_pgvector

from app.services.processing_job_service import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    create_processing_job,
    update_processing_job,
)
from app.services.pgvector_search_service import search_similar_chunks_pgvector

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path("app/storage/uploads").resolve()

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


def ensure_path_inside_directory(path_value: str, base_dir: Path, label: str) -> str:
    """Garante que um caminho recebido pela API esta dentro da pasta permitida."""
    path = Path(path_value).resolve()

    try:
        path.relative_to(base_dir)
    except ValueError as error:
        raise ValueError(f"{label} deve estar dentro de {base_dir}.") from error

    return str(path)


def remove_file_if_exists(file_path: str | None) -> bool:
    if not file_path:
        return False

    path = Path(file_path)

    if not path.exists():
        return False

    if not path.is_file():
        return False

    path.unlink()

    return True


def run_smart_ingest_job(
    job_id: str,
    saved_file: dict,
    theme_id: str,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
) -> None:
    try:
        update_processing_job(
            job_id,
            {
                "status": STATUS_PROCESSING,
                "progress": 5,
                "current_step": "Extraindo texto do PDF",
            },
        )

        extracted_text = extract_text_from_pdf(saved_file["path"])

        update_processing_job(
            job_id,
            {
                "progress": 15,
                "current_step": "Gerando chunks do documento",
            },
        )

        chunks = split_text_into_chunks(
            pages=extracted_text["pages"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        saved_chunks = save_chunks_to_json(
            chunks=chunks,
            source_file_path=extracted_text["file_path"],
        )

        update_processing_job(
            job_id,
            {
                "progress": 30,
                "current_step": "Enriquecendo chunks com IA",
                "partial_result": {
                    "chunks_file": saved_chunks["chunks_file"],
                    "total_chunks": saved_chunks["total_chunks"],
                },
            },
        )

        def update_enrichment_progress(
            processed_chunks: int,
            total_chunks: int,
        ) -> None:
            enrichment_progress = 30 + int((processed_chunks / total_chunks) * 50)

            update_processing_job(
                job_id,
                {
                    "progress": min(enrichment_progress, 80),
                    "current_step": (
                        f"Enriquecendo chunks com IA "
                        f"({processed_chunks}/{total_chunks})"
                    ),
                    "partial_result": {
                        "chunks_file": saved_chunks["chunks_file"],
                        "total_chunks": saved_chunks["total_chunks"],
                        "processed_chunks": processed_chunks,
                    },
                },
            )

        enriched_chunks = enrich_all_chunks_file(
            chunks_file=saved_chunks["chunks_file"],
            batch_size=batch_size,
            theme_id=theme_id,
            progress_callback=update_enrichment_progress,
        )

        update_processing_job(
            job_id,
            {
                "progress": 80,
                "current_step": "Indexando chunks enriquecidos no pgvector",
                "partial_result": {
                    "chunks_file": saved_chunks["chunks_file"],
                    "enriched_chunks_file": enriched_chunks["enriched_chunks_file"],
                    "total_chunks": saved_chunks["total_chunks"],
                    "total_enriched_chunks": enriched_chunks["total_enriched_chunks"],
                },
            },
        )

        indexed_document = index_enriched_chunks_in_pgvector(
            enriched_chunks_file=enriched_chunks["enriched_chunks_file"],
        )

        update_processing_job(
            job_id,
            {
                "progress": 90,
                "current_step": "Gerando resumo do documento",
            },
        )

        document_summary = generate_document_summary(
            enriched_chunks_file=enriched_chunks["enriched_chunks_file"],
            theme_id=theme_id,
        )

        theme = find_theme_by_id(theme_id)

        if theme is None:
            raise ValueError("Tema informado nÃ£o encontrado.")

        document_payload = {
            "original_filename": saved_file["original_filename"],
            "stored_filename": saved_file["stored_filename"],
            "file_path": saved_file["path"],
            "document_id": indexed_document["document_id"],
            "collection_name": indexed_document["collection_name"],
            "enriched_collection_name": indexed_document["collection_name"],
            "retrieval_mode": "pgvector",
            "theme_id": theme["theme_id"],
            "theme_name": theme["name"],
            "total_pages": extracted_text["total_pages"],
            "total_chars": extracted_text["total_chars"],
            "total_chunks": saved_chunks["total_chunks"],
            "chunks_file": saved_chunks["chunks_file"],
            "enriched_chunks_file": enriched_chunks["enriched_chunks_file"],
            "document_summary": document_summary["summary"].get("document_summary"),
            "document_type": document_summary["summary"].get("document_type"),
            "main_topics": document_summary["summary"].get("main_topics", []),
            "suggested_questions": document_summary["summary"].get(
                "suggested_questions",
                [],
            ),
            "summary_limitations": document_summary["summary"].get("limitations", []),
        }

        registered_document = register_document(document_payload)

        update_processing_job(
            job_id,
            {
                "status": STATUS_COMPLETED,
                "progress": 100,
                "current_step": "Processamento concluÃ­do",
                "result": {
                    "document": registered_document,
                    "retrieval_backend": "pgvector",
                    "total_enriched_chunks": indexed_document.get(
                        "total_enriched_chunks"
                    ),
                    "total_embeddings": indexed_document.get("total_embeddings"),
                    "total_indexed_documents": indexed_document.get(
                        "total_indexed_documents",
                        indexed_document.get("total_documents"),
                    ),
                    "total_skipped_chunks": indexed_document.get("total_skipped_chunks"),
                    "skipped_chunks": indexed_document.get("skipped_chunks", []),
                },
            },
        )

    except Exception as error:
        logger.exception("Erro ao executar smart ingest job %s", job_id)

        update_processing_job(
            job_id,
            {
                "status": STATUS_FAILED,
                "current_step": "Erro no processamento",
                "error": str(error),
            },
        )


@router.get("")
def list_documents():
    """Lista todos os documentos ja ingeridos e registrados."""
    documents = list_registered_documents()

    return {
        "total": len(documents),
        "documents": documents,
    }


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    _admin_user: dict = Depends(require_admin_user),
):
    try:
        document = find_registered_document_by_id(document_id)

        if document is None:
            raise ValueError("Documento não encontrado.")

        removed_document = delete_registered_document(document_id)

        deleted_files = []

        file_fields = [
            "file_path",
            "chunks_file",
            "enriched_chunks_file",
        ]

        for field in file_fields:
            file_path = removed_document.get(field)

            if remove_file_if_exists(file_path):
                deleted_files.append(
                    {
                        "field": field,
                        "path": file_path,
                    }
                )

        return {
            "message": "Documento apagado com sucesso.",
            "document_id": document_id,
            "deleted_files": deleted_files,
            "removed_document": removed_document,
        }

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        logger.exception("Erro inesperado ao apagar documento")
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado ao apagar documento: {error}",
        )


@router.post("/chunk")
def chunk_document(
    file_path: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    _auth: None = Depends(require_api_key),
):
    """Divide o texto de um PDF em chunks para consulta posterior."""
    try:
        safe_file_path = ensure_path_inside_directory(
            path_value=file_path,
            base_dir=UPLOADS_DIR,
            label="file_path",
        )

        extracted_text = extract_text_from_pdf(safe_file_path)

        chunks = split_text_into_chunks(
            pages=extracted_text["pages"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        preview_chunks = []

        for chunk in chunks[:5]:
            preview_chunks.append(
                {
                    "chunk_index": chunk["chunk_index"],
                    "page": chunk["page"],
                    "char_count": chunk["char_count"],
                    "preview": chunk["content"][:300],
                }
            )

        return {
            "message": "Chunks gerados com sucesso.",
            "file_path": extracted_text["file_path"],
            "total_pages": extracted_text["total_pages"],
            "total_chars": extracted_text["total_chars"],
            "total_chunks": len(chunks),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "preview_chunks": preview_chunks,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/process")
def process_document(
    file_path: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    _auth: None = Depends(require_api_key),
):
    """Extrai texto, gera chunks e salva o arquivo JSON de chunks."""
    try:
        safe_file_path = ensure_path_inside_directory(
            path_value=file_path,
            base_dir=UPLOADS_DIR,
            label="file_path",
        )

        extracted_text = extract_text_from_pdf(safe_file_path)

        chunks = split_text_into_chunks(
            pages=extracted_text["pages"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        saved_chunks = save_chunks_to_json(
            chunks=chunks,
            source_file_path=extracted_text["file_path"],
        )

        return {
            "message": "Documento processado com sucesso.",
            "file_path": extracted_text["file_path"],
            "total_pages": extracted_text["total_pages"],
            "total_chars": extracted_text["total_chars"],
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "document_id": saved_chunks["document_id"],
            "chunks_file": saved_chunks["chunks_file"],
            "total_chunks": saved_chunks["total_chunks"],
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
@router.post("/{document_id}/search-pgvector")
def search_document_pgvector(
    document_id: str,
    query: str,
    k: int = 4,
    _auth: None = Depends(require_api_key),
):
    try:
        results = search_similar_chunks_pgvector(
            document_id=document_id,
            query=query,
            k=k,
        )

        return {
            "document_id": document_id,
            "query": query,
            "k": k,
            "total": len(results),
            "results": results,
        }

    except Exception as error:
        logger.exception("Erro ao buscar chunks com pgvector")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar chunks com pgvector: {error}",
        )


@router.post("/enrich-chunks")
def enrich_document_chunks(
    chunks_file: str,
    limit: int = 10,
    offset: int = 0,
):
    """Enriquece uma parte dos chunks com informacoes adicionais geradas por IA."""
    try:
        result = enrich_chunks_file(
            chunks_file=chunks_file,
            limit=limit,
            offset=offset,
        )

        return {
            "message": "Chunks enriquecidos com sucesso.",
            "document_id": result["document_id"],
            "enriched_chunks_file": result["enriched_chunks_file"],
            "total_original_chunks": result["total_original_chunks"],
            "total_enriched_chunks": result["total_enriched_chunks"],
            "preview": result["preview"],
            "offset": result["offset"],
            "limit": result["limit"],
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

@router.post("/enrich-chunks-batch")
def enrich_document_chunks_batch(
    chunks_file: str,
    limit: int = 20,
    offset: int = 0,
    batch_size: int = 5,
    theme_id: str = "generic_pdf",
):
    """Enriquece chunks em lotes menores para controlar custo e tempo de execucao."""
    try:
        result = enrich_chunks_file_in_batches(
            chunks_file=chunks_file,
            limit=limit,
            offset=offset,
            batch_size=batch_size,
            theme_id=theme_id,
        )

        return {
            "message": "Chunks enriquecidos em lote com sucesso.",
            "document_id": result["document_id"],
            "enrichment_run_id": result["enrichment_run_id"],
            "enriched_chunks_file": result["enriched_chunks_file"],
            "total_original_chunks": result["total_original_chunks"],
            "total_enriched_chunks": result["total_enriched_chunks"],
            "offset": result["offset"],
            "limit": result["limit"],
            "batch_size": result["batch_size"],
            "preview": result["preview"],
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/enrich-all-chunks")
def enrich_all_document_chunks(
    chunks_file: str,
    batch_size: int = 10,
    theme_id: str = "generic_pdf",
):
    """Enriquece todos os chunks de um documento usando o tema informado."""
    try:
        result = enrich_all_chunks_file(
            chunks_file=chunks_file,
            batch_size=batch_size,
            theme_id=theme_id,
        )

        return {
            "message": "Todos os chunks foram enriquecidos com sucesso.",
            "document_id": result["document_id"],
            "enriched_chunks_file": result["enriched_chunks_file"],
            "total_original_chunks": result["total_original_chunks"],
            "total_enriched_chunks": result["total_enriched_chunks"],
            "enrichment_mode": result["enrichment_mode"],
            "enrichment_run_id": result["enrichment_run_id"],
            "batch_size": result["batch_size"],
            "preview": result["preview"],
            "theme_id": result["theme_id"],
            "theme_name": result["theme_name"],
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

@router.post("/smart-ingest/start")
def start_smart_ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    theme_id: str = Form("generic_pdf"),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    batch_size: int = Form(10),
    _admin_user: dict = Depends(require_admin_user),
):
    try:
        theme = find_theme_by_id(theme_id)

        if theme is None:
            raise ValueError("Tema informado nÃ£o encontrado.")

        saved_file = save_uploaded_file(file)

        job = create_processing_job(
            job_type="smart_ingest",
            payload={
                "original_filename": saved_file["original_filename"],
                "stored_filename": saved_file["stored_filename"],
                "file_path": saved_file["path"],
                "theme_id": theme["theme_id"],
                "theme_name": theme["name"],
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "batch_size": batch_size,
            },
        )

        background_tasks.add_task(
            run_smart_ingest_job,
            job_id=job["job_id"],
            saved_file=saved_file,
            theme_id=theme_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            batch_size=batch_size,
        )

        return {
            "message": "Processamento inteligente iniciado.",
            "job": job,
        }

    except ValueError as error:
        logger.warning("Falha de validaÃ§Ã£o ao iniciar smart ingest: %s", error)
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        logger.exception("Erro inesperado ao iniciar smart ingest")
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado ao iniciar smart ingest: {error}",
        )


