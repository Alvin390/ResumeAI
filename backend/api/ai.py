import os
from typing import Tuple
import json
import time

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None

# AI wrapper with deterministic dry-run default.

DEFAULT_PROVIDER = "gemini"


def _bool_env(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


def choose_provider() -> str:
    # For now always prefer gemini when keys exist, otherwise deepseek, otherwise mock
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    return "mock"


def _gemini_generate(prompt: str, timeout: float = 20.0) -> str:
    if requests is None:
        raise RuntimeError("requests not installed; cannot call Gemini API")
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    # Extract text from candidates
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return json.dumps(data)[:4000]


def _deepseek_generate(prompt: str, timeout: float = 20.0) -> str:
    if requests is None:
        raise RuntimeError("requests not installed; cannot call DeepSeek API")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    url = "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Avoid fabrications. Use only provided facts."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(data)[:4000]


def _build_cover_prompt(jd_text: str, cv_text: str | None) -> str:
    return (
        "You are an expert career writer. Create a tailored, first-person cover letter optimized for ATS.\n"
        "Requirements:\n"
        "- Use ONLY facts from the CV and job description (no fabrications).\n"
        "- Tone: confident, concise, professional, and warm.\n"
        "- Structure:\n"
        "  1) Greeting (e.g., Dear Hiring Manager).\n"
        "  2) Opening (1–2 sentences aligning experience to role).\n"
        "  3) 2–4 bullet points with quantified impact aligned to JD.\n"
        "  4) Closing (availability + call to action).\n"
        "- Naturally include relevant JD keywords for ATS.\n"
        "- Length: 180–250 words.\n"
        "- Output plain text only.\n\n"
        "Job Description:\n" + (jd_text or "") + "\n\n"
        "Candidate CV (may be raw text):\n" + (cv_text or "") + "\n"
    )


def _build_cv_prompt(jd_text: str, cv_text: str | None, template: str) -> str:
    return (
        f"You are an expert resume writer. Generate an ATS-optimized CV in a '{template}' style using ONLY facts from the provided inputs.\n"
        "Requirements:\n"
        "- No fabrications; preserve truthful dates, titles, employers.\n"
        "- Use clear section headings in plain text (no tables/graphics):\n"
        "  NAME & CONTACT\n"
        "  SUMMARY (3–4 lines tailored to JD)\n"
        "  SKILLS (comma- or bullet-separated; JD-aligned keywords)\n"
        "  EXPERIENCE (Company — Title — Dates; 3–5 bullets with action + context + metric)\n"
        "  EDUCATION\n"
        "  CERTIFICATIONS (if any)\n"
        "- Prefer bullet points with strong verbs and measurable results when present.\n"
        "- Keep concise, remove redundancy, normalize formatting.\n"
        "- Output plain text only.\n\n"
        "Job Description:\n" + (jd_text or "") + "\n\n"
        "Baseline CV (may be raw text):\n" + (cv_text or "") + "\n"
    )


def generate_cover_letter(jd_text: str, cv_text: str | None = None) -> Tuple[str, str]:
    """
    Returns (provider_used, content)
    - Uses env AI_DRY_RUN=true (default) to return deterministic content without external calls.
    """
    provider = choose_provider()
    ai_dry_run = _bool_env("AI_DRY_RUN", True)

    if ai_dry_run or provider == "mock":
        content = (
            "Cover Letter (Stub) — ATS-style\n\n"
            f"Provider: {provider}\n\n"
            "Dear Hiring Manager,\n\n"
            "I’m excited to apply for this opportunity. My background aligns closely with the role and the outcomes you’re targeting.\n\n"
            "• Delivered results aligned with the JD (example placeholder).\n"
            "• Led initiatives with measurable impact (example placeholder).\n"
            "• Collaborated cross-functionally to improve KPIs (example placeholder).\n\n"
            "I’d welcome the chance to discuss how my experience can support your team.\n\n"
            "Sincerely,\nYour Name\n\n"
            "JD Excerpt:\n" + (jd_text or "").strip()[:500] + "\n\n"
            "CV Excerpt:\n" + (cv_text or "").strip()[:500] + "\n"
        )
        return provider, content

    # Real path with fallback
    prompt = _build_cover_prompt(jd_text or "", cv_text or "")
    timeout = float(os.environ.get("AI_TIMEOUT_SECONDS", "20"))
    errors = []
    if provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
        try:
            return "gemini", _gemini_generate(prompt, timeout)
        except Exception as e:  # fall through to deepseek
            errors.append(f"gemini:{e}")
            time.sleep(0.1)
    if os.environ.get("DEEPSEEK_API_KEY"):
        try:
            return "deepseek", _deepseek_generate(prompt, timeout)
        except Exception as e:
            errors.append(f"deepseek:{e}")
            time.sleep(0.1)
    # Final fallback
    content = (
        "Cover Letter (Fallback stub)\n\n" + "\n".join(errors) + "\n\n" + (jd_text or "")[:600]
    )
    return provider, content


def generate_cv(jd_text: str, cv_text: str | None = None, template: str = "classic") -> Tuple[str, str]:
    """
    Returns (provider_used, content) for a generated CV. Uses AI_DRY_RUN like above.
    """
    provider = choose_provider()
    ai_dry_run = _bool_env("AI_DRY_RUN", True)

    if ai_dry_run or provider == "mock":
        content = (
            "Generated CV (Stub) — ATS-style\n\n"
            f"Provider: {provider}\nTemplate: {template}\n\n"
            "NAME & CONTACT\nYour Name | email@example.com | City, ST | linkedin.com/in/username\n\n"
            "SUMMARY\n3–4 lines tailored to JD, highlighting scope, domain, and top strengths.\n\n"
            "SKILLS\nKeyword 1, Keyword 2, Keyword 3, Keyword 4\n\n"
            "EXPERIENCE\nCompany — Title — Dates\n"
            "• Action + context + metric (placeholder).\n"
            "• Action + context + metric (placeholder).\n\n"
            "EDUCATION\nInstitution — Degree — Year\n\n"
            "CERTIFICATIONS\nCertification (if any)\n\n"
            "JD Excerpt:\n" + (jd_text or "").strip()[:500] + "\n\n"
            "CV Excerpt:\n" + (cv_text or "").strip()[:500] + "\n"
        )
        return provider, content

    prompt = _build_cv_prompt(jd_text or "", cv_text or "", template)
    timeout = float(os.environ.get("AI_TIMEOUT_SECONDS", "20"))
    errors = []
    if provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
        try:
            return "gemini", _gemini_generate(prompt, timeout)
        except Exception as e:
            errors.append(f"gemini:{e}")
            time.sleep(0.1)
    if os.environ.get("DEEPSEEK_API_KEY"):
        try:
            return "deepseek", _deepseek_generate(prompt, timeout)
        except Exception as e:
            errors.append(f"deepseek:{e}")
            time.sleep(0.1)
    content = (
        "Generated CV (Fallback stub)\n\n" + "\n".join(errors) + "\n\n" + (jd_text or "")[:600]
    )
    return provider, content
