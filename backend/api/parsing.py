from __future__ import annotations

from typing import Optional
from io import BytesIO

from .models import Document
import re


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
            raw = "\n\n".join(text_parts)
            return _normalize_text(raw)
        except Exception:
            # Fall back to raw decode
            return _normalize_text(_safe_decode(blob))

    if _is_docx(doc):
        try:
            import docx  # type: ignore
            from io import BytesIO

            d = docx.Document(BytesIO(blob))
            lines: list[str] = []
            for p in d.paragraphs:
                txt = p.text or ""
                if not txt.strip():
                    lines.append("")
                    continue
                style = (p.style.name if p.style is not None else "") or ""
                # Detect numbered/bulleted lists via numbering properties
                is_list = False
                try:
                    is_list = p._p.pPr.numPr is not None  # type: ignore[attr-defined]
                except Exception:
                    is_list = False
                if style.startswith("List") or is_list:
                    lines.append(f"- {txt}")
                elif style.startswith("Heading"):
                    lines.append(txt.upper())
                else:
                    lines.append(txt)
            return _normalize_text("\n".join(lines))
        except Exception:
            return _normalize_text(_safe_decode(blob))

    # Default: assume text
    return _normalize_text(_safe_decode(blob))


def _normalize_text(s: str) -> str:
    """Normalize extracted text for better downstream prompts.
    - Unify bullet characters to '- '
    - Collapse excess blank lines
    - Strip trailing spaces per line
    """
    if not s:
        return ""
    # Replace common bullet glyphs with '- '
    s = s.replace("•", "- ").replace("◦", "- ").replace("▪", "- ")
    # Replace common long dashes with '-'
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    # Normalize whitespace at EOL
    s = "\n".join(line.rstrip() for line in s.splitlines())
    # Collapse >2 blank lines to max 2
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s
