from __future__ import annotations

from typing import Optional
from io import BytesIO

from .models import Document


def _safe_decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except Exception:
        try:
            return data.decode("latin-1")
        except Exception:
            return ""


def _is_pdf(doc: Document) -> bool:
    if (doc.content_type or "").lower() in {"application/pdf"}:
        return True
    return (doc.file_name or "").lower().endswith(".pdf")


def _is_docx(doc: Document) -> bool:
    ct = (doc.content_type or "").lower()
    if ct in {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
        return True
    return (doc.file_name or "").lower().endswith(".docx")


def extract_text_from_document(doc: Optional[Document]) -> str:
    """
    Extracts text from a Document. Supports PDF, DOCX, and plaintext bytes.
    Returns empty string if no content.
    """
    if not doc or not doc.file_blob:
        return ""

    blob = bytes(doc.file_blob)

    if _is_pdf(doc):
        try:
            import pdfplumber  # type: ignore

            text_parts: list[str] = []
            with pdfplumber.open(BytesIO(blob)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    if t:
                        text_parts.append(t)
            return "\n\n".join(text_parts)
        except Exception:
            # Fall back to raw decode
            return _safe_decode(blob)

    if _is_docx(doc):
        try:
            import docx  # type: ignore
            from io import BytesIO

            d = docx.Document(BytesIO(blob))
            paras = [p.text for p in d.paragraphs if p.text]
            return "\n".join(paras)
        except Exception:
            return _safe_decode(blob)

    # Default: assume text
    return _safe_decode(blob)
