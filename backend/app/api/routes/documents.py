from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.chunk_service import save_chunks_to_json, split_text_into_chunks
from app.services.document_service import extract_text_from_pdf, save_uploaded_file
from app.services.vector_store_service import (
    index_chunks_in_vectorstore,
    search_similar_chunks,
)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post("/upload")
def upload_document(file: UploadFile = File(...)):
    try:
        saved_file = save_uploaded_file(file)

        return {
            "message": "Arquivo enviado com sucesso.",
            "document": saved_file,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/extract-text")
def extract_document_text(file_path: str):
    try:
        result = extract_text_from_pdf(file_path)

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
def chunk_document(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    try:
        extracted_text = extract_text_from_pdf(file_path)

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
def process_document(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    try:
        extracted_text = extract_text_from_pdf(file_path)

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
def index_document_chunks(chunks_file: str):
    try:
        result = index_chunks_in_vectorstore(chunks_file)

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
def search_document_chunks(collection_name: str, query: str, k: int = 4):
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
