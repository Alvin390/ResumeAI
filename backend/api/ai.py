import os
import re
import time
import html
import json
import hashlib
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from functools import lru_cache
from dataclasses import dataclass
import pickle
import logging

# ML Quality Prediction
try:
    from .ml_quality_predictor import (
        predict_generation_quality,
        collect_quality_feedback,
        feature_extractor,
        QualityFeatures
    )
    ML_QUALITY_ENABLED = True
except ImportError as e:
    logging.warning(f"ML quality prediction disabled: {e}")
    ML_QUALITY_ENABLED = False

# A/B Testing Framework
try:
    from .ab_testing import (
        assign_generation_variant,
        record_generation_metrics,
        ab_test_manager
    )
    AB_TESTING_ENABLED = True
except ImportError as e:
    logging.warning(f"A/B testing disabled: {e}")
    AB_TESTING_ENABLED = False

# Semantic Caching
try:
    from .semantic_cache import (
        get_semantic_cached_response,
        cache_semantic_response,
        semantic_cache
    )
    SEMANTIC_CACHE_ENABLED = True
except ImportError as e:
    logging.warning(f"Semantic caching disabled: {e}")
    SEMANTIC_CACHE_ENABLED = False

# Multi-Modal Generation
try:
    from .multimodal_generation import generate_formatted_content
    MULTIMODAL_ENABLED = True
except ImportError as e:
    logging.warning(f"Multi-modal generation disabled: {e}")
    MULTIMODAL_ENABLED = False

# AI wrapper with deterministic dry-run default.

DEFAULT_PROVIDER = "gemini"

# Simple in-memory cache for AI responses
_ai_cache = {}
CACHE_MAX_SIZE = 100
CACHE_TTL_SECONDS = 3600  # 1 hour

# Global rate limiting and health tracking
RATE_LIMIT_LOCK = threading.Lock()
PROVIDER_HEALTH = {
    "gemini": {"failures": 0, "last_success": 0, "last_failure": 0},
    "deepseek": {"failures": 0, "last_success": 0, "last_failure": 0},
    "groq": {"failures": 0, "last_success": 0, "last_failure": 0}
}

# CV content caching
CV_CACHE = {}
CACHE_LOCK = threading.Lock()
CACHE_TTL = 3600  # 1 hour cache TTL

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
    
    # Strategy 1: Enhanced header-based extraction (first 7 lines for international CVs)
    header_candidates = []
    for i, line in enumerate(lines[:7]):
        # Skip lines with common non-name patterns
        if re.search(r'(resume|cv|curriculum|email|phone|address|objective|summary)', line.lower()):
            continue
        
        # Enhanced name patterns for international support
        name_patterns = [
            r'^([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)$',  # First Last [Middle]
            r'^([A-Z][A-Z\s]{10,40})$',  # ALL CAPS NAME
            r'^([A-Za-z\u00C0-\u017F][A-Za-z\u00C0-\u017F\s\'.,-]{5,50})$',  # General pattern with accents
            r'^([\u4e00-\u9fff]{2,8})$',  # Chinese names (2-8 characters)
            r'^([\u0600-\u06ff\s]{3,30})$',  # Arabic names
            r'^([\u0900-\u097f\s]{3,30})$',  # Hindi/Devanagari names
            r'^([A-Za-z\u00C0-\u017F]+(?:[-\s][A-Za-z\u00C0-\u017F]+){1,3})$',  # Hyphenated European names
            r'^([A-Za-z]+\s+(?:van|de|der|von|da|del|dos|ibn)\s+[A-Za-z]+)$'  # Names with particles
        ]
        
        for pattern in name_patterns:
            try:
                match = re.match(pattern, line)
                if match:
                    candidate = match.group(1).strip()
                    confidence = _score_name_candidate(candidate, lines)
                    if confidence > 0.25:  # Lower threshold for international names
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


def _extract_structured_cv_content(cv_text: str) -> Dict[str, any]:
    """Extract structured content from CV including skills, experience, and education."""
    if not cv_text:
        return {"skills": [], "experience": [], "education": [], "sections": {}}
    
    text = cv_text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    # Initialize result structure
    result = {
        "skills": [],
        "experience": [],
        "education": [],
        "sections": {},
        "achievements": []
    }
    
    # Section detection patterns
    section_patterns = {
        "skills": r"(?:technical\s+)?skills?|competenc(?:ies|y)|technologies?",
        "experience": r"(?:work\s+)?experience|employment|professional\s+(?:experience|background)",
        "education": r"education(?:al\s+background)?|academic|qualifications?",
        "achievements": r"achievements?|accomplishments?"
    }
    
    current_section = None
    section_content = []
    
    # Parse sections
    for line in lines:
        line_lower = line.lower()
        detected_section = None
        
        for section_name, pattern in section_patterns.items():
            try:
                if re.search(f"^{pattern}\s*:?\s*$", line_lower):
                    detected_section = section_name
                    break
            except re.error:
                continue
        
        if detected_section:
            if current_section and section_content:
                result["sections"][current_section] = "\n".join(section_content)
                _parse_section_content(result, current_section, section_content)
            current_section = detected_section
            section_content = []
        else:
            if current_section:
                section_content.append(line)
    
    if current_section and section_content:
        result["sections"][current_section] = "\n".join(section_content)
        _parse_section_content(result, current_section, section_content)
    
    if not result["skills"]:
        result["skills"] = _extract_skills_from_text(text)
    
    result["achievements"] = _extract_achievements(text)
    
    return result


def _parse_section_content(result: Dict, section_name: str, content: List[str]) -> None:
    """Parse specific section content based on section type."""
    text = "\n".join(content)
    
    if section_name == "skills":
        result["skills"] = _extract_skills_from_text(text)
    elif section_name == "experience":
        result["experience"] = _extract_work_experience(text)
    elif section_name == "education":
        result["education"] = _extract_education(text)


def _extract_skills_from_text(text: str) -> List[Dict[str, str]]:
    """Extract technical and soft skills from text with enhanced patterns."""
    if not text:
        return []
    
    skills = []
    
    # Comprehensive technical skills patterns
    tech_patterns = [
        # Programming Languages
        r"\b(Python|Java|JavaScript|TypeScript|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin|Scala|R|MATLAB)\b",
        # Web Frameworks
        r"\b(React|Angular|Vue|Node\.js|Express|Django|Flask|Spring|Laravel|FastAPI|Next\.js|Nuxt\.js)\b",
        # Cloud & DevOps
        r"\b(AWS|Azure|GCP|Google Cloud|Docker|Kubernetes|Jenkins|Terraform|Ansible|Chef|Puppet)\b",
        # Databases
        r"\b(MySQL|PostgreSQL|MongoDB|Redis|Elasticsearch|Cassandra|Oracle|SQL Server|DynamoDB)\b",
        # Frontend Technologies
        r"\b(HTML|CSS|SASS|SCSS|Bootstrap|Tailwind|jQuery|Webpack|Babel|Vite)\b",
        # Data Science & AI
        r"\b(Machine Learning|AI|Data Science|TensorFlow|PyTorch|Pandas|NumPy|Scikit-learn|Jupyter)\b",
        # Tools & Methodologies
        r"\b(Git|GitHub|GitLab|Jira|Confluence|Slack|Agile|Scrum|DevOps|CI/CD|REST|GraphQL|API)\b",
        # Mobile Development
        r"\b(iOS|Android|React Native|Flutter|Xamarin|Ionic)\b"
    ]
    
    for pattern in tech_patterns:
        try:
            matches = re.findall(pattern, text, re.I)
            for match in matches:
                if match not in [s["name"] for s in skills]:
                    skills.append({"name": match, "type": "technical", "context": "pattern_match"})
        except re.error:
            continue
    
    # Extract skills from bullet points and structured lists
    try:
        # Skills in bullet format
        bullet_skills = re.findall(r"[•\-\*]\s*([A-Za-z][A-Za-z\s&+#.]{2,25})(?:\s*[,;]|$)", text)
        for skill in bullet_skills:
            skill = skill.strip()
            if len(skill) > 2 and skill not in [s["name"] for s in skills]:
                skills.append({"name": skill, "type": "general", "context": "bullet_point"})
        
        # Skills in comma-separated format
        skill_sections = re.findall(r"(?:skills?|technologies?|tools?)\s*:?\s*([^\n]{20,200})", text, re.I)
        for section in skill_sections:
            comma_skills = [s.strip() for s in section.split(',') if len(s.strip()) > 2]
            for skill in comma_skills[:10]:  # Limit per section
                if skill not in [s["name"] for s in skills]:
                    skills.append({"name": skill, "type": "listed", "context": "skills_section"})
    
    except re.error:
        pass
    
    return skills[:25]  # Increased limit for comprehensive extraction


def _extract_work_experience(text: str) -> List[Dict[str, str]]:
    """Extract work experience entries."""
    if not text:
        return []
    
    experiences = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    for line in lines:
        try:
            title_company_match = re.search(r"^(.+?)\s+at\s+(.+?)(?:\s*[|,]\s*(.+))?$", line)
            if title_company_match:
                experiences.append({
                    "title": title_company_match.group(1).strip(),
                    "company": title_company_match.group(2).strip(),
                    "duration": title_company_match.group(3).strip() if title_company_match.group(3) else ""
                })
        except re.error:
            continue
    
    return experiences[:5]


def _extract_education(text: str) -> List[Dict[str, str]]:
    """Extract education entries."""
    if not text:
        return []
    
    education = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    for line in lines:
        try:
            degree_match = re.search(r"(Bachelor|Master|PhD).*?(?:from\s+)?(.+?)(?:\s*(\d{4}))?$", line, re.I)
            if degree_match:
                education.append({
                    "degree": degree_match.group(1),
                    "institution": degree_match.group(2).strip(),
                    "year": degree_match.group(3) if degree_match.group(3) else ""
                })
        except re.error:
            continue
    
    return education[:3]


def _extract_achievements(text: str) -> List[Dict[str, str]]:
    """Extract quantified achievements."""
    if not text:
        return []
    
    achievements = []
    patterns = [
        r"(?:increased|improved|reduced)\s+.{10,80}?\s+(\d+(?:%|\$|k))",
        r"(?:managed|led)\s+(?:team of\s+)?(\d+)\s+(?:people|employees)"
    ]
    
    for pattern in patterns:
        try:
            matches = re.finditer(pattern, text, re.I)
            for match in matches:
                achievements.append({
                    "text": match.group(0),
                    "metric": match.group(1) if match.groups() else ""
                })
        except re.error:
            continue
    
    return achievements[:10]


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


def _intelligent_cv_truncation(cv_text: str, max_length: int = 4000) -> str:
    """Intelligently truncate CV content while preserving important sections."""
    if not cv_text or len(cv_text) <= max_length:
        return cv_text
    
    # Extract structured content first
    structured = _extract_structured_cv_content(cv_text)
    
    # Priority order for sections
    section_priority = ["skills", "experience", "achievements", "education"]
    
    # Start with contact information (first 200 chars)
    truncated = cv_text[:200]
    remaining_length = max_length - len(truncated)
    
    # Add sections by priority
    for section_name in section_priority:
        if section_name in structured["sections"]:
            section_content = structured["sections"][section_name]
            
            if len(section_content) <= remaining_length - 100:
                truncated += f"\n\n{section_name.upper()}\n{section_content}"
                remaining_length -= len(section_content) + len(section_name) + 4
            else:
                # Truncate section intelligently
                if section_name == "experience":
                    lines = section_content.split('\n')[:10]  # Keep recent experiences
                    important_lines = []
                    current_length = 0
                    
                    for line in lines:
                        if current_length + len(line) < remaining_length - 100:
                            important_lines.append(line)
                            current_length += len(line) + 1
                        else:
                            break
                    
                    if important_lines:
                        truncated += f"\n\n{section_name.upper()}\n" + '\n'.join(important_lines)
                        remaining_length -= current_length + len(section_name) + 4
            
            if remaining_length <= 100:
                break
    
    return truncated[:max_length]


def _validate_cv_content_ownership(cv_contacts: Dict, user_profile: Dict) -> Dict[str, float]:
    """Validate that extracted CV contacts belong to the user profile."""
    validation_scores = {
        "email_match": 0.0,
        "name_similarity": 0.0,
        "overall_confidence": 0.0
    }
    
    if not cv_contacts or not user_profile:
        return validation_scores
    
    # Email validation
    cv_email = cv_contacts.get("email", "").lower()
    profile_email = user_profile.get("email", "").lower()
    
    if cv_email and profile_email:
        if cv_email == profile_email:
            validation_scores["email_match"] = 1.0
        elif cv_email.split('@')[0] == profile_email.split('@')[0]:  # Same username
            validation_scores["email_match"] = 0.8
        elif cv_email.split('@')[1] == profile_email.split('@')[1]:  # Same domain
            validation_scores["email_match"] = 0.3
    
    # Name similarity validation
    cv_name = cv_contacts.get("name", "").lower()
    profile_name = f"{user_profile.get('first_name', '')} {user_profile.get('last_name', '')}".strip().lower()
    
    if cv_name and profile_name:
        cv_name_parts = set(cv_name.split())
        profile_name_parts = set(profile_name.split())
        
        if cv_name_parts == profile_name_parts:
            validation_scores["name_similarity"] = 1.0
        elif cv_name_parts.intersection(profile_name_parts):
            overlap = len(cv_name_parts.intersection(profile_name_parts))
            total = len(cv_name_parts.union(profile_name_parts))
            validation_scores["name_similarity"] = overlap / total if total > 0 else 0.0
    
    # Calculate overall confidence
    validation_scores["overall_confidence"] = (
        validation_scores["email_match"] * 0.7 + 
        validation_scores["name_similarity"] * 0.3
    )
    
    return validation_scores


def _calculate_skills_job_match(cv_skills: List[Dict], jd_text: str, jd_requirements: List[str]) -> Dict[str, any]:
    """Calculate skills-to-job matching with relevance scoring."""
    if not cv_skills or not jd_text:
        return {"matched_skills": [], "missing_skills": [], "match_score": 0.0, "skill_gaps": []}
    
    jd_lower = jd_text.lower()
    
    # Extract skills from job description
    jd_skill_patterns = [
        r"\b(Python|Java|JavaScript|TypeScript|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin|Scala)\b",
        r"\b(React|Angular|Vue|Node\.js|Express|Django|Flask|Spring|Laravel|FastAPI)\b",
        r"\b(AWS|Azure|GCP|Google Cloud|Docker|Kubernetes|Jenkins|Git|GitHub|GitLab)\b",
        r"\b(MySQL|PostgreSQL|MongoDB|Redis|Elasticsearch|Cassandra|Oracle|SQL Server)\b",
        r"\b(HTML|CSS|SASS|SCSS|Bootstrap|Tailwind|jQuery|Webpack|Babel)\b",
        r"\b(Machine Learning|AI|Data Science|TensorFlow|PyTorch|Pandas|NumPy|Scikit-learn)\b",
        r"\b(Agile|Scrum|DevOps|CI/CD|Microservices|REST|GraphQL|API)\b"
    ]
    
    jd_skills = set()
    for pattern in jd_skill_patterns:
        try:
            matches = re.findall(pattern, jd_text, re.I)
            jd_skills.update(match.lower() for match in matches)
        except re.error:
            continue
    
    # Add skills from requirements
    for req in jd_requirements:
        try:
            tech_terms = re.findall(r"\b[A-Z][A-Za-z+#.]{2,20}\b", req)
            jd_skills.update(term.lower() for term in tech_terms)
        except re.error:
            continue
    
    # Match CV skills against job requirements
    matched_skills = []
    cv_skill_names = {skill["name"].lower() for skill in cv_skills}
    
    for skill in cv_skills:
        skill_name = skill["name"].lower()
        relevance_score = 0.0
        
        # Direct match in JD skills
        if skill_name in jd_skills:
            relevance_score = 1.0
        # Partial match in job description text
        elif skill_name in jd_lower:
            relevance_score = 0.8
        # Fuzzy match for similar technologies
        else:
            for jd_skill in jd_skills:
                if _calculate_skill_similarity(skill_name, jd_skill) > 0.7:
                    relevance_score = 0.6
                    break
        
        if relevance_score > 0:
            matched_skills.append({
                "name": skill["name"],
                "type": skill.get("type", "general"),
                "relevance_score": relevance_score,
                "context": skill.get("context", "")
            })
    
    # Identify missing critical skills
    missing_skills = []
    for jd_skill in jd_skills:
        if jd_skill not in cv_skill_names:
            # Check if it's a critical skill (appears multiple times or in requirements)
            frequency = jd_lower.count(jd_skill)
            if frequency > 1 or any(jd_skill in req.lower() for req in jd_requirements):
                missing_skills.append({
                    "name": jd_skill.title(),
                    "frequency": frequency,
                    "criticality": "high" if frequency > 2 else "medium"
                })
    
    # Calculate overall match score
    if jd_skills:
        match_score = len([s for s in matched_skills if s["relevance_score"] >= 0.8]) / len(jd_skills)
    else:
        match_score = 0.0
    
    # Identify skill gaps and recommendations
    skill_gaps = []
    for missing in missing_skills[:5]:  # Top 5 missing skills
        similar_skills = [s["name"] for s in cv_skills if _calculate_skill_similarity(s["name"].lower(), missing["name"].lower()) > 0.5]
        skill_gaps.append({
            "missing_skill": missing["name"],
            "similar_existing": similar_skills[:2],
            "recommendation": f"Consider highlighting {missing['name']} experience" if similar_skills else f"Consider acquiring {missing['name']} skills"
        })
    
    return {
        "matched_skills": sorted(matched_skills, key=lambda x: x["relevance_score"], reverse=True),
        "missing_skills": missing_skills[:10],
        "match_score": min(1.0, match_score),
        "skill_gaps": skill_gaps
    }


def _calculate_skill_similarity(skill1: str, skill2: str) -> float:
    """Calculate similarity between two skills using simple string matching."""
    if skill1 == skill2:
        return 1.0
    
    # Check for common abbreviations and variations
    skill_mappings = {
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "react.js": "react",
        "vue.js": "vue",
        "node": "node.js",
        "postgres": "postgresql",
        "mongo": "mongodb"
    }
    
    normalized1 = skill_mappings.get(skill1, skill1)
    normalized2 = skill_mappings.get(skill2, skill2)
    
    if normalized1 == normalized2:
        return 0.9
    
    # Simple substring matching
    if skill1 in skill2 or skill2 in skill1:
        return 0.7
    
    # Character overlap ratio
    common_chars = set(normalized1) & set(normalized2)
    total_chars = set(normalized1) | set(normalized2)
    
    return len(common_chars) / len(total_chars) if total_chars else 0.0


def _score_experience_relevance(experiences: List[Dict], jd_text: str, jd_requirements: List[str]) -> List[Dict]:
    """Score work experience entries based on job relevance."""
    if not experiences or not jd_text:
        return experiences
    
    jd_lower = jd_text.lower()
    
    # Extract key terms from job description
    jd_keywords = set()
    
    # Industry-specific terms
    industry_patterns = {
        "tech": r"\b(software|developer|engineer|programming|coding|technical|system|platform|architecture)\b",
        "management": r"\b(manage|lead|supervise|direct|coordinate|oversee|strategy|planning)\b",
        "sales": r"\b(sales|revenue|client|customer|business development|account|relationship)\b",
        "marketing": r"\b(marketing|campaign|brand|digital|social media|analytics|growth)\b"
    }
    
    for pattern in industry_patterns.values():
        try:
            matches = re.findall(pattern, jd_text, re.I)
            jd_keywords.update(match.lower() for match in matches)
        except re.error:
            continue
    
    # Score each experience
    scored_experiences = []
    for exp in experiences:
        relevance_score = 0.0
        matching_keywords = []
        
        # Check title relevance
        title = exp.get("title", "").lower()
        for keyword in jd_keywords:
            if keyword in title:
                relevance_score += 0.3
                matching_keywords.append(keyword)
        
        # Check company/industry relevance
        company = exp.get("company", "").lower()
        if any(keyword in company for keyword in jd_keywords):
            relevance_score += 0.2
        
        # Check description relevance
        description = " ".join(exp.get("description", [])).lower()
        for keyword in jd_keywords:
            if keyword in description:
                relevance_score += 0.1
                if keyword not in matching_keywords:
                    matching_keywords.append(keyword)
        
        # Bonus for recent experience (if duration available)
        duration = exp.get("duration", "")
        if "2023" in duration or "2024" in duration or "present" in duration.lower() or "current" in duration.lower():
            relevance_score += 0.2
        
        scored_experiences.append({
            **exp,
            "relevance_score": min(1.0, relevance_score),
            "matching_keywords": matching_keywords[:5],
            "relevance_reasons": _generate_relevance_reasons(exp, matching_keywords)
        })
    
    # Sort by relevance score
    return sorted(scored_experiences, key=lambda x: x["relevance_score"], reverse=True)


def _generate_relevance_reasons(experience: Dict, matching_keywords: List[str]) -> List[str]:
    """Generate human-readable reasons for experience relevance."""
    reasons = []
    
    if matching_keywords:
        reasons.append(f"Relevant keywords: {', '.join(matching_keywords[:3])}")
    
    title = experience.get("title", "")
    if any(keyword in title.lower() for keyword in ["senior", "lead", "manager", "director"]):
        reasons.append("Leadership experience")
    
    duration = experience.get("duration", "")
    if "present" in duration.lower() or "current" in duration.lower():
        reasons.append("Current role")
    elif any(year in duration for year in ["2023", "2024"]):
        reasons.append("Recent experience")
    
    return reasons[:3]


def _create_cv_preprocessing_pipeline(cv_text: str, file_format: str = "unknown") -> Dict[str, any]:
    """Create preprocessing pipeline for different CV formats."""
    if not cv_text:
        return {"processed_text": "", "format_info": {}, "preprocessing_steps": []}
    
    preprocessing_steps = []
    processed_text = cv_text
    format_info = {"detected_format": file_format, "confidence": 0.0}
    
    # Step 1: Format detection and normalization
    if file_format == "unknown":
        format_info = _detect_cv_format(cv_text)
        preprocessing_steps.append(f"Format detection: {format_info['detected_format']}")
    
    # Step 2: Text cleaning based on format
    if format_info["detected_format"] == "pdf_with_tables":
        processed_text = _clean_pdf_table_artifacts(processed_text)
        preprocessing_steps.append("Cleaned PDF table artifacts")
    elif format_info["detected_format"] == "docx_formatted":
        processed_text = _clean_docx_formatting(processed_text)
        preprocessing_steps.append("Cleaned DOCX formatting")
    elif format_info["detected_format"] == "plain_text":
        processed_text = _standardize_plain_text(processed_text)
        preprocessing_steps.append("Standardized plain text")
    
    # Step 3: Universal cleaning
    processed_text = _universal_cv_cleaning(processed_text)
    preprocessing_steps.append("Applied universal cleaning")
    
    # Step 4: Section standardization
    processed_text = _standardize_cv_sections(processed_text)
    preprocessing_steps.append("Standardized section headers")
    
    # Step 5: Content validation
    validation_results = _validate_cv_content_quality(processed_text)
    preprocessing_steps.append(f"Content validation: {validation_results['quality_score']:.2f}")
    
    return {
        "processed_text": processed_text,
        "format_info": format_info,
        "preprocessing_steps": preprocessing_steps,
        "validation_results": validation_results
    }


def _detect_cv_format(cv_text: str) -> Dict[str, any]:
    """Detect CV format based on content patterns."""
    format_indicators = {
        "pdf_with_tables": {
            "patterns": [r"\s{3,}\|\s{3,}", r"\n\s*\n\s*\n", r"[A-Z]{2,}\s{5,}[A-Z]{2,}"],
            "score": 0.0
        },
        "docx_formatted": {
            "patterns": [r"\u2022", r"\u2013", r"\u2014", r"\t+"],
            "score": 0.0
        },
        "linkedin_export": {
            "patterns": [r"LinkedIn", r"Connections?", r"Profile", r"Experience at"],
            "score": 0.0
        },
        "ats_formatted": {
            "patterns": [r"^[A-Z\s]+$", r"\n[A-Z][a-z]+:\n", r"Skills?:\s*\n"],
            "score": 0.0
        },
        "plain_text": {
            "patterns": [r"^[a-zA-Z\s]+$", r"\n\n+"],
            "score": 0.0
        }
    }
    
    # Score each format
    for format_type, info in format_indicators.items():
        for pattern in info["patterns"]:
            try:
                matches = len(re.findall(pattern, cv_text, re.M))
                info["score"] += matches * 0.1
            except re.error:
                continue
    
    # Determine best format
    best_format = max(format_indicators.items(), key=lambda x: x[1]["score"])
    
    return {
        "detected_format": best_format[0],
        "confidence": min(1.0, best_format[1]["score"]),
        "all_scores": {k: v["score"] for k, v in format_indicators.items()}
    }


def _clean_pdf_table_artifacts(text: str) -> str:
    """Clean artifacts from PDF table extraction."""
    # Remove excessive whitespace from table extraction
    text = re.sub(r"\s{3,}", " ", text)
    # Fix broken lines from table cells
    text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
    # Remove table borders
    text = re.sub(r"[|_-]{3,}", "", text)
    return text.strip()


def _clean_docx_formatting(text: str) -> str:
    """Clean DOCX formatting artifacts."""
    # Replace bullet characters
    text = re.sub(r"[\u2022\u2023\u25E6]", "•", text)
    # Replace em/en dashes
    text = re.sub(r"[\u2013\u2014]", "-", text)
    # Remove excessive tabs
    text = re.sub(r"\t+", " ", text)
    return text.strip()


def _standardize_plain_text(text: str) -> str:
    """Standardize plain text CV format."""
    # Ensure consistent line breaks
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\r", "\n", text)
    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _universal_cv_cleaning(text: str) -> str:
    """Apply universal cleaning to all CV formats."""
    # Remove email signatures and footers
    text = re.sub(r"Sent from my .*", "", text, flags=re.I)
    text = re.sub(r"This email.*confidential.*", "", text, flags=re.I | re.DOTALL)
    
    # Remove page numbers and headers
    text = re.sub(r"Page \d+ of \d+", "", text, flags=re.I)
    text = re.sub(r"^\d+\s*$", "", text, flags=re.M)
    
    # Standardize phone number formats
    text = re.sub(r"\(?(\d{3})\)?[-\s]?(\d{3})[-\s]?(\d{4})", r"(\1) \2-\3", text)
    
    # Clean up excessive punctuation
    text = re.sub(r"[.]{3,}", "...", text)
    text = re.sub(r"[-]{3,}", "---", text)
    
    return text.strip()


def _standardize_cv_sections(text: str) -> str:
    """Standardize CV section headers."""
    section_mappings = {
        r"(?i)^(work experience|employment history|professional experience|career history)\s*:?\s*$": "EXPERIENCE",
        r"(?i)^(education|academic background|qualifications)\s*:?\s*$": "EDUCATION",
        r"(?i)^(skills|technical skills|core competencies|technologies)\s*:?\s*$": "SKILLS",
        r"(?i)^(achievements|accomplishments|awards)\s*:?\s*$": "ACHIEVEMENTS",
        r"(?i)^(certifications?|certificates?|licenses?)\s*:?\s*$": "CERTIFICATIONS",
        r"(?i)^(projects?|portfolio)\s*:?\s*$": "PROJECTS",
        r"(?i)^(summary|profile|objective|about)\s*:?\s*$": "SUMMARY"
    }
    
    for pattern, replacement in section_mappings.items():
        try:
            text = re.sub(pattern, replacement, text, flags=re.M)
        except re.error:
            continue
    
    return text


def _validate_cv_content_quality(text: str) -> Dict[str, any]:
    """Validate CV content quality after preprocessing."""
    quality_metrics = {
        "length_score": 0.0,
        "structure_score": 0.0,
        "contact_score": 0.0,
        "content_score": 0.0,
        "quality_score": 0.0
    }
    
    if not text:
        return quality_metrics
    
    # Length scoring (optimal: 300-2000 words)
    word_count = len(text.split())
    if 300 <= word_count <= 2000:
        quality_metrics["length_score"] = 1.0
    elif 200 <= word_count <= 3000:
        quality_metrics["length_score"] = 0.8
    else:
        quality_metrics["length_score"] = 0.5
    
    # Structure scoring (presence of key sections)
    key_sections = ["EXPERIENCE", "EDUCATION", "SKILLS"]
    found_sections = sum(1 for section in key_sections if section in text.upper())
    quality_metrics["structure_score"] = found_sections / len(key_sections)
    
    # Contact information scoring
    has_email = bool(re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text))
    has_phone = bool(re.search(r"\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}", text))
    quality_metrics["contact_score"] = (has_email + has_phone) / 2
    
    # Content richness scoring
    has_quantified_achievements = bool(re.search(r"\d+(?:%|\$|k|million|billion)", text))
    has_action_verbs = bool(re.search(r"\b(managed|led|developed|created|improved|increased)\b", text, re.I))
    has_technical_terms = bool(re.search(r"\b(Python|Java|JavaScript|AWS|Docker|SQL)\b", text, re.I))
    quality_metrics["content_score"] = (has_quantified_achievements + has_action_verbs + has_technical_terms) / 3
    
    # Overall quality score
    quality_metrics["quality_score"] = (
        quality_metrics["length_score"] * 0.2 +
        quality_metrics["structure_score"] * 0.3 +
        quality_metrics["contact_score"] * 0.2 +
        quality_metrics["content_score"] * 0.3
    )
    
    return quality_metrics


def _get_cv_cache_key(cv_text: str) -> str:
    """Generate cache key for CV content."""
    return hashlib.md5(cv_text.encode('utf-8')).hexdigest()


def _cache_cv_data(cache_key: str, data: Dict) -> None:
    """Cache extracted CV data with TTL."""
    with CACHE_LOCK:
        CV_CACHE[cache_key] = {
            "data": data,
            "timestamp": datetime.now(),
            "ttl": CACHE_TTL
        }
        
        # Clean expired entries
        current_time = datetime.now()
        expired_keys = [
            key for key, value in CV_CACHE.items()
            if current_time - value["timestamp"] > timedelta(seconds=value["ttl"])
        ]
        for key in expired_keys:
            del CV_CACHE[key]


def _get_cached_cv_data(cache_key: str) -> Optional[Dict]:
    """Retrieve cached CV data if valid."""
    with CACHE_LOCK:
        if cache_key in CV_CACHE:
            cached_entry = CV_CACHE[cache_key]
            if datetime.now() - cached_entry["timestamp"] <= timedelta(seconds=cached_entry["ttl"]):
                return cached_entry["data"]
            else:
                # Remove expired entry
                del CV_CACHE[cache_key]
    return None


def extract_cv_content_with_caching(cv_text: str, file_format: str = "unknown") -> Dict[str, any]:
    """Extract CV content with caching and preprocessing pipeline."""
    if not cv_text:
        return {"structured_content": {}, "preprocessing_info": {}, "cached": False}
    
    # Check cache first
    cache_key = _get_cv_cache_key(cv_text)
    cached_data = _get_cached_cv_data(cache_key)
    
    if cached_data:
        return {**cached_data, "cached": True}
    
    # Process CV through pipeline
    preprocessing_result = _create_cv_preprocessing_pipeline(cv_text, file_format)
    processed_text = preprocessing_result["processed_text"]
    
    # Extract structured content
    structured_content = _extract_structured_cv_content(processed_text)
    
    # Calculate skills-job matching (placeholder - requires job description)
    # skills_match = _calculate_skills_job_match(structured_content.get("skills", []), "", [])
    
    # Score experience relevance (placeholder - requires job description)
    # scored_experience = _score_experience_relevance(structured_content.get("experience", []), "", [])
    
    result = {
        "structured_content": structured_content,
        "preprocessing_info": preprocessing_result,
        "cached": False
    }
    
    # Cache the result
    _cache_cv_data(cache_key, result)
    
    return result


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
        
        # Extract structured CV content with caching and preprocessing
        cv_extraction_result = extract_cv_content_with_caching(cv_text or "")
        structured_cv = cv_extraction_result["structured_content"]
        contacts = _extract_contacts(cv_text) if cv_text else {}
        company_name = _extract_company_name(jd_text)
        key_requirements = _extract_key_requirements(jd_text)
        
        # Calculate skills-job matching
        skills_match = _calculate_skills_job_match(structured_cv.get("skills", []), jd_text, key_requirements)
        
        # Score experience relevance
        scored_experience = _score_experience_relevance(structured_cv.get("experience", []), jd_text, key_requirements)
        
        # Validate CV content ownership (placeholder for user profile integration)
        # validation_scores = _validate_cv_content_ownership(contacts, user_profile)
        
        # Intelligent CV truncation
        truncated_cv = _intelligent_cv_truncation(cv_text or "", 3000)
        
        # Select prompt variant
        variant = _select_prompt_variant(industry, "cover_letter")
    except Exception:
        # Fallback to basic prompt if extraction fails
        industry = "general"
        industry_config = INDUSTRY_TEMPLATES["general"]
        structured_cv = {}
        contacts = {}
        company_name = ""
        key_requirements = []
        truncated_cv = cv_text[:3000] if cv_text else ""
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
        "STRUCTURED CV DATA:\n"
        f"Matched Skills ({skills_match['match_score']:.1%}): {', '.join([s.get('name', '') for s in skills_match['matched_skills'][:8]])}\n"
        f"Top Experience: {'; '.join([f"{exp.get('title', '')} at {exp.get('company', '')} (relevance: {exp.get('relevance_score', 0):.1f})" for exp in scored_experience[:3]])}\n"
        f"Education: {'; '.join([f"{ed.get('degree', '')} from {ed.get('institution', '')}" for ed in structured_cv.get('education', [])][:2])}\n"
        f"Key Achievements: {'; '.join([ach.get('text', '')[:80] for ach in structured_cv.get('achievements', [])][:3])}\n"
        f"Skill Gaps: {'; '.join([gap.get('missing_skill', '') for gap in skills_match.get('skill_gaps', [])][:3])}\n\n"
        "FULL CV CONTENT:\n" + truncated_cv + "\n\n"
        f"Generate a {variant.replace('_', ' ')} cover letter using structured data and achievements."
    )


def _build_cv_prompt(jd_text: str, cv_text: str | None, template: str = "classic") -> str:
    """Build CV prompt with industry-specific templates and dynamic formatting."""
    try:
        industry = _detect_industry(jd_text)
        industry_config = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["general"])
        
        # Extract structured CV content with caching and preprocessing
        cv_extraction_result = extract_cv_content_with_caching(cv_text or "")
        structured_cv = cv_extraction_result["structured_content"]
        contacts = _extract_contacts(cv_text) if cv_text else {}
        key_requirements = _extract_key_requirements(jd_text)
        
        # Calculate skills-job matching
        skills_match = _calculate_skills_job_match(structured_cv.get("skills", []), jd_text, key_requirements)
        
        # Score experience relevance
        scored_experience = _score_experience_relevance(structured_cv.get("experience", []), jd_text, key_requirements)
        
        # Validate CV content ownership (placeholder for user profile integration)
        # validation_scores = _validate_cv_content_ownership(contacts, user_profile)
        
        # Intelligent CV truncation
        truncated_cv = _intelligent_cv_truncation(cv_text or "", 4000)
        
        # Select prompt variant
        variant = _select_prompt_variant(industry, "cv")
    except Exception:
        # Fallback to basic prompt if extraction fails
        industry = "general"
        industry_config = INDUSTRY_TEMPLATES["general"]
        structured_cv = {}
        contacts = {}
        key_requirements = []
        truncated_cv = cv_text[:4000] if cv_text else ""
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
        "STRUCTURED CV DATA:\n"
        f"Matched Skills ({skills_match['match_score']:.1%}): {', '.join([s.get('name', '') for s in skills_match['matched_skills'][:12]])}\n"
        f"Relevant Experience: {'; '.join([f"{exp.get('title', '')} at {exp.get('company', '')} ({exp.get('duration', '')}) - {exp.get('relevance_score', 0):.1f}" for exp in scored_experience[:4]])}\n"
        f"Education: {'; '.join([f"{ed.get('degree', '')} from {ed.get('institution', '')} ({ed.get('year', '')})" for ed in structured_cv.get('education', [])][:3])}\n"
        f"Key Achievements: {'; '.join([ach.get('text', '')[:100] for ach in structured_cv.get('achievements', [])][:5])}\n"
        f"Missing Skills: {'; '.join([gap.get('missing_skill', '') for gap in skills_match.get('skill_gaps', [])][:4])}\n\n"
        "SOURCE CV CONTENT:\n" + truncated_cv + "\n\n"
        f"Generate a {variant.replace('_', ' ')} CV using structured data for maximum ATS compatibility and relevance."
    )


def generate_cover_letter(jd_text: str, cv_text: str | None = None, user_id: str = "anonymous") -> Tuple[str, str, List[Dict]]:
    """
    Returns (provider_used, content, trace)
    - Enhanced with ML quality prediction, A/B testing, and semantic caching
    - Uses AI_DRY_RUN=true (default) to return deterministic content without external calls.
    """
    ai_dry_run = _bool_env("AI_DRY_RUN", True)
    trace: List[Dict] = []
    
    # A/B Testing: Assign variant
    generation_variant = "control"
    if AB_TESTING_ENABLED:
        generation_variant = assign_generation_variant(user_id, "cover_letter")
        trace.append({"ab_test_variant": generation_variant})
    
    # Build prompt for caching (variant-aware)
    prompt = _build_cover_prompt(jd_text or "", cv_text or "", variant=generation_variant)
    
    # Semantic Caching: Check for similar cached responses
    if SEMANTIC_CACHE_ENABLED:
        cached_response = get_semantic_cached_response(
            prompt, 
            "cover_letter", 
            {"variant": generation_variant, "industry": _detect_industry(jd_text)}
        )
        if cached_response:
            trace.append({"provider": "semantic_cache", "status": "hit", "duration_ms": 0})
            return "semantic_cache", cached_response, trace
    
    # ML Quality Prediction: Predict quality before generation
    ml_prediction = None
    if ML_QUALITY_ENABLED:
        try:
            cv_extraction_result = extract_cv_content_with_caching(cv_text or "")
            structured_cv = cv_extraction_result["structured_content"]
            skills_match = _calculate_skills_job_match(structured_cv.get("skills", []), jd_text, _extract_key_requirements(jd_text))
            scored_experience = _score_experience_relevance(structured_cv.get("experience", []), jd_text, _extract_key_requirements(jd_text))
            
            ml_prediction = predict_generation_quality(
                jd_text=jd_text,
                cv_text=cv_text or "",
                industry=_detect_industry(jd_text),
                template="standard",
                variant=generation_variant,
                provider="predicted",
                skills_match=skills_match,
                experience_scores=scored_experience
            )
            trace.append({"ml_prediction": ml_prediction})
        except Exception as e:
            logging.warning(f"ML quality prediction failed: {e}")
    
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
            
            # ML Quality Prediction and Feedback Collection
            ml_prediction = None
            if ML_QUALITY_ENABLED:
                try:
                    # Extract features for ML feedback
                    cv_extraction_result = extract_cv_content_with_caching(cv_text or "")
                    structured_cv = cv_extraction_result["structured_content"]
                    skills_match = _calculate_skills_job_match(structured_cv.get("skills", []), jd_text, _extract_key_requirements(jd_text))
                    scored_experience = _score_experience_relevance(structured_cv.get("experience", []), jd_text, _extract_key_requirements(jd_text))
                    
                    features = feature_extractor.extract_features(
                        jd_text=jd_text,
                        cv_text=cv_text or "",
                        generated_content=out,
                        industry=_detect_industry(jd_text),
                        template="standard",
                        variant="standard",
                        provider=provider,
                        generation_time_ms=dt,
                        skills_match=skills_match,
                        experience_scores=scored_experience
                    )
                    
                    # Collect feedback for model training
                    collect_quality_feedback(features, out, quality_scores)
                    
                except Exception as e:
                    logging.warning(f"ML quality feedback collection failed: {e}")
            
            trace.append({
                "provider": provider, 
                "status": "success", 
                "duration_ms": dt,
                "quality_score": quality_scores["overall"],
                "quality_breakdown": quality_scores,
                "ml_prediction": ml_prediction
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
