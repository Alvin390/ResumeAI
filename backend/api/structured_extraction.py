from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from .models import Document
from . import parsing

# Optional semantic cache integration
try:
    from .semantic_cache import get_from_cache, put_in_cache
except Exception:
    # Provide no-op fallbacks if cache module unavailable
    def get_from_cache(key: str, metadata: Optional[dict] = None, min_score: float = 0.0):
        return None
    def put_in_cache(key: str, content: str, metadata: Optional[dict] = None, quality: float = 0.5):
        return None


@dataclass
class Block:
    kind: str  # 'heading' | 'bullet' | 'paragraph' | 'blank'
    text: str


@dataclass
class Section:
    name: str
    blocks: List[Block] = field(default_factory=list)


@dataclass
class StructuredDoc:
    language: str
    sections: List[Section]

    def to_json(self) -> dict:
        return {
            "language": self.language,
            "sections": [
                {"name": s.name, "blocks": [{"kind": b.kind, "text": b.text} for b in s.blocks]}
                for s in self.sections
            ],
        }

    def to_html(self) -> str:
        parts: List[str] = [f"<article data-lang='{self.language}'>"]
        for sec in self.sections:
            parts.append(f"<section><h2>{_escape_html(sec.name)}</h2>")
            for b in sec.blocks:
                if b.kind == "heading":
                    parts.append(f"<h3>{_escape_html(b.text)}</h3>")
                elif b.kind == "bullet":
                    # We'll wrap bullets in a UL per contiguous run later; for simplicity, use <li> directly
                    parts.append(f"<li>{_escape_html(b.text[2:] if b.text.startswith('- ') else b.text)}</li>")
                elif b.kind == "paragraph":
                    parts.append(f"<p>{_escape_html(b.text)}</p>")
                else:
                    parts.append("<br/>")
            parts.append("</section>")
        parts.append("</article>")
        return "".join(parts)


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# Basic multilingual section header lexicon
SECTION_ALIASES: Dict[str, List[str]] = {
    "summary": ["summary", "profile", "about", "résumé", "resumen", "resumo", "über mich", "sobre"],
    "experience": ["experience", "work experience", "employment", "experiencia", "berufserfahrung", "experiência"],
    "education": ["education", "academics", "educación", "bildung", "formação"],
    "skills": ["skills", "technical skills", "competencies", "habilidades", "fähigkeiten", "competências"],
    "projects": ["projects", "proyectos", "projetos", "projekte"],
    "certifications": ["certifications", "licenses", "certificados", "zertifizierungen"],
    "contact": ["contact", "contact information", "contacto", "kontaktdaten", "contato"],
}

SECTION_ORDER = [
    "contact",
    "summary",
    "skills",
    "experience",
    "projects",
    "education",
    "certifications",
]


def detect_language(text: str) -> str:
    # Try optional langdetect
    try:
        from langdetect import detect  # type: ignore
        return detect(text or "")
    except Exception:
        pass
    # Heuristic: look for common words
    sample = (text or "").lower()[:5000]
    if any(w in sample for w in ["habilidades", "experiencia", "educación", "proyectos"]):
        return "es"
    if any(w in sample for w in ["fähigkeiten", "berufserfahrung", "bildung", "projekte"]):
        return "de"
    if any(w in sample for w in ["competências", "experiência", "formação", "projetos"]):
        return "pt"
    return "en"


def compute_doc_hash(doc: Document) -> str:
    h = hashlib.sha256()
    try:
        h.update(bytes(doc.file_blob or b""))
    except Exception:
        pass
    return h.hexdigest()


def _line_kind(line: str) -> str:
    s = line.strip()
    if not s:
        return "blank"
    if s.startswith("- ") or s.startswith("• "):
        return "bullet"
    # Treat all-caps short lines as headings
    if len(s) <= 80 and re.sub(r"[^A-Za-z]", "", s).isupper():
        return "heading"
    return "paragraph"


def _segment_lines_to_sections(lines: List[str], language: str) -> List[Section]:
    # Identify section headers by lexicon in multiple languages
    aliases = {
        key: [a.lower() for a in vals]
        for key, vals in SECTION_ALIASES.items()
    }
    sections: Dict[str, Section] = {name: Section(name=name, blocks=[]) for name in SECTION_ORDER}

    current: Optional[Section] = None

    def match_header(s: str) -> Optional[str]:
        low = s.lower().strip().strip(":")
        for name, words in aliases.items():
            for w in words:
                if low == w or low.startswith(w + ":"):
                    return name
        # Also accept pure heading tokens like "EXPERIENCE"
        cap = re.sub(r"[^A-Za-z]", "", s)
        for name in aliases.keys():
            if cap.lower() == name:
                return name
        return None

    for raw in lines:
        kind = _line_kind(raw)
        header_name = match_header(raw) if kind == "heading" or raw.strip().endswith(":") else None
        if header_name:
            current = sections.get(header_name)
            # Start a new logical header block under that section
            current.blocks.append(Block(kind="heading", text=raw.strip()))
            continue
        # If we haven't selected a section yet, try to infer early context
        if current is None:
            # Bias towards contact or summary for very first non-empty lines
            target = sections.get("contact") if any(t in raw.lower() for t in ["@", "+", "www", "linkedin", "github"]) else sections.get("summary")
            current = target
        # Append block
        current.blocks.append(Block(kind=kind, text=raw.rstrip()))

    # Prune empty sections
    ordered: List[Section] = [s for name in SECTION_ORDER if (s := sections[name]).blocks]
    return ordered


def extract_structured_document(doc: Document) -> StructuredDoc:
    # Cache lookup first
    doc_hash = compute_doc_hash(doc)
    cache_key = f"cv_structured:{doc_hash}"
    cached = None
    try:
        cached = get_from_cache(cache_key, metadata={"type": "structured_doc"}, min_score=0.99)
    except Exception:
        cached = None
    if cached and isinstance(cached, dict) and cached.get("content"):
        try:
            payload = json.loads(cached["content"])  # type: ignore[index]
            return StructuredDoc(
                language=payload.get("language", "en"),
                sections=[Section(name=s["name"], blocks=[Block(**b) for b in s.get("blocks", [])]) for s in payload.get("sections", [])],
            )
        except Exception:
            pass

    text = parsing.extract_text_from_document(doc)
    language = detect_language(text)
    lines = [ln for ln in text.splitlines()]
    sections = _segment_lines_to_sections(lines, language)
    structured = StructuredDoc(language=language, sections=sections)

    # Cache result
    try:
        put_in_cache(
            cache_key,
            json.dumps(structured.to_json()),
            metadata={"type": "structured_doc", "language": language, "doc_id": doc.id},
            quality=0.99,
        )
    except Exception:
        pass

    return structured


def extract_plain_text(doc: Document) -> str:
    return parsing.extract_text_from_document(doc)


def extract_structured_from_text(text: str) -> StructuredDoc:
    """Build a StructuredDoc from raw text input.
    Used when clients POST content directly for analysis instead of a stored Document.
    """
    language = detect_language(text or "")
    lines = [ln for ln in (text or "").splitlines()]
    sections = _segment_lines_to_sections(lines, language)
    return StructuredDoc(language=language, sections=sections)
