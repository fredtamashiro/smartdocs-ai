from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.document_service import extract_text_from_pdf, save_uploaded_file

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
