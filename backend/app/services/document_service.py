from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

UPLOAD_DIR = Path("app/storage/uploads")


def save_uploaded_file(file: UploadFile) -> dict:
    if not file.filename:
        raise ValueError("Arquivo sem nome.")

    file_extension = Path(file.filename).suffix.lower()

    if file_extension != ".pdf":
        raise ValueError("Apenas arquivos PDF são permitidos.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    generated_filename = f"{uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / generated_filename

    with file_path.open("wb") as buffer:
        buffer.write(file.file.read())

    return {
        "original_filename": file.filename,
        "stored_filename": generated_filename,
        "path": str(file_path),
    }


def extract_text_from_pdf(file_path: str) -> dict:
    path = Path(file_path)

    if not path.exists():
        raise ValueError("Arquivo não encontrado.")

    reader = PdfReader(str(path))

    pages = []

    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        pages.append(
            {
                "page": index,
                "text": text.strip(),
                "char_count": len(text),
            }
        )

    total_chars = sum(page["char_count"] for page in pages)

    return {
        "file_path": str(path),
        "total_pages": len(pages),
        "total_chars": total_chars,
        "pages": pages,
    }
