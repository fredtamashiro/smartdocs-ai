import re


def clean_extracted_text(text: str) -> str:
    if not text:
        return ""

    cleaned_text = text

    # Remove padrões estranhos comuns em alguns PDFs, como /gid00017
    cleaned_text = re.sub(r"/gid\d+", " ", cleaned_text)

    # Troca quebras de linha por espaço
    cleaned_text = cleaned_text.replace("\n", " ")

    # Remove múltiplos espaços
    cleaned_text = re.sub(r"\s+", " ", cleaned_text)

    # Corrige espaços antes de pontuação
    cleaned_text = re.sub(r"\s+([,.;:!?])", r"\1", cleaned_text)

    return cleaned_text.strip()
