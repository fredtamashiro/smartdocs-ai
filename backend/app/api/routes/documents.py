import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import require_api_key
from app.services.chunk_enrichment_service import enrich_chunks_file
from app.services.chunk_service import save_chunks_to_json, split_text_into_chunks
from app.services.document_service import extract_text_from_pdf, save_uploaded_file
from app.services.vector_store_service import (
    index_chunks_in_vectorstore,
    search_similar_chunks,
)

from app.services.document_registry_service import (
    list_registered_documents,
    register_document,
)

logger = logging.getLogger(__name__)
UPLOADS_DIR = Path("app/storage/uploads").resolve()
CHUNKS_DIR = Path("app/storage/chunks").resolve()

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


def ensure_path_inside_directory(path_value: str, base_dir: Path, label: str) -> str:
    path = Path(path_value).resolve()

    try:
        path.relative_to(base_dir)
    except ValueError as error:
        raise ValueError(f"{label} deve estar dentro de {base_dir}.") from error

    return str(path)


@router.get("")
def list_documents():
    documents = list_registered_documents()

    return {
        "total": len(documents),
        "documents": documents,
    }

@router.post("/ingest")
def ingest_document(
    file: UploadFile = File(...),
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    _auth: None = Depends(require_api_key),
):
    try:
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
def enrich_document_chunks(chunks_file: str, limit: int = 10, offset: int = 0):
    try:
        result = enrich_chunks_file(
            chunks_file=chunks_file,
            limit=limit,
            offset=offset
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
