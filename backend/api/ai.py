import os
import re
import time
import json
import hashlib
import requests
import html
import bleach
from typing import Dict, List, Tuple, Optional
from functools import lru_cache
from collections import defaultdict
import threading
import logging

# AI wrapper with deterministic dry-run default.

DEFAULT_PROVIDER = "gemini"

# Simple in-memory cache for AI responses
_ai_cache = {}
CACHE_MAX_SIZE = 100
CACHE_TTL_SECONDS = 3600  # 1 hour

# AI provider health tracking
PROVIDER_HEALTH = {
    "gemini": {"failures": 0, "last_success": None, "last_failure": None},
    "deepseek": {"failures": 0, "last_success": None, "last_failure": None},
    "groq": {"failures": 0, "last_success": None, "last_failure": None},
}

# Rate limiting tracking
RATE_LIMITS = defaultdict(lambda: {"requests": [], "daily_count": 0, "last_reset": time.time()})
RATE_LIMIT_LOCK = threading.Lock()

# Security configuration
MAX_INPUT_LENGTH = 50000  # Maximum characters for input text
ALLOWED_HTML_TAGS = []  # No HTML allowed in AI inputs
SUSPICIOUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'javascript:',
    r'data:text/html',
    r'vbscript:',
    r'onload\s*=',
    r'onerror\s*=',
]

# Logging configuration
logger = logging.getLogger(__name__)

# Content quality scoring weights
QUALITY_WEIGHTS = {
    "keyword_density": 0.25,
    "readability": 0.20,
    "structure": 0.20,
    "quantification": 0.15,
    "relevance": 0.10,
    "length": 0.10
}

# A/B testing prompt variations
PROMPT_VARIANTS = {
    "cover_letter": {
        "standard": "Write a compelling, job-specific cover letter",
        "story_driven": "Craft a narrative-driven cover letter that tells the candidate's professional story",
        "achievement_focused": "Create an achievement-focused cover letter highlighting quantified results",
        "problem_solution": "Write a problem-solution cover letter addressing the employer's key challenges"
    },
    "cv": {
        "standard": "Create a professional CV optimized for ATS systems",
        "impact_focused": "Build an impact-driven CV emphasizing measurable business outcomes",
        "skills_first": "Develop a skills-first CV highlighting core competencies upfront",
        "hybrid": "Design a hybrid CV balancing chronological experience with skills emphasis"
    }
}

# Industry-specific templates and keywords
INDUSTRY_TEMPLATES = {
    "tech": {
        "keywords": ["software", "development", "programming", "technical", "engineering", "agile", "scrum", "API", "database", "cloud"],
        "cv_focus": "technical skills, project outcomes, system architecture",
        "cover_tone": "technical precision with innovation focus",
        "quality_indicators": ["metrics", "performance", "scalability", "optimization", "automation"]
    },
    "finance": {
        "keywords": ["financial", "analysis", "investment", "risk", "compliance", "audit", "portfolio", "trading", "banking", "accounting"],
        "cv_focus": "quantified financial impact, regulatory knowledge, risk management",
        "cover_tone": "analytical precision with business acumen",
        "quality_indicators": ["ROI", "revenue", "cost savings", "compliance", "risk reduction"]
    },
    "healthcare": {
        "keywords": ["patient", "clinical", "medical", "healthcare", "treatment", "diagnosis", "compliance", "safety", "quality", "research"],
        "cv_focus": "patient outcomes, clinical expertise, regulatory compliance",
        "cover_tone": "professional care with evidence-based approach",
        "quality_indicators": ["patient outcomes", "safety", "quality improvement", "research", "protocols"]
    },
    "marketing": {
        "keywords": ["marketing", "brand", "campaign", "digital", "social media", "analytics", "conversion", "engagement", "ROI", "growth"],
        "cv_focus": "campaign results, growth metrics, brand impact",
        "cover_tone": "creative strategy with data-driven results",
        "quality_indicators": ["conversion rates", "engagement", "brand awareness", "lead generation", "growth"]
    },
    "sales": {
        "keywords": ["sales", "revenue", "targets", "pipeline", "conversion", "client", "relationship", "negotiation", "quota", "growth"],
        "cv_focus": "sales achievements, quota performance, client relationships",
        "cover_tone": "results-driven with relationship focus",
        "quality_indicators": ["quota attainment", "revenue growth", "client retention", "pipeline", "closing rate"]
    },
    "general": {
        "keywords": ["professional", "experience", "skills", "achievement", "leadership", "collaboration", "problem-solving", "communication", "results", "impact"],
        "cv_focus": "transferable skills, leadership experience, measurable outcomes",
        "cover_tone": "professional competence with adaptability",
        "quality_indicators": ["leadership", "team building", "process improvement", "efficiency", "collaboration"]
    }
}


def _bool_env(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


class AIConfig:
    """Centralized configuration management for AI system."""
    
    def __init__(self):
        self.providers = {
            "gemini": {
                "api_key": os.environ.get("GEMINI_API_KEY"),
                "model": os.environ.get("GEMINI_MODEL", "gemini-pro"),
                "enabled": _bool_env("GEMINI_ENABLED", True),
                "priority": int(os.environ.get("GEMINI_PRIORITY", "1")),
                "rate_limit_hourly": int(os.environ.get("GEMINI_RATE_LIMIT_HOURLY", "100")),
                "rate_limit_daily": int(os.environ.get("GEMINI_RATE_LIMIT_DAILY", "1000")),
            },
            "deepseek": {
                "api_key": os.environ.get("DEEPSEEK_API_KEY"),
                "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
                "enabled": _bool_env("DEEPSEEK_ENABLED", True),
                "priority": int(os.environ.get("DEEPSEEK_PRIORITY", "2")),
                "rate_limit_hourly": int(os.environ.get("DEEPSEEK_RATE_LIMIT_HOURLY", "200")),
                "rate_limit_daily": int(os.environ.get("DEEPSEEK_RATE_LIMIT_DAILY", "2000")),
            },
            "groq": {
                "api_key": os.environ.get("GROQ_API_KEY"),
                "model": os.environ.get("GROQ_MODEL", "llama3-8b-8192"),
                "enabled": _bool_env("GROQ_ENABLED", True),
                "priority": int(os.environ.get("GROQ_PRIORITY", "3")),
                "rate_limit_hourly": int(os.environ.get("GROQ_RATE_LIMIT_HOURLY", "500")),
                "rate_limit_daily": int(os.environ.get("GROQ_RATE_LIMIT_DAILY", "5000")),
            }
        }
        
        self.security = {
            "max_input_length": int(os.environ.get("AI_MAX_INPUT_LENGTH", "50000")),
            "sanitize_html": _bool_env("AI_SANITIZE_HTML", True),
            "check_suspicious_patterns": _bool_env("AI_CHECK_SUSPICIOUS_PATTERNS", True),
        }
        
        self.cache = {
            "enabled": _bool_env("AI_CACHE_ENABLED", True),
            "max_size": int(os.environ.get("AI_CACHE_MAX_SIZE", "100")),
            "ttl_seconds": int(os.environ.get("AI_CACHE_TTL_SECONDS", "3600")),
        }
        
        self.quality = {
            "min_score_threshold": float(os.environ.get("AI_MIN_QUALITY_SCORE", "0.6")),
            "enable_quality_filtering": _bool_env("AI_ENABLE_QUALITY_FILTERING", True),
        }
        
        self.fallback = {
            "enable_fallback_content": _bool_env("AI_ENABLE_FALLBACK_CONTENT", True),
            "fallback_quality_threshold": float(os.environ.get("AI_FALLBACK_QUALITY_THRESHOLD", "0.4")),
        }
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of enabled providers with API keys, sorted by priority."""
        enabled = []
        for name, config in self.providers.items():
            if config["enabled"] and config["api_key"]:
                enabled.append((name, config["priority"]))
        
        # Sort by priority (lower number = higher priority)
        enabled.sort(key=lambda x: x[1])
        return [name for name, _ in enabled]
    
    def get_provider_config(self, provider: str) -> Dict:
        """Get configuration for specific provider."""
        return self.providers.get(provider, {})


# Global configuration instance
ai_config = AIConfig()


def _sanitize_input(text: str) -> str:
    """Sanitize input text to prevent injection attacks."""
    if not text:
        return ""
    
    # Use configuration for security settings
    max_length = ai_config.security["max_input_length"]
    
    # Limit input length
    if len(text) > max_length:
        text = text[:max_length]
    
    if ai_config.security["sanitize_html"]:
        # HTML escape
        text = html.escape(text)
        
        # Remove any HTML tags
        text = bleach.clean(text, tags=ALLOWED_HTML_TAGS, strip=True)
    
    if ai_config.security["check_suspicious_patterns"]:
        # Check for suspicious patterns
        for pattern in SUSPICIOUS_PATTERNS:
            try:
                if re.search(pattern, text, re.I | re.DOTALL):
                    logger.warning(f"Suspicious pattern detected: {pattern}")
                    return True
            except re.error as e:
                logger.error(f"Regex error in suspicious pattern check: {e}")
                continue
        
        return text.strip()


def _check_rate_limit(provider: str) -> bool:
    """Check if provider is within rate limits."""
    with RATE_LIMIT_LOCK:
        now = time.time()
        provider_limits = RATE_LIMITS[provider]
        
        # Reset daily counter if needed (24 hours)
        if now - provider_limits["last_reset"] > 86400:
            provider_limits["daily_count"] = 0
            provider_limits["requests"] = []
            provider_limits["last_reset"] = now
        
        # Remove requests older than 1 hour
        provider_limits["requests"] = [
            req_time for req_time in provider_limits["requests"]
            if now - req_time < 3600
        ]
        
        # Get rate limits from configuration
        provider_config = ai_config.get_provider_config(provider)
        provider_limit = {
            "hourly": provider_config.get("rate_limit_hourly", 50),
            "daily": provider_config.get("rate_limit_daily", 500)
        }
        
        # Check limits
        if len(provider_limits["requests"]) >= provider_limit["hourly"]:
            return False
        if provider_limits["daily_count"] >= provider_limit["daily"]:
            return False
        
        # Record this request
        provider_limits["requests"].append(now)
        provider_limits["daily_count"] += 1
        
        return True


def _log_ai_request(provider: str, prompt_type: str, success: bool, duration_ms: int, error: str = None):
    """Log AI request for monitoring and debugging."""
    log_data = {
        "timestamp": time.time(),
        "provider": provider,
        "prompt_type": prompt_type,
        "success": success,
        "duration_ms": duration_ms,
        "error": error[:200] if error else None
    }
    
    if success:
        logger.info(f"AI request successful: {provider} {prompt_type} ({duration_ms}ms)")
    else:
        logger.error(f"AI request failed: {provider} {prompt_type} - {error}")
    
    # In production, this could be sent to monitoring service
    # monitoring_service.log_ai_request(log_data)


def _get_cache_key(prompt: str, provider: str = "") -> str:
    """Generate cache key for AI responses."""
    content = f"{provider}:{prompt}"
    return hashlib.md5(content.encode()).hexdigest()


def _get_cached_response(cache_key: str) -> Optional[str]:
    """Get cached AI response if valid."""
    if not ai_config.cache["enabled"]:
        return None
        
    if cache_key in _ai_cache:
        cached_data = _ai_cache[cache_key]
        # Check if cache entry is still valid
        if time.time() - cached_data["timestamp"] < ai_config.cache["ttl_seconds"]:
            return cached_data["response"]
        else:
            # Remove expired entry
            del _ai_cache[cache_key]
    return None


def _cache_response(cache_key: str, response: str) -> None:
    """Cache AI response with size limit."""
    if not ai_config.cache["enabled"]:
        return
        
    # Simple LRU: remove oldest if at capacity
    if len(_ai_cache) >= ai_config.cache["max_size"]:
        oldest_key = min(_ai_cache.keys(), key=lambda k: _ai_cache[k]["timestamp"])
        del _ai_cache[oldest_key]
    
    _ai_cache[cache_key] = {
        "response": response,
        "timestamp": time.time()
    }


def _update_provider_health(provider: str, success: bool) -> None:
    """Update provider health tracking."""
    now = time.time()
    if success:
        PROVIDER_HEALTH[provider]["last_success"] = now
        PROVIDER_HEALTH[provider]["failures"] = max(0, PROVIDER_HEALTH[provider]["failures"] - 1)
    else:
        PROVIDER_HEALTH[provider]["last_failure"] = now
        PROVIDER_HEALTH[provider]["failures"] += 1


def _get_provider_priority() -> List[str]:
    """Get provider priority list based on health and configuration with error handling."""
    providers = []
    
    try:
        # Add enabled providers based on environment variables
        if _bool_env("GEMINI_ENABLED", True) and os.environ.get("GEMINI_API_KEY"):
            providers.append("gemini")
        if _bool_env("DEEPSEEK_ENABLED", True) and os.environ.get("DEEPSEEK_API_KEY"):
            providers.append("deepseek")
        if _bool_env("GROQ_ENABLED", True) and os.environ.get("GROQ_API_KEY"):
            providers.append("groq")
        
        # Sort by health (fewer failures first) with error handling
        try:
            providers.sort(key=lambda p: PROVIDER_HEALTH.get(p, {"failures": 999})["failures"])
        except (KeyError, TypeError):
            # If health data is corrupted, use original order
            pass
        
        return providers
    except Exception:
        # Fallback to all available providers if configuration fails
        fallback_providers = []
        if os.environ.get("GEMINI_API_KEY"):
            fallback_providers.append("gemini")
        if os.environ.get("DEEPSEEK_API_KEY"):
            fallback_providers.append("deepseek")
        if os.environ.get("GROQ_API_KEY"):
            fallback_providers.append("groq")
        return fallback_providers


def choose_provider() -> str:
    """Choose best available provider based on health."""
    providers = _get_provider_priority()
    return providers[0] if providers else "mock"


def _make_request_with_retry(func, *args, max_retries: int = 3, base_delay: float = 1.0) -> str:
    """Make API request with exponential backoff retry logic and comprehensive error handling."""
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            result = func(*args)
            if result:  # Ensure we got a valid response
                return result
            else:
                raise ValueError("Empty response from API")
        except Exception as e:
            last_exception = e
            if attempt == max_retries - 1:
                # Log the final failure
                logger.error(f"API request failed after {max_retries} attempts: {str(e)}")
                raise e
            
            # Calculate exponential backoff delay
            delay = base_delay * (2 ** attempt)
            logger.warning(f"API request attempt {attempt + 1} failed, retrying in {delay}s: {str(e)}")
            time.sleep(delay)
    
    # This should never be reached, but just in case
    raise last_exception or Exception("Unknown error in retry logic")


def _gemini_generate(prompt: str, timeout: float = 30.0) -> str:
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


def _deepseek_generate(prompt: str, timeout: float = 30.0) -> str:
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


def _groq_generate(prompt: str, timeout: float = 30.0) -> str:
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


@lru_cache(maxsize=128)
def _detect_industry(jd_text: str) -> str:
    """Detect industry from job description text with robust error handling."""
    if not jd_text:
        return "general"
    
    try:
        text_lower = jd_text.lower()
        industry_scores = {}
        
        for industry, config in INDUSTRY_TEMPLATES.items():
            try:
                score = 0
                keywords = config.get("keywords", [])
                for keyword in keywords:
                    if keyword.lower() in text_lower:
                        score += 1
                
                # Normalize by keyword count
                industry_scores[industry] = score / len(keywords) if keywords else 0
            except (AttributeError, TypeError, ZeroDivisionError):
                industry_scores[industry] = 0
        
        # Return industry with highest score, or "general" if no matches
        if not industry_scores or max(industry_scores.values()) == 0:
            return "general"
        
        return max(industry_scores.items(), key=lambda x: x[1])[0]
    except Exception:
        return "general"


def _calculate_content_quality_score(content: str, jd_text: str, industry: str, content_type: str) -> Dict[str, float]:
    """Calculate comprehensive quality score for generated content."""
    if not content:
        return {"overall": 0.0, "keyword_density": 0.0, "readability": 0.0, "structure": 0.0, "quantification": 0.0, "relevance": 0.0, "length": 0.0}
    
    try:
        industry_config = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["general"])
        scores = {}
    except Exception:
        # Fallback if industry templates are corrupted
        return {"overall": 0.5, "keyword_density": 0.5, "readability": 0.5, "structure": 0.5, "quantification": 0.5, "relevance": 0.5, "length": 0.5}
    
    # 1. Keyword Density Score (0-1)
    jd_keywords = set(word.lower() for word in jd_text.split() if len(word) > 3) if jd_text else set()
    industry_keywords = set(keyword.lower() for keyword in industry_config["keywords"])
    content_words = set(word.lower().strip('.,!?;:') for word in content.split())
    
    jd_matches = len(jd_keywords.intersection(content_words))
    industry_matches = len(industry_keywords.intersection(content_words))
    total_possible = len(jd_keywords) + len(industry_keywords)
    
    scores["keyword_density"] = min(1.0, (jd_matches * 2 + industry_matches) / max(1, total_possible)) if total_possible > 0 else 0.5
    
    # 2. Readability Score (based on sentence length and complexity)
    try:
        sentences = re.split(r'[.!?]+', content)
        valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    except re.error:
        scores["readability"] = 0.5
        valid_sentences = []
    
    if valid_sentences:
        avg_sentence_length = sum(len(s.split()) for s in valid_sentences) / len(valid_sentences)
        # Optimal range: 15-25 words per sentence
        if 15 <= avg_sentence_length <= 25:
            scores["readability"] = 1.0
        elif 10 <= avg_sentence_length <= 30:
            scores["readability"] = 0.8
        else:
            scores["readability"] = 0.6
    else:
        scores["readability"] = 0.0
    
    # 3. Structure Score (based on content type)
    if content_type == "cover_letter":
        # Check for greeting, body paragraphs, closing with error handling
        try:
            has_greeting = bool(re.search(r'dear\s+\w+', content, re.I))
            has_closing = bool(re.search(r'(sincerely|regards|best)', content, re.I))
            has_bullets = bool(re.search(r'[•\-\*]', content))
            paragraph_count = len([p for p in content.split('\n\n') if len(p.strip()) > 20])
        except re.error:
            scores["structure"] = 0.5
            has_greeting = has_closing = has_bullets = False
            paragraph_count = 0
        
        structure_score = 0.0
        if has_greeting: structure_score += 0.3
        if has_closing: structure_score += 0.3
        if has_bullets: structure_score += 0.2
        if 2 <= paragraph_count <= 4: structure_score += 0.2
        
        scores["structure"] = min(1.0, structure_score)
    
    elif content_type == "cv":
        # Check for sections with error handling
        try:
            sections = ['summary', 'experience', 'education', 'skills']
            section_matches = sum(1 for section in sections if section.lower() in content.lower())
            has_contact = bool(re.search(r'@|\(\d{3}\)', content))
            has_bullets = bool(re.search(r'[•\-\*]', content))
        except re.error:
            scores["structure"] = 0.5
            section_matches = 0
            has_contact = has_bullets = False
        
        structure_score = (section_matches / len(sections)) * 0.6
        if has_contact: structure_score += 0.2
        if has_bullets: structure_score += 0.2
        
        scores["structure"] = min(1.0, structure_score)
    else:
        scores["structure"] = 0.5
    
    # 4. Quantification Score (presence of numbers, percentages, metrics)
    try:
        quantifiers = re.findall(r'\b\d+(?:[.,]\d+)?(?:%|\$|k|million|billion)?\b', content, re.I)
        quality_indicators = industry_config.get("quality_indicators", [])
        indicator_matches = sum(1 for indicator in quality_indicators if indicator.lower() in content.lower())
    except (re.error, AttributeError):
        quantifiers = []
        indicator_matches = 0
    
    quant_score = min(1.0, len(quantifiers) * 0.2 + indicator_matches * 0.1)
    scores["quantification"] = quant_score
    
    # 5. Relevance Score (alignment with job requirements)
    if jd_text:
        # Extract key requirements/skills from JD with error handling
        requirement_patterns = [
            r'(?:require|need|must have|should have)[:\s]*([^\n.]{20,100})',
            r'(?:skills|qualifications|experience)[:\s]*([^\n.]{20,100})'
        ]
        
        jd_requirements = []
        for pattern in requirement_patterns:
            try:
                matches = re.findall(pattern, jd_text, re.I)
                jd_requirements.extend(matches)
            except re.error:
                continue
        
        if jd_requirements:
            relevance_matches = 0
            for req in jd_requirements:
                req_words = set(word.lower() for word in req.split() if len(word) > 3)
                if req_words.intersection(content_words):
                    relevance_matches += 1
            
            scores["relevance"] = min(1.0, relevance_matches / len(jd_requirements))
        else:
            scores["relevance"] = 0.7  # Default if no requirements found
    else:
        scores["relevance"] = 0.5
    
    # 6. Length Score (appropriate length for content type)
    word_count = len(content.split())
    
    if content_type == "cover_letter":
        # Optimal: 250-400 words
        if 250 <= word_count <= 400:
            scores["length"] = 1.0
        elif 200 <= word_count <= 500:
            scores["length"] = 0.8
        elif 150 <= word_count <= 600:
            scores["length"] = 0.6
        else:
            scores["length"] = 0.4
    elif content_type == "cv":
        # Optimal: 300-800 words
        if 300 <= word_count <= 800:
            scores["length"] = 1.0
        elif 200 <= word_count <= 1000:
            scores["length"] = 0.8
        else:
            scores["length"] = 0.6
    else:
        scores["length"] = 0.7
    
    # Calculate overall score with error handling
    try:
        scores["overall"] = sum(scores[metric] * QUALITY_WEIGHTS[metric] for metric in QUALITY_WEIGHTS.keys())
    except (KeyError, TypeError):
        scores["overall"] = sum(scores.values()) / len(scores) if scores else 0.0
    
    return scores


def _select_prompt_variant(industry: str, content_type: str, user_preferences: Dict = None) -> str:
    """Select optimal prompt variant based on industry and A/B testing results."""
    # Simple A/B testing logic - in production, this would use historical performance data
    variants = PROMPT_VARIANTS.get(content_type, {})
    
    if not variants:
        return "standard"
    
    # Industry-specific variant selection
    if industry == "tech":
        return "achievement_focused" if content_type == "cover_letter" else "skills_first"
    elif industry == "finance":
        return "problem_solution" if content_type == "cover_letter" else "impact_focused"
    elif industry == "sales":
        return "story_driven" if content_type == "cover_letter" else "impact_focused"
    elif industry == "healthcare":
        return "achievement_focused" if content_type == "cover_letter" else "hybrid"
    else:
        return "standard"


def _score_name_candidate(name: str, context_lines: List[str]) -> float:
    """Score a potential name candidate based on various heuristics."""
    if not name or len(name) < 2:
        return 0.0
    
    score = 0.5  # Base score
    
    # Length scoring (optimal 10-40 chars)
    if 10 <= len(name) <= 40:
        score += 0.2
    elif len(name) < 10:
        score -= 0.1
    elif len(name) > 50:
        score -= 0.3
    
    # Word count scoring (2-4 words is typical)
    words = name.split()
    if 2 <= len(words) <= 4:
        score += 0.2
    elif len(words) == 1:
        score -= 0.1
    elif len(words) > 4:
        score -= 0.2
    
    # Capitalization patterns (proper names are capitalized)
    if name.istitle():
        score += 0.2
    elif name.isupper() and len(words) <= 3:
        score += 0.1  # All caps might be acceptable
    elif name.islower():
        score -= 0.3
    
    # Common name patterns
    if re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+$", name):  # First Last
        score += 0.2
    if re.match(r"^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+$", name):  # First M. Last
        score += 0.2
    
    # Penalize business/title indicators
    business_terms = ["inc", "ltd", "corp", "llc", "company", "enterprises", "solutions", "consulting"]
    if any(term in name.lower() for term in business_terms):
        score -= 0.4
    
    # Penalize document terms
    doc_terms = ["resume", "cv", "curriculum", "vitae", "profile", "summary"]
    if any(term in name.lower() for term in doc_terms):
        score -= 0.5
    
    # Position bonus (earlier in document is better)
    line_position = next((i for i, line in enumerate(context_lines) if name in line), 10)
    if line_position <= 2:
        score += 0.1
    elif line_position <= 5:
        score += 0.05
    
    return max(0.0, min(1.0, score))


def _validate_email(email: str) -> Tuple[bool, float]:
    """Validate email and return confidence score."""
    if not email:
        return False, 0.0
    
    # Basic format validation with error handling
    try:
        if not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$", email):
            return False, 0.0
    except re.error:
        return False, 0.0
    
    score = 0.7  # Base score for valid format
    
    # Domain scoring
    domain = email.split('@')[1].lower()
    
    # Common professional domains
    professional_domains = ['gmail.com', 'outlook.com', 'yahoo.com', 'hotmail.com', 'icloud.com']
    if domain in professional_domains:
        score += 0.2
    
    # Corporate domains (has company indicators)
    if any(indicator in domain for indicator in ['.com', '.org', '.net', '.edu', '.gov']):
        if domain not in professional_domains:
            score += 0.1  # Likely corporate email
    
    # Penalize suspicious patterns with error handling
    try:
        if re.search(r'\d{4,}', email):  # Too many consecutive digits
            score -= 0.1
    except re.error:
        pass
    
    if email.count('.') > 3:  # Too many dots
        score -= 0.1
    
    return True, min(1.0, score)


def _validate_phone(phone: str) -> Tuple[bool, float, str]:
    """Validate phone number and return confidence score with normalized format."""
    if not phone:
        return False, 0.0, ""
    
    # Remove all non-digit characters for analysis
    digits_only = re.sub(r'\D', '', phone)
    
    # Length validation
    if len(digits_only) < 7 or len(digits_only) > 15:
        return False, 0.0, ""
    
    score = 0.6  # Base score
    
    # US/Canada format (10-11 digits)
    if len(digits_only) == 10:
        score += 0.3
        normalized = f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
    elif len(digits_only) == 11 and digits_only[0] == '1':
        score += 0.2
        normalized = f"+1 ({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"
    else:
        # International format
        score += 0.1
        normalized = phone  # Keep original formatting for international
    
    # Pattern bonuses with error handling
    try:
        if re.match(r'^\+', phone):  # International prefix
            score += 0.1
        if re.search(r'\(\d{3}\)', phone):  # Area code in parentheses
            score += 0.1
    except re.error:
        pass
    
    # Penalize suspicious patterns with error handling
    try:
        if re.search(r'(\d)\1{4,}', digits_only):  # Too many repeated digits
            score -= 0.2
    except re.error:
        pass
    
    if digits_only in ['1234567890', '0123456789']:  # Sequential numbers
        score -= 0.3
    
    return True, min(1.0, score), normalized


def _extract_contacts_advanced(cv_text: str | None) -> Dict[str, any]:
    """Advanced contact extraction with multiple strategies and confidence scoring."""
    if not cv_text:
        return {"name": "", "email": "", "phone": "", "linkedin": "", "github": "", "confidence": {}}
    
    text = cv_text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    # Strategy 1: Header-based extraction (first 5 lines)
    header_candidates = []
    for i, line in enumerate(lines[:5]):
        # Skip lines with common non-name patterns
        if re.search(r'(resume|cv|curriculum|email|phone|address|objective|summary)', line.lower()):
            continue
        
        # Look for name-like patterns with error handling
        name_patterns = [
            r'^([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)$',  # First Last [Middle]
            r'^([A-Z][A-Z\s]{10,40})$',  # ALL CAPS NAME
            r'^([A-Za-z\u00C0-\u017F][A-Za-z\u00C0-\u017F\s\'.,-]{5,50})$'  # General pattern with accents
        ]
        
        for pattern in name_patterns:
            try:
                match = re.match(pattern, line)
                if match:
                    candidate = match.group(1).strip()
                    confidence = _score_name_candidate(candidate, lines)
                    if confidence > 0.3:
                        header_candidates.append((candidate, confidence, i))
            except re.error:
                continue
    
    # Strategy 2: Contact block extraction
    contact_block = ' '.join(lines[:3])
    
    # Email extraction with validation and error handling
    email_candidates = []
    email_patterns = [
        r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b',
        r'(?:email|e-mail)[:\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
    ]
    
    for pattern in email_patterns:
        try:
            matches = re.findall(pattern, text, re.I)
            for match in matches:
                try:
                    is_valid, confidence = _validate_email(match)
                    if is_valid:
                        email_candidates.append((match, confidence))
                except Exception:
                    continue
        except re.error:
            continue
    
    # Phone extraction with validation and error handling
    phone_candidates = []
    phone_patterns = [
        r'(?:phone|tel|mobile|cell)[:\s]*([+]?[\d\s\-\(\)\.]{7,20})',
        r'([+]?\d{1,4}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9})',
        r'(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})',
    ]
    
    for pattern in phone_patterns:
        try:
            matches = re.findall(pattern, text, re.I)
            for match in matches:
                try:
                    is_valid, confidence, normalized = _validate_phone(match)
                    if is_valid:
                        phone_candidates.append((normalized, confidence))
                except Exception:
                    continue
        except re.error:
            continue
    
    # Social profiles with validation and error handling
    linkedin = ""
    github = ""
    
    try:
        linkedin_pattern = r'https?://(www\.)?linkedin\.com/in/([A-Za-z0-9\-]+)/?'
        linkedin_matches = re.findall(linkedin_pattern, text, re.I)
        linkedin = f"https://linkedin.com/in/{linkedin_matches[0][1]}" if linkedin_matches else ""
    except (re.error, IndexError):
        pass
    
    try:
        github_pattern = r'https?://(www\.)?github\.com/([A-Za-z0-9\-_]+)/?'
        github_matches = re.findall(github_pattern, text, re.I)
        github = f"https://github.com/{github_matches[0][1]}" if github_matches else ""
    except (re.error, IndexError):
        pass
    
    # Select best candidates
    best_name = max(header_candidates, key=lambda x: x[1])[0] if header_candidates else ""
    best_email = max(email_candidates, key=lambda x: x[1])[0] if email_candidates else ""
    best_phone = max(phone_candidates, key=lambda x: x[1])[0] if phone_candidates else ""
    
    # Calculate confidence scores
    confidence_scores = {
        "name": max(header_candidates, key=lambda x: x[1])[1] if header_candidates else 0.0,
        "email": max(email_candidates, key=lambda x: x[1])[1] if email_candidates else 0.0,
        "phone": max(phone_candidates, key=lambda x: x[1])[1] if phone_candidates else 0.0,
        "linkedin": 0.9 if linkedin else 0.0,
        "github": 0.9 if github else 0.0,
        "overall": 0.0
    }
    
    # Calculate overall confidence
    weights = {"name": 0.3, "email": 0.3, "phone": 0.2, "linkedin": 0.1, "github": 0.1}
    confidence_scores["overall"] = sum(confidence_scores[field] * weight for field, weight in weights.items())
    
    return {
        "name": best_name,
        "email": best_email,
        "phone": best_phone,
        "linkedin": linkedin,
        "github": github,
        "confidence": confidence_scores,
        "candidates": {
            "names": header_candidates[:3],  # Top 3 name candidates
            "emails": email_candidates[:2],  # Top 2 email candidates
            "phones": phone_candidates[:2]   # Top 2 phone candidates
        }
    }


def _extract_contacts(cv_text: str | None) -> Dict[str, str]:
    """Backward compatible contact extraction wrapper."""
    advanced_result = _extract_contacts_advanced(cv_text)
    return {
        "name": advanced_result["name"],
        "email": advanced_result["email"],
        "phone": advanced_result["phone"],
        "linkedin": advanced_result["linkedin"],
        "github": advanced_result["github"]
    }


def _extract_company_name(jd_text: str) -> str:
    """Extract company name from job description."""
    if not jd_text:
        return ""
    
    # Look for common company indicators
    company_patterns = [
        r"(?:at|join|with)\s+([A-Z][A-Za-z\s&.,-]{2,30})(?:\s+(?:is|as|we|our|the))",
        r"([A-Z][A-Za-z\s&.,-]{2,30})\s+(?:is looking|seeks|hiring)",
        r"Company:\s*([A-Z][A-Za-z\s&.,-]{2,30})",
        r"([A-Z][A-Za-z\s&.,-]{2,30})\s+(?:team|department|organization)",
        r"(?:work for|employed by)\s+([A-Z][A-Za-z\s&.,-]{2,30})"
    ]
    
    for pattern in company_patterns:
        try:
            match = re.search(pattern, jd_text)
            if match:
                potential_company = match.group(1).strip()
                # Filter out generic terms
                generic_terms = ["the company", "our company", "this role", "the team", "our team", "the organization", "our organization"]
                if not any(generic in potential_company.lower() for generic in generic_terms):
                    # Additional validation - company names should be reasonable length
                    if 2 <= len(potential_company) <= 50 and not potential_company.lower() in ["we", "our", "the", "this", "that"]:
                        return potential_company
        except re.error:
            continue
    
    return ""


def _extract_key_requirements(jd_text: str) -> List[str]:
    """Extract key requirements from job description."""
    if not jd_text:
        return []
    
    requirements = []
    # Look for requirement sections with improved error handling
    requirement_patterns = [
        r"(?:requirements?|qualifications?|skills?)[:\s]*([^\n]{20,200})",
        r"(?:must have|required)[:\s]*([^\n]{20,200})",
        r"(?:experience with|knowledge of)[:\s]*([^\n]{20,200})"
    ]
    
    for pattern in requirement_patterns:
        try:
            matches = re.findall(pattern, jd_text, re.I)
            for match in matches:
                # Extract key terms from each requirement with validation
                try:
                    terms = re.findall(r"\b[A-Z][A-Za-z+#.]{2,20}\b", match)
                    requirements.extend(terms[:3])
                except re.error:
                    continue
        except re.error:
            continue
    
    return list(set(requirements))[:10]


def _generate_intelligent_fallback_cover_letter(industry: str, industry_config: Dict, contacts: Dict, company_name: str, key_requirements: List[str], cv_text: str) -> str:
    """Generate intelligent fallback cover letter with industry and context awareness."""
    name = contacts.get("name", "[Your Name]")
    
    # Build industry-specific opening
    industry_openings = {
        "tech": "I am excited to apply for this technology role",
        "finance": "I am writing to express my interest in this financial position",
        "healthcare": "I am eager to contribute to your healthcare organization",
        "marketing": "I am enthusiastic about this marketing opportunity",
        "sales": "I am excited to apply for this sales position",
        "general": "I am writing to express my strong interest in this position"
    }
    
    opening = industry_openings.get(industry, industry_openings["general"])
    company_ref = f" at {company_name}" if company_name else ""
    
    # Build skills paragraph based on requirements
    skills_paragraph = ""
    if key_requirements:
        skills_paragraph = f"\n\nMy experience with {', '.join(key_requirements[:5])} aligns well with your requirements. "
    
    skills_paragraph += industry_config.get('cover_letter_focus', 'I bring relevant experience and skills to this role.')
    
    # Build closing based on industry
    industry_closings = {
        "tech": "I look forward to discussing how my technical expertise can contribute to your team's success.",
        "finance": "I would welcome the opportunity to discuss how my financial acumen can add value to your organization.",
        "healthcare": "I am eager to discuss how my commitment to patient care aligns with your mission.",
        "marketing": "I look forward to discussing how my creative approach can enhance your marketing initiatives.",
        "sales": "I am excited to discuss how my sales achievements can drive results for your team.",
        "general": "I look forward to the opportunity to discuss my qualifications further."
    }
    
    closing = industry_closings.get(industry, industry_closings["general"])
    
    return f"""Dear Hiring Manager,

{opening}{company_ref}. {skills_paragraph}

Based on my background and the requirements outlined in your job description, I believe I would be a strong addition to your team. My experience has prepared me well for the challenges and opportunities this role presents.

{closing}

Thank you for considering my application.

Sincerely,
{name}"""


def _generate_intelligent_fallback_cv(industry: str, industry_config: Dict, contacts: Dict, template: str, jd_text: str, cv_text: str) -> str:
    """Generate intelligent fallback CV with template and industry awareness."""
    name = contacts.get("name", "[Your Name]")
    email = contacts.get("email", "[Your Email]")
    phone = contacts.get("phone", "[Your Phone]")
    linkedin = contacts.get("linkedin", "")
    
    # Build contact header based on template
    if template == "modern":
        header = f"{name}\n{email} | {phone}" + (f" | {linkedin}" if linkedin else "")
    elif template == "executive":
        header = f"{name}\n{industry.title()} Professional\n{email} | {phone}" + (f" | {linkedin}" if linkedin else "")
    else:  # classic, technical
        header = f"{name}\n{email} | {phone}" + (f" | {linkedin}" if linkedin else "")
    
    # Industry-specific professional summary
    summary_templates = {
        "tech": f"Experienced {industry} professional with expertise in software development, system architecture, and technical problem-solving.",
        "finance": f"Results-driven {industry} professional with strong analytical skills and experience in financial analysis and strategic planning.",
        "healthcare": f"Dedicated {industry} professional committed to patient care excellence and healthcare quality improvement.",
        "marketing": f"Creative {industry} professional with proven track record in brand management, digital marketing, and customer engagement.",
        "sales": f"High-performing {industry} professional with consistent record of exceeding targets and building client relationships.",
        "general": "Experienced professional with strong analytical and problem-solving skills."
    }
    
    summary = summary_templates.get(industry, summary_templates["general"])
    
    # Core competencies based on industry
    competencies = industry_config.get('keywords', ['Communication', 'Problem Solving', 'Team Collaboration'])[:8]
    competency_section = "\n".join([f"• {skill}" for skill in competencies])
    
    return f"""{header}

PROFESSIONAL SUMMARY
{summary}

CORE COMPETENCIES
{competency_section}

PROFESSIONAL EXPERIENCE
[Your relevant work experience with quantified achievements]

EDUCATION
[Your educational background]

ADDITIONAL SKILLS
{' • '.join(industry_config.get('keywords', [])[-5:])}"""


def _build_cover_prompt(jd_text: str, cv_text: str | None) -> str:
    """Build cover letter prompt with industry-specific templates and dynamic formatting."""
    try:
        industry = _detect_industry(jd_text)
        industry_config = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["general"])
        
        # Extract key information with error handling
        contacts = _extract_contacts(cv_text) if cv_text else {}
        company_name = _extract_company_name(jd_text)
        key_requirements = _extract_key_requirements(jd_text)
        
        # Select prompt variant
        variant = _select_prompt_variant(industry, "cover_letter")
    except Exception:
        # Fallback to basic prompt if extraction fails
        industry = "general"
        industry_config = INDUSTRY_TEMPLATES["general"]
        contacts = {}
        company_name = ""
        key_requirements = []
        variant = "default"
    
    name = contacts.get("name", "")
    contact_line = ", ".join(x for x in [contacts.get("email"), contacts.get("phone"), contacts.get("linkedin") or contacts.get("github")] if x)
    
    # Extract company name from JD for personalized greeting
    greeting = f"Dear {company_name} Hiring Team," if company_name else "Dear Hiring Manager,"
    
    # Dynamic length based on content complexity
    cv_length = len(cv_text or "")
    jd_length = len(jd_text or "")
    
    if cv_length > 2000 or jd_length > 1000:
        target_length = "300-400 words"
        structure = "opening paragraph, 3-5 achievement bullets, closing paragraph"
    else:
        target_length = "250-350 words"
        structure = "opening paragraph, 2-4 achievement bullets, closing paragraph"
    
    # Variant-specific instructions
    variant_instructions = {
        "standard": "Focus on clear alignment between experience and requirements",
        "story_driven": "Tell a compelling professional story that connects past achievements to future potential",
        "achievement_focused": "Lead with quantified achievements and measurable impact from the CV",
        "problem_solution": "Address specific challenges mentioned in the JD and present solutions from your experience"
    }
    
    return (
        f"ROLE: Expert {industry} career writer crafting ATS-optimized cover letters.\n"
        f"OBJECTIVE: {PROMPT_VARIANTS['cover_letter'].get(variant, PROMPT_VARIANTS['cover_letter']['standard'])} using ONLY verified facts from the CV and JD.\n"
        f"VARIANT STRATEGY: {variant_instructions.get(variant, variant_instructions['standard'])}\n\n"
        f"INDUSTRY FOCUS: {industry_config['cover_tone']}\n"
        f"KEY INDUSTRY TERMS: {', '.join(industry_config['keywords'][:8])}\n"
        f"QUALITY INDICATORS: {', '.join(industry_config['quality_indicators'][:5])}\n\n"
        "STRICT REQUIREMENTS:\n"
        "- NO fabrications: use only CV facts, dates, companies, technologies, achievements\n"
        "- KEYWORD INTEGRATION: naturally incorporate JD keywords that appear in the CV\n"
        "- QUANTIFIED IMPACT: include specific metrics, percentages, dollar amounts from CV\n"
        "- ATS OPTIMIZATION: use exact job title and key requirements from JD\n"
        f"- LENGTH: {target_length}\n"
        f"- STRUCTURE: {structure}\n"
        "- FORMAT: Plain text, professional business letter format\n"
        f"- GREETING: {greeting}\n\n"
        "PERSONALIZATION DATA:\n"
        f"Candidate: {name}\n"
        f"Contact: {contact_line}\n"
        f"Company: {company_name or 'Not specified'}\n\n"
        "JOB DESCRIPTION:\n" + (jd_text or "")[:2000] + "\n\n"
        "CANDIDATE CV:\n" + (cv_text or "")[:3000] + "\n\n"
        f"Generate a {variant.replace('_', ' ')} cover letter that demonstrates clear alignment between the candidate's experience and the role requirements."
    )


def _build_cv_prompt(jd_text: str, cv_text: str | None, template: str = "classic") -> str:
    """Build CV prompt with industry-specific templates and dynamic formatting."""
    try:
        industry = _detect_industry(jd_text)
        industry_config = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["general"])
        
        # Extract key information with error handling
        contacts = _extract_contacts(cv_text) if cv_text else {}
        key_requirements = _extract_key_requirements(jd_text)
        
        # Select prompt variant
        variant = _select_prompt_variant(industry, "cv")
    except Exception:
        # Fallback to basic prompt if extraction fails
        industry = "general"
        industry_config = INDUSTRY_TEMPLATES["general"]
        contacts = {}
        key_requirements = []
        variant = "default"
    
    name = contacts.get("name", "")
    email = contacts.get("email", "")
    phone = contacts.get("phone", "")
    profile = " | ".join(x for x in [email, phone, contacts.get("linkedin") or contacts.get("github")] if x)
    
    # Template-specific formatting
    template_formats = {
        "modern": "Clean, contemporary formatting",
        "classic": "Traditional, professional layout", 
        "executive": "Leadership-focused presentation",
        "technical": "Skills and project-oriented"
    }
    
    template_config = template_formats.get(template, template_formats["classic"])
    
    # Extract key requirements from JD for targeted optimization
    jd_keywords = []
    if jd_text:
        # Extract requirements, skills, qualifications
        requirement_sections = re.findall(r"(?:requirements?|qualifications?|skills?|experience)[:\s]*([^\n]{50,200})", jd_text, re.I)
        for section in requirement_sections:
            # Extract key terms
            terms = re.findall(r"\b[A-Z][A-Za-z+#.]{2,15}\b", section)
            jd_keywords.extend(terms[:5])
    
    # Variant-specific CV instructions
    variant_instructions = {
        "standard": "Create a well-structured CV with clear sections and professional formatting",
        "impact_focused": "Emphasize quantified business outcomes and measurable achievements throughout",
        "skills_first": "Lead with a comprehensive skills section before experience details",
        "hybrid": "Balance chronological experience with prominent skills and achievements sections"
    }
    
    return (
        f"ROLE: Senior {industry} resume writer specializing in ATS optimization.\n"
        f"OBJECTIVE: {PROMPT_VARIANTS['cv'].get(variant, PROMPT_VARIANTS['cv']['standard'])} optimized for {industry} roles using ONLY verified CV facts.\n"
        f"VARIANT STRATEGY: {variant_instructions.get(variant, variant_instructions['standard'])}\n\n"
        f"INDUSTRY FOCUS: {industry_config['cv_focus']}\n"
        f"TARGET KEYWORDS: {', '.join(industry_config['keywords'][:10])}\n"
        f"QUALITY INDICATORS: {', '.join(industry_config['quality_indicators'][:5])}\n"
        f"JD PRIORITY TERMS: {', '.join(jd_keywords[:8])}\n\n"
        f"TEMPLATE SPECIFICATIONS ({template.upper()}):\n"
        f"- Header: {template_config}\n"
        f"- Sections: {template_config}\n"
        f"- Bullets: {template_config}\n\n"
        "STRICT REQUIREMENTS:\n"
        "- FACTUAL ACCURACY: Use only CV companies, titles, dates, technologies, achievements\n"
        "- ATS OPTIMIZATION: Include exact job title and key requirements from JD where CV supports\n"
        "- QUANTIFIED IMPACT: Preserve and highlight all numbers, percentages, metrics from CV\n"
        "- KEYWORD DENSITY: Naturally integrate JD keywords that exist in CV experience\n"
        "- SECTION RELEVANCE: Only include sections with substantial CV content\n"
        "- PLAIN TEXT: No tables, graphics, or complex formatting\n\n"
        "REQUIRED SECTIONS (if CV content exists):\n"
        "1. CONTACT HEADER\n"
        "2. PROFESSIONAL SUMMARY (3-4 lines, JD-tailored)\n"
        "3. CORE COMPETENCIES/SKILLS (grouped by category, JD-aligned)\n"
        "4. PROFESSIONAL EXPERIENCE (Company | Title | Dates | 3-5 impact bullets each)\n"
        "5. EDUCATION (Institution | Degree | Year | Honors if applicable)\n"
        "6. CERTIFICATIONS & LICENSES (if any)\n"
        "7. TECHNICAL PROFICIENCIES (if applicable)\n"
        "8. KEY ACHIEVEMENTS (if space permits)\n\n"
        f"CANDIDATE DATA:\n"
        f"Name: {name}\n"
        f"Contact: {profile}\n\n"
        "TARGET JOB DESCRIPTION:\n" + (jd_text or "")[:2000] + "\n\n"
        "SOURCE CV CONTENT:\n" + (cv_text or "")[:4000] + "\n\n"
        f"Generate a {variant.replace('_', ' ')} CV that maximizes ATS compatibility while showcasing the candidate's strongest qualifications for this specific role."
    )


def generate_cover_letter(jd_text: str, cv_text: str | None = None) -> Tuple[str, str, List[Dict]]:
    """
    Returns (provider_used, content, trace)
    - Enhanced with caching, retry logic, and provider health tracking
    - Uses AI_DRY_RUN=true (default) to return deterministic content without external calls.
    """
    ai_dry_run = _bool_env("AI_DRY_RUN", True)
    trace: List[Dict] = []
    
    # Build prompt for caching
    prompt = _build_cover_prompt(jd_text or "", cv_text or "")
    
    if ai_dry_run:
        # Enhanced mock response with industry detection
        industry = _detect_industry(jd_text)
        industry_config = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["general"])
        contacts = _extract_contacts(cv_text)
        
        content = (
            f"Cover Letter — {industry.title()} Industry Focus\n\n"
            f"Provider: mock (dry run)\n"
            f"Industry: {industry}\n\n"
            f"Dear Hiring Manager,\n\n"
            f"I'm excited to apply for this {industry} opportunity. My background in {industry_config['cv_focus']} "
            f"aligns closely with your requirements and the outcomes you're targeting.\n\n"
            f"Key Achievements:\n"
            f"• Delivered {industry}-specific results using relevant technologies and methodologies\n"
            f"• Led initiatives with measurable impact in {', '.join(industry_config['keywords'][:3])}\n"
            f"• Collaborated cross-functionally to improve KPIs and drive business outcomes\n\n"
            f"I'd welcome the chance to discuss how my {industry} experience can support your team's objectives.\n\n"
            f"Sincerely,\n{contacts.get('name', 'Your Name')}\n"
            f"{', '.join(x for x in [contacts.get('email'), contacts.get('phone')] if x)}\n\n"
            f"JD Keywords Detected: {', '.join(industry_config['keywords'][:5])}\n"
            f"JD Excerpt: {(jd_text or '').strip()[:300]}...\n"
        )
        trace.append({"provider": "mock", "status": "dry_run", "duration_ms": 0, "industry": industry})
        return "mock", content, trace
    
    # Check cache first
    cache_key = _get_cache_key(prompt, "cover_letter")
    cached_response = _get_cached_response(cache_key)
    if cached_response:
        trace.append({"provider": "cache", "status": "hit", "duration_ms": 0})
        return "cache", cached_response, trace
    
    # Try providers with health-based ordering
    providers = _get_provider_priority()
    timeout = float(os.environ.get("AI_TIMEOUT_SECONDS", "30"))
    
    for provider in providers:
        if provider == "mock":
            continue
            
        # Skip providers with too many recent failures
        if PROVIDER_HEALTH[provider]["failures"] > 5:
            trace.append({"provider": provider, "status": "skipped", "reason": "too_many_failures", "duration_ms": 0})
            continue
        
        t0 = time.perf_counter()
        try:
            if provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
                out = _make_request_with_retry(_gemini_generate, prompt, timeout)
            elif provider == "deepseek" and os.environ.get("DEEPSEEK_API_KEY"):
                out = _make_request_with_retry(_deepseek_generate, prompt, timeout)
            elif provider == "groq" and os.environ.get("GROQ_API_KEY"):
                out = _make_request_with_retry(_groq_generate, prompt, timeout)
            else:
                continue
            
            dt = int((time.perf_counter() - t0) * 1000)
            _update_provider_health(provider, True)
            _cache_response(cache_key, out)
            
            # Calculate quality score for generated content
            quality_scores = _calculate_content_quality_score(out, jd_text, _detect_industry(jd_text), "cover_letter")
            
            trace.append({
                "provider": provider, 
                "status": "success", 
                "duration_ms": dt,
                "quality_score": quality_scores["overall"],
                "quality_breakdown": quality_scores
            })
            return provider, out, trace
            
        except Exception as e:
            dt = int((time.perf_counter() - t0) * 1000)
            _update_provider_health(provider, False)
            trace.append({
                "provider": provider, 
                "status": "error", 
                "error": str(e)[:200], 
                "duration_ms": dt
            })
            continue
    
    # Enhanced fallback content generation
    if ai_config.fallback["enable_fallback_content"]:
        industry = _detect_industry(jd_text)
        industry_config = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["general"])
        contacts = _extract_contacts(cv_text)
        
        # Extract company name and key requirements
        company_name = _extract_company_name(jd_text)
        key_requirements = _extract_key_requirements(jd_text)
        
        fallback_content = _generate_intelligent_fallback_cover_letter(
            industry, industry_config, contacts, company_name, key_requirements, cv_text
        )
        
        # Calculate quality score for fallback content
        quality_scores = _calculate_content_quality_score(fallback_content, jd_text, industry, "cover_letter")
        
        trace.append({
            "provider": "intelligent_fallback", 
            "status": "generated", 
            "reason": "All providers failed",
            "quality_score": quality_scores["overall"],
            "fallback_type": "intelligent"
        })
        return "intelligent_fallback", fallback_content, trace
    
    # Basic fallback if intelligent fallback is disabled
    basic_fallback = "Dear Hiring Manager,\n\nI am writing to express my interest in this position. Please find my attached resume for your consideration.\n\nThank you for your time.\n\nSincerely,\n[Your Name]"
    trace.append({"provider": "basic_fallback", "status": "generated", "reason": "All providers failed, intelligent fallback disabled"})
    return "basic_fallback", basic_fallback, trace


def generate_cv(jd_text: str, cv_text: str | None = None, template: str = "classic") -> Tuple[str, str, List[Dict]]:
    """
    Returns (provider_used, content, trace) for a generated CV.
    - Enhanced with caching, retry logic, and provider health tracking
    - Uses AI_DRY_RUN=true (default) to return deterministic content without external calls.
    """
    ai_dry_run = _bool_env("AI_DRY_RUN", True)
    trace: List[Dict] = []
    
    # Build prompt for caching
    prompt = _build_cv_prompt(jd_text or "", cv_text or "", template)
    
    if ai_dry_run:
        # Enhanced mock response with industry and template awareness
        industry = _detect_industry(jd_text)
        industry_config = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["general"])
        contacts = _extract_contacts(cv_text)
        
        template_formats = {
            "modern": "Clean, contemporary formatting",
            "classic": "Traditional, professional layout", 
            "executive": "Leadership-focused presentation",
            "technical": "Skills and project-oriented"
        }
        
        content = (
            f"Generated CV — {template.title()} Template\n"
            f"Industry: {industry.title()} | Provider: mock (dry run)\n\n"
            f"{contacts.get('name', 'YOUR NAME').upper()}\n"
            f"{' | '.join(x for x in [contacts.get('email', 'email@example.com'), contacts.get('phone', '(555) 123-4567'), contacts.get('linkedin', 'linkedin.com/in/username')] if x)}\n\n"
            f"PROFESSIONAL SUMMARY\n"
            f"Results-driven {industry} professional with expertise in {industry_config['cv_focus']}. "
            f"Proven track record of delivering measurable outcomes through {', '.join(industry_config['keywords'][:3])}.\n\n"
            f"CORE COMPETENCIES\n"
            f"{' • '.join(industry_config['keywords'][:8])}\n\n"
            f"PROFESSIONAL EXPERIENCE\n"
            f"Company Name — Job Title — 2020-Present\n"
            f"• Achieved [specific metric] through implementation of {industry_config['keywords'][0]} strategies\n"
            f"• Led cross-functional initiatives resulting in [quantified outcome]\n"
            f"• Optimized {industry_config['keywords'][1]} processes, improving efficiency by [percentage]\n\n"
            f"Previous Company — Previous Title — 2018-2020\n"
            f"• Delivered {industry_config['keywords'][2]} solutions with [measurable impact]\n"
            f"• Collaborated with stakeholders to enhance [relevant area]\n\n"
            f"EDUCATION\n"
            f"University Name — Degree in Relevant Field — Year\n\n"
            f"CERTIFICATIONS\n"
            f"Relevant {industry.title()} Certifications (if applicable)\n\n"
            f"Template Style: {template_formats.get(template, 'Professional formatting')}\n"
            f"JD Keywords Detected: {', '.join(industry_config['keywords'][:5])}\n"
        )
        trace.append({"provider": "mock", "status": "dry_run", "duration_ms": 0, "template": template, "industry": industry})
        return "mock", content, trace
    
    # Check cache first
    cache_key = _get_cache_key(prompt, f"cv_{template}")
    cached_response = _get_cached_response(cache_key)
    if cached_response:
        trace.append({"provider": "cache", "status": "hit", "duration_ms": 0, "template": template})
        return "cache", cached_response, trace
    
    # Try providers with health-based ordering
    providers = _get_provider_priority()
    timeout = float(os.environ.get("AI_TIMEOUT_SECONDS", "30"))
    
    for provider in providers:
        if provider == "mock":
            continue
            
        # Skip providers with too many recent failures
        if PROVIDER_HEALTH[provider]["failures"] > 5:
            trace.append({"provider": provider, "status": "skipped", "reason": "too_many_failures", "duration_ms": 0})
            continue
        
        t0 = time.perf_counter()
        try:
            if provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
                out = _make_request_with_retry(_gemini_generate, prompt, timeout)
            elif provider == "deepseek" and os.environ.get("DEEPSEEK_API_KEY"):
                out = _make_request_with_retry(_deepseek_generate, prompt, timeout)
            elif provider == "groq" and os.environ.get("GROQ_API_KEY"):
                out = _make_request_with_retry(_groq_generate, prompt, timeout)
            else:
                continue
            
            dt = int((time.perf_counter() - t0) * 1000)
            _update_provider_health(provider, True)
            _cache_response(cache_key, out)
            
            # Calculate quality score for generated content
            quality_scores = _calculate_content_quality_score(out, jd_text, _detect_industry(jd_text), "cv")
            
            trace.append({
                "provider": provider, 
                "status": "success", 
                "duration_ms": dt, 
                "template": template,
                "quality_score": quality_scores["overall"],
                "quality_breakdown": quality_scores
            })
            return provider, out, trace
            
        except Exception as e:
            dt = int((time.perf_counter() - t0) * 1000)
            _update_provider_health(provider, False)
            trace.append({
                "provider": provider, 
                "status": "error", 
                "error": str(e)[:200], 
                "duration_ms": dt
            })
            continue
    
    # Enhanced fallback with industry and template awareness
    industry = _detect_industry(jd_text)
    industry_config = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["general"])
    contacts = _extract_contacts(cv_text)
    name = contacts.get("name", "YOUR NAME") or "YOUR NAME"
    profile = " | ".join(x for x in [contacts.get("email"), contacts.get("phone"), contacts.get("linkedin") or contacts.get("github")] if x)
    
    # Template-specific formatting for fallback
    if template == "executive":
        header_style = f"{name.upper()}\nSenior {industry.title()} Executive"
    elif template == "technical":
        header_style = f"{name.upper()}\n{industry.title()} Specialist"
    else:
        header_style = name.upper()
    
    content = (
        f"{header_style}\n{profile}\n\n"
        f"PROFESSIONAL SUMMARY\n"
        f"Experienced {industry} professional with demonstrated expertise in {industry_config['cv_focus']}. "
        f"Proven ability to deliver results through {', '.join(industry_config['keywords'][:3])}.\n\n"
        f"CORE COMPETENCIES\n"
        f"{' • '.join(industry_config['keywords'][:6])}\n\n"
        f"PROFESSIONAL EXPERIENCE\n"
        f"[Company Name] — [Job Title] — [Dates]\n"
        f"• Achieved measurable results in {industry_config['keywords'][0]} through strategic implementation\n"
        f"• Led initiatives resulting in quantified business impact and process improvements\n"
        f"• Collaborated with cross-functional teams to deliver {industry_config['keywords'][1]} solutions\n\n"
        f"EDUCATION\n"
        f"[Institution] — [Degree] — [Year]\n\n"
        f"CERTIFICATIONS\n"
        f"Relevant {industry.title()} certifications and professional development\n"
    )
    
    trace.append({"provider": "fallback", "status": "generated", "duration_ms": 0, "template": template, "industry": industry})
    return "fallback", content, trace
