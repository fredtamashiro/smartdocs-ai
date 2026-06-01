import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import require_api_key
from app.services.chunk_enrichment_service import (
    enrich_all_chunks_file,
    enrich_chunks_file,
    enrich_chunks_file_in_batches,
)
from app.services.chunk_service import save_chunks_to_json, split_text_into_chunks
from app.services.document_registry_service import (
    list_registered_documents,
    register_document,
    update_registered_document,
)
from app.services.document_service import extract_text_from_pdf, save_uploaded_file
from app.services.theme_service import find_theme_by_id
from app.services.vector_store_service import (
    index_chunks_in_vectorstore,
    index_enriched_chunks_in_vectorstore,
    search_similar_chunks,
)

from app.services.processing_job_service import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    create_processing_job,
    update_processing_job,
)

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path("app/storage/uploads").resolve()
CHUNKS_DIR = Path("app/storage/chunks").resolve()

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

        enriched_chunks = enrich_all_chunks_file(
            chunks_file=saved_chunks["chunks_file"],
            batch_size=batch_size,
            theme_id=theme_id,
        )

        update_processing_job(
            job_id,
            {
                "progress": 80,
                "current_step": "Indexando chunks enriquecidos no vector store",
                "partial_result": {
                    "chunks_file": saved_chunks["chunks_file"],
                    "enriched_chunks_file": enriched_chunks["enriched_chunks_file"],
                    "total_chunks": saved_chunks["total_chunks"],
                    "total_enriched_chunks": enriched_chunks["total_enriched_chunks"],
                },
            },
        )

        indexed_document = index_enriched_chunks_in_vectorstore(
            enriched_chunks_file=enriched_chunks["enriched_chunks_file"],
        )

        theme = find_theme_by_id(theme_id)

        if theme is None:
            raise ValueError("Tema informado não encontrado.")

        document_payload = {
            "original_filename": saved_file["original_filename"],
            "stored_filename": saved_file["stored_filename"],
            "file_path": saved_file["path"],
            "document_id": indexed_document["document_id"],
            "collection_name": indexed_document["collection_name"],
            "enriched_collection_name": indexed_document["collection_name"],
            "retrieval_mode": "enriched",
            "theme_id": theme["theme_id"],
            "theme_name": theme["name"],
            "total_pages": extracted_text["total_pages"],
            "total_chars": extracted_text["total_chars"],
            "total_chunks": saved_chunks["total_chunks"],
            "chunks_file": saved_chunks["chunks_file"],
            "enriched_chunks_file": enriched_chunks["enriched_chunks_file"],
        }

        registered_document = register_document(document_payload)

        update_processing_job(
            job_id,
            {
                "status": STATUS_COMPLETED,
                "progress": 100,
                "current_step": "Processamento concluído",
                "result": {
                    "document": registered_document,
                    "vectorstore_dir": indexed_document["vectorstore_dir"],
                    "total_indexed_documents": indexed_document.get(
                        "total_indexed_documents",
                        indexed_document.get("total_documents"),
                    ),
                    "total_skipped_chunks": indexed_document.get("total_skipped_chunks"),
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


@router.post("/ingest")
def ingest_document(
    file: UploadFile = File(...),
    theme_id: str = Form("automotive_manual"),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    _auth: None = Depends(require_api_key),
):
    """Faz upload, extrai texto, cria chunks, indexa e registra o documento."""
    try:
        theme = find_theme_by_id(theme_id)

        if theme is None:
            raise ValueError("Tema informado não encontrado.")

        saved_file = save_uploaded_file(file)

        extracted_text = extract_text_from_pdf(saved_file["path"])

        chunks = split_text_into_chunks(
            pages=extracted_text["pages"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        saved_chunks = save_chunks_to_json(
            chunks=chunks,
            source_file_path=extracted_text["file_path"],
        )

        indexed_document = index_chunks_in_vectorstore(
            chunks_file=saved_chunks["chunks_file"],
        )

        document_payload = {
            "original_filename": saved_file["original_filename"],
            "stored_filename": saved_file["stored_filename"],
            "file_path": saved_file["path"],
            "document_id": indexed_document["document_id"],
            "collection_name": indexed_document["collection_name"],
            "theme_id": theme["theme_id"],
            "theme_name": theme["name"],
            "total_pages": extracted_text["total_pages"],
            "total_chars": extracted_text["total_chars"],
            "total_chunks": saved_chunks["total_chunks"],
            "chunks_file": saved_chunks["chunks_file"],
        }

        registered_document = register_document(document_payload)

        return {
            "message": "Documento ingerido e indexado com sucesso.",
            "document": registered_document,
            "vectorstore_dir": indexed_document["vectorstore_dir"],
        }

    except ValueError as error:
        logger.warning("Falha de validacao ao ingerir documento: %s", error)
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        logger.exception("Erro inesperado ao ingerir documento")
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado ao ingerir documento: {error}",
        )


@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    _auth: None = Depends(require_api_key),
):
    """Salva o PDF enviado, sem processar chunks nem indexar no vector store."""
    try:
        saved_file = save_uploaded_file(file)

        return {
            "message": "Arquivo enviado com sucesso.",
            "document": saved_file,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/extract-text")
def extract_document_text(
    file_path: str,
    _auth: None = Depends(require_api_key),
):
    """Extrai o texto de um PDF ja salvo e retorna uma previa das paginas."""
    try:
        safe_file_path = ensure_path_inside_directory(
            path_value=file_path,
            base_dir=UPLOADS_DIR,
            label="file_path",
        )

        result = extract_text_from_pdf(safe_file_path)

        preview_pages = []

        for page in result["pages"][:3]:
            preview_pages.append(
                {
                    "page": page["page"],
                    "char_count": page["char_count"],
                    "preview": page["text"][:500],
                }
            )

        return {
            "message": "Texto extraído com sucesso.",
            "file_path": result["file_path"],
            "total_pages": result["total_pages"],
            "total_chars": result["total_chars"],
            "preview_pages": preview_pages,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


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


@router.post("/index")
def index_document_chunks(
    chunks_file: str,
    _auth: None = Depends(require_api_key),
):
    """Indexa um arquivo de chunks no vector store."""
    try:
        safe_chunks_file = ensure_path_inside_directory(
            path_value=chunks_file,
            base_dir=CHUNKS_DIR,
            label="chunks_file",
        )

        result = index_chunks_in_vectorstore(safe_chunks_file)

        return {
            "message": "Chunks indexados com sucesso no vector store.",
            "document_id": result["document_id"],
            "collection_name": result["collection_name"],
            "total_documents": result["total_documents"],
            "vectorstore_dir": result["vectorstore_dir"],
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/search")
def search_document_chunks(
    collection_name: str,
    query: str,
    k: int = 4,
    _auth: None = Depends(require_api_key),
):
    """Busca no vector store os chunks mais parecidos com a pergunta."""
    try:
        results = search_similar_chunks(
            collection_name=collection_name,
            query=query,
            k=k,
        )

        preview_results = []

        for item in results:
            preview_results.append(
                {
                    "page": item["metadata"].get("page"),
                    "chunk_index": item["metadata"].get("chunk_index"),
                    "score": item["score"],
                    "preview": item["content"][:500],
                    "metadata": item["metadata"],
                }
            )

        return {
            "message": "Busca semântica realizada com sucesso.",
            "collection_name": collection_name,
            "query": query,
            "total_results": len(results),
            "results": preview_results,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


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


@router.post("/index-enriched")
def index_enriched_document_chunks(
    enriched_chunks_file: str,
    register_as_active: bool = False,
):
    """Indexa chunks enriquecidos e opcionalmente os ativa para uso no chat."""
    try:
        result = index_enriched_chunks_in_vectorstore(enriched_chunks_file)

        updated_document = None

        if register_as_active:
            updated_document = update_registered_document(
                document_id=result["document_id"],
                updates={
                    "enriched_collection_name": result["collection_name"],
                    "retrieval_mode": "enriched",
                    "enriched_chunks_file": enriched_chunks_file,
                },
            )

        return {
            "message": "Chunks enriquecidos indexados com sucesso no vector store.",
            "document_id": result["document_id"],
            "collection_name": result["collection_name"],
            "total_documents": result["total_documents"],
            "vectorstore_dir": result["vectorstore_dir"],
            "registered_as_active": register_as_active,
            "document": updated_document,
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
    _auth: None = Depends(require_api_key),
):
    try:
        theme = find_theme_by_id(theme_id)

        if theme is None:
            raise ValueError("Tema informado não encontrado.")

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
        logger.warning("Falha de validação ao iniciar smart ingest: %s", error)
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        logger.exception("Erro inesperado ao iniciar smart ingest")
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado ao iniciar smart ingest: {error}",
        )
