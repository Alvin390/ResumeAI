import os
from typing import Tuple, List, Dict
import json
import time
import re

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
    # Prefer Gemini, then DeepSeek, then Groq if keys exist; otherwise mock
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
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


def _groq_generate(prompt: str, timeout: float = 20.0) -> str:
    """Groq OpenAI-compatible Chat Completions."""
    if requests is None:
        raise RuntimeError("requests not installed; cannot call Groq API")
    api_key = os.environ.get("GROQ_API_KEY")
    model = os.environ.get("GROQ_MODEL", "llama-3.1-70b-versatile")
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a careful, high-precision career writing assistant. Use only provided facts."},
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


def _extract_contacts(cv_text: str | None) -> Dict[str, str]:
    if not cv_text:
        return {}
    text = cv_text.strip()
    # Name guess: first non-empty line, strip non-letters at ends
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    name_guess = re.sub(r"[^A-Za-z .\-]", "", first_line)[:120]
    # Email
    m_email = re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    email = m_email.group(0) if m_email else ""
    # Phone (simple)
    m_phone = re.search(r"(\+?\d[\d \-()]{7,}\d)", text)
    phone = m_phone.group(0) if m_phone else ""
    # LinkedIn / GitHub
    m_li = re.search(r"https?://(www\.)?linkedin\.com/[^\s]+", text, re.I)
    linkedin = m_li.group(0) if m_li else ""
    m_gh = re.search(r"https?://(www\.)?github\.com/[^\s]+", text, re.I)
    github = m_gh.group(0) if m_gh else ""
    return {"name": name_guess, "email": email, "phone": phone, "linkedin": linkedin, "github": github}


def _build_cover_prompt(jd_text: str, cv_text: str | None) -> str:
    contacts = _extract_contacts(cv_text)
    name = contacts.get("name", "")
    contact_line = ", ".join(x for x in [contacts.get("email"), contacts.get("phone"), contacts.get("linkedin") or contacts.get("github")] if x)
    return (
        "ROLE: Senior career writer crafting tailored materials for ATS.\n"
        "OBJECTIVE: Write a job-specific, first-person cover letter using ONLY facts from the provided CV and JD.\n"
        "STRICT CONSTRAINTS:\n"
        "- No fabrications or invented companies, titles, dates, or tools.\n"
        "- Prioritize relevance to the JD; naturally weave JD keywords present in the CV.\n"
        "- Tone: confident, concise, professional, warm.\n"
        "- Length: 180–250 words.\n"
        "- Format plain text (no markdown).\n"
        "- Greeting defaults to 'Dear Hiring Manager,' if company unknown.\n"
        "- Use one short opening paragraph and then 2–4 bullet points with quantified outcomes derived from CV facts.\n"
        f"CANDIDATE HEADER (use if present): {name} | {contact_line}\n\n"
        "JOB DESCRIPTION:\n" + (jd_text or "") + "\n\n"
        "CANDIDATE CV:\n" + (cv_text or "") + "\n"
    )


def _build_cv_prompt(jd_text: str, cv_text: str | None, template: str) -> str:
    contacts = _extract_contacts(cv_text)
    name = contacts.get("name", "")
    email = contacts.get("email", "")
    phone = contacts.get("phone", "")
    profile = " | ".join(x for x in [email, phone, contacts.get("linkedin") or contacts.get("github")] if x)
    return (
        f"ROLE: Expert resume writer. OBJECTIVE: Produce an ATS-optimized '{template}' style CV using ONLY facts from inputs.\n"
        "HARD RULES:\n"
        "- No fabrications; preserve truthful companies, titles, dates, technologies.\n"
        "- Use plain-text sections only (no tables/graphics).\n"
        "- Tight, impact-focused bullets: action + context + measurable outcome.\n"
        "- Prioritize JD-relevant achievements and keywords that already appear in the CV.\n"
        "- If some sections are missing in the CV, omit rather than invent.\n"
        "SECTIONS:\n"
        "  NAME & CONTACT\n  SUMMARY (3–4 lines tailored to JD)\n  SKILLS (grouped; JD-aligned)\n  EXPERIENCE (Company — Title — Dates; 3–5 bullets each)\n  EDUCATION\n  CERTIFICATIONS (if any)\n"
        f"CANDIDATE NAME: {name}\n"
        f"CANDIDATE CONTACT: {profile}\n\n"
        "JOB DESCRIPTION:\n" + (jd_text or "") + "\n\n"
        "CANDIDATE CV (raw):\n" + (cv_text or "") + "\n"
    )


def generate_cover_letter(jd_text: str, cv_text: str | None = None) -> Tuple[str, str, List[Dict]]:
    """
    Returns (provider_used, content)
    - Uses env AI_DRY_RUN=true (default) to return deterministic content without external calls.
    """
    provider = choose_provider()
    ai_dry_run = _bool_env("AI_DRY_RUN", True)
    trace: List[Dict] = []

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
        trace.append({"provider": provider, "status": "mock", "duration_ms": 0})
        return provider, content, trace

    # Real path with fallback
    prompt = _build_cover_prompt(jd_text or "", cv_text or "")
    timeout = float(os.environ.get("AI_TIMEOUT_SECONDS", "30"))
    errors = []
    # Attempt providers in order with timing and trace
    if os.environ.get("GEMINI_API_KEY"):
        t0 = time.perf_counter()
        try:
            out = _gemini_generate(prompt, timeout)
            trace.append({"provider": "gemini", "status": "ok", "duration_ms": int((time.perf_counter()-t0)*1000)})
            return "gemini", out, trace
        except Exception as e:  # fall through to deepseek
            dt = int((time.perf_counter()-t0)*1000)
            trace.append({"provider": "gemini", "status": "error", "error": str(e), "duration_ms": dt})
            errors.append(f"gemini:{e}")
            time.sleep(0.1)
    if os.environ.get("DEEPSEEK_API_KEY"):
        t1 = time.perf_counter()
        try:
            out = _deepseek_generate(prompt, timeout)
            trace.append({"provider": "deepseek", "status": "ok", "duration_ms": int((time.perf_counter()-t1)*1000)})
            return "deepseek", out, trace
        except Exception as e:
            dt = int((time.perf_counter()-t1)*1000)
            trace.append({"provider": "deepseek", "status": "error", "error": str(e), "duration_ms": dt})
            errors.append(f"deepseek:{e}")
            time.sleep(0.1)
    if os.environ.get("GROQ_API_KEY"):
        t2 = time.perf_counter()
        try:
            out = _groq_generate(prompt, timeout)
            trace.append({"provider": "groq", "status": "ok", "duration_ms": int((time.perf_counter()-t2)*1000)})
            return "groq", out, trace
        except Exception as e:
            dt = int((time.perf_counter()-t2)*1000)
            trace.append({"provider": "groq", "status": "error", "error": str(e), "duration_ms": dt})
            errors.append(f"groq:{e}")
            time.sleep(0.1)
    # Final fallback
    # Produce a clean, structured fallback without exposing provider errors to the user
    contacts = _extract_contacts(cv_text)
    name = contacts.get("name", "Your Name") or "Your Name"
    contact_line = ", ".join(x for x in [contacts.get("email"), contacts.get("phone"), contacts.get("linkedin") or contacts.get("github")] if x)
    jd_snip = (jd_text or "").strip()[:600]
    content = (
        f"Dear Hiring Manager,\n\n"
        f"I’m excited to apply for this role. My background aligns with your needs in the job description, "
        f"including relevant technologies and outcomes.\n\n"
        f"- Delivered results aligned to the JD using tools cited in my CV.\n"
        f"- Built and shipped features end-to-end with measurable impact.\n"
        f"- Collaborated cross-functionally to improve KPIs.\n\n"
        f"Sincerely,\n{name}\n{contact_line}\n\n"
        f"JD Excerpt:\n{jd_snip}\n"
    )
    return provider, content, trace


def generate_cv(jd_text: str, cv_text: str | None = None, template: str = "classic") -> Tuple[str, str, List[Dict]]:
    """
    Returns (provider_used, content) for a generated CV. Uses AI_DRY_RUN like above.
    """
    provider = choose_provider()
    ai_dry_run = _bool_env("AI_DRY_RUN", True)
    trace: List[Dict] = []

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
        trace.append({"provider": provider, "status": "mock", "duration_ms": 0})
        return provider, content, trace

    prompt = _build_cv_prompt(jd_text or "", cv_text or "", template)
    timeout = float(os.environ.get("AI_TIMEOUT_SECONDS", "30"))
    errors = []
    if os.environ.get("GEMINI_API_KEY"):
        t0 = time.perf_counter()
        try:
            out = _gemini_generate(prompt, timeout)
            trace.append({"provider": "gemini", "status": "ok", "duration_ms": int((time.perf_counter()-t0)*1000)})
            return "gemini", out, trace
        except Exception as e:
            dt = int((time.perf_counter()-t0)*1000)
            trace.append({"provider": "gemini", "status": "error", "error": str(e), "duration_ms": dt})
            errors.append(f"gemini:{e}")
            time.sleep(0.1)
    if os.environ.get("DEEPSEEK_API_KEY"):
        t1 = time.perf_counter()
        try:
            out = _deepseek_generate(prompt, timeout)
            trace.append({"provider": "deepseek", "status": "ok", "duration_ms": int((time.perf_counter()-t1)*1000)})
            return "deepseek", out, trace
        except Exception as e:
            dt = int((time.perf_counter()-t1)*1000)
            trace.append({"provider": "deepseek", "status": "error", "error": str(e), "duration_ms": dt})
            errors.append(f"deepseek:{e}")
            time.sleep(0.1)
    if os.environ.get("GROQ_API_KEY"):
        t2 = time.perf_counter()
        try:
            out = _groq_generate(prompt, timeout)
            trace.append({"provider": "groq", "status": "ok", "duration_ms": int((time.perf_counter()-t2)*1000)})
            return "groq", out, trace
        except Exception as e:
            dt = int((time.perf_counter()-t2)*1000)
            trace.append({"provider": "groq", "status": "error", "error": str(e), "duration_ms": dt})
            errors.append(f"groq:{e}")
            time.sleep(0.1)
    # Clean structured fallback CV without error dump
    contacts = _extract_contacts(cv_text)
    name = contacts.get("name", "YOUR NAME") or "YOUR NAME"
    profile = " | ".join(x for x in [contacts.get("email"), contacts.get("phone"), contacts.get("linkedin") or contacts.get("github")] if x)
    jd_snip = (jd_text or "").strip()[:600]
    content = (
        f"{name}\n{profile}\n\n"
        "SUMMARY\n"
        "Impact-focused professional aligned to the role, emphasizing relevant skills and achievements.\n\n"
        "SKILLS\n"
        "Core skills from the CV and JD.\n\n"
        "EXPERIENCE\n"
        "Company — Title — Dates\n"
        "- Action + context + metric.\n"
        "- Action + context + metric.\n\n"
        "EDUCATION\nInstitution — Degree — Year\n\n"
        "CERTIFICATIONS\n(if any)\n\n"
        f"JD Excerpt:\n{jd_snip}\n"
    )
    return provider, content, trace
