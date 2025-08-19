"""
Advanced Semantic Caching System
Caches AI responses based on semantic similarity rather than exact matches.
"""

import os
import json
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD

logger = logging.getLogger(__name__)

@dataclass
class SemanticCacheEntry:
    """Entry in the semantic cache."""
    cache_key: str
    content_hash: str
    prompt_text: str
    response_text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    created_at: datetime
    last_accessed: datetime
    access_count: int
    quality_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_accessed'] = self.last_accessed.isoformat()
        return data

class SemanticEmbedder:
    """Creates semantic embeddings for text using TF-IDF and SVD."""
    
    def __init__(self, max_features: int = 5000, n_components: int = 300):
        self.max_features = max_features
        self.n_components = n_components
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95
        )
        self.svd = TruncatedSVD(n_components=n_components, random_state=42)
        self.is_fitted = False
        self.lock = threading.Lock()
    
    def fit(self, texts: List[str]):
        """Fit the embedder on a corpus of texts."""
        if not texts:
            return
        
        with self.lock:
            try:
                # Fit TF-IDF vectorizer
                tfidf_matrix = self.vectorizer.fit_transform(texts)
                
                # Fit SVD for dimensionality reduction
                self.svd.fit(tfidf_matrix)
                self.is_fitted = True
                
                logger.info(f"Semantic embedder fitted on {len(texts)} texts")
            except Exception as e:
                logger.error(f"Failed to fit semantic embedder: {e}")
    
    def embed(self, text: str) -> Optional[List[float]]:
        """Create semantic embedding for text."""
        if not self.is_fitted:
            # Use simple word-based embedding as fallback
            return self._simple_embedding(text)
        
        try:
            # Transform text to TF-IDF
            tfidf_vector = self.vectorizer.transform([text])
            
            # Apply SVD for dimensionality reduction
            embedding = self.svd.transform(tfidf_vector)[0]
            
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"Failed to create embedding: {e}")
            return self._simple_embedding(text)
    
    def _simple_embedding(self, text: str) -> List[float]:
        """Simple word-based embedding as fallback."""
        words = text.lower().split()
        
        # Create a simple hash-based embedding
        embedding = [0.0] * 100
        for i, word in enumerate(words[:50]):  # Use first 50 words
            hash_val = hash(word) % 100
            embedding[hash_val] += 1.0 / (i + 1)  # Weight by position
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between embeddings."""
        try:
            return float(cosine_similarity([embedding1], [embedding2])[0][0])
        except Exception:
            return 0.0

class SemanticCache:
    """Advanced semantic caching system."""
    
    def __init__(self, 
                 cache_file: str = "semantic_cache.json",
                 max_entries: int = 1000,
                 similarity_threshold: float = 0.85,
                 ttl_hours: int = 24):
        self.cache_file = cache_file
        self.max_entries = max_entries
        self.similarity_threshold = similarity_threshold
        self.ttl = timedelta(hours=ttl_hours)
        
        self.entries: Dict[str, SemanticCacheEntry] = {}
        self.embedder = SemanticEmbedder()
        self.lock = threading.Lock()
        
        self._load_cache()
        self._fit_embedder()
    
    def _load_cache(self):
        """Load existing cache from file."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    
                    for entry_data in data.get('entries', []):
                        entry = SemanticCacheEntry(
                            cache_key=entry_data['cache_key'],
                            content_hash=entry_data['content_hash'],
                            prompt_text=entry_data['prompt_text'],
                            response_text=entry_data['response_text'],
                            embedding=entry_data['embedding'],
                            metadata=entry_data['metadata'],
                            created_at=datetime.fromisoformat(entry_data['created_at']),
                            last_accessed=datetime.fromisoformat(entry_data['last_accessed']),
                            access_count=entry_data['access_count'],
                            quality_score=entry_data['quality_score']
                        )
                        self.entries[entry.cache_key] = entry
                        
                logger.info(f"Loaded {len(self.entries)} semantic cache entries")
        except Exception as e:
            logger.warning(f"Could not load semantic cache: {e}")
    
    def _save_cache(self):
        """Save cache to file."""
        try:
            data = {
                'entries': [entry.to_dict() for entry in self.entries.values()],
                'last_updated': datetime.now().isoformat(),
                'total_entries': len(self.entries)
            }
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save semantic cache: {e}")
    
    def _fit_embedder(self):
        """Fit embedder on existing cache entries."""
        if self.entries:
            texts = [entry.prompt_text for entry in self.entries.values()]
            self.embedder.fit(texts)
    
    def _cleanup_expired(self):
        """Remove expired cache entries."""
        now = datetime.now()
        expired_keys = []
        
        for key, entry in self.entries.items():
            if now - entry.created_at > self.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.entries[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _evict_lru(self):
        """Evict least recently used entries if cache is full."""
        if len(self.entries) <= self.max_entries:
            return
        
        # Sort by last accessed time and remove oldest
        sorted_entries = sorted(
            self.entries.items(),
            key=lambda x: x[1].last_accessed
        )
        
        entries_to_remove = len(self.entries) - self.max_entries
        for i in range(entries_to_remove):
            key = sorted_entries[i][0]
            del self.entries[key]
        
        logger.info(f"Evicted {entries_to_remove} LRU cache entries")
    
    def get(self, prompt: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get cached response for semantically similar prompt."""
        if not prompt.strip():
            return None
        
        with self.lock:
            self._cleanup_expired()
            
            # Create embedding for the prompt
            query_embedding = self.embedder.embed(prompt)
            if not query_embedding:
                return None
            
            # Find most similar cached entry
            best_match = None
            best_similarity = 0.0
            
            for entry in self.entries.values():
                similarity = self.embedder.similarity(query_embedding, entry.embedding)
                
                # Consider metadata matching for higher relevance
                metadata_bonus = 0.0
                if metadata and entry.metadata:
                    common_keys = set(metadata.keys()) & set(entry.metadata.keys())
                    if common_keys:
                        matching_values = sum(
                            1 for key in common_keys 
                            if metadata[key] == entry.metadata[key]
                        )
                        metadata_bonus = (matching_values / len(common_keys)) * 0.1
                
                total_similarity = similarity + metadata_bonus
                
                if total_similarity > best_similarity and total_similarity >= self.similarity_threshold:
                    best_similarity = total_similarity
                    best_match = entry
            
            if best_match:
                # Update access statistics
                best_match.last_accessed = datetime.now()
                best_match.access_count += 1
                
                logger.info(f"Semantic cache hit with similarity {best_similarity:.3f}")
                return best_match.response_text
            
            return None
    
    def put(self, 
            prompt: str, 
            response: str, 
            quality_score: float = 0.5,
            metadata: Optional[Dict[str, Any]] = None):
        """Cache a prompt-response pair with semantic embedding."""
        if not prompt.strip() or not response.strip():
            return
        
        with self.lock:
            # Create cache key
            cache_key = hashlib.md5(f"{prompt}:{response}".encode()).hexdigest()
            
            # Skip if already cached
            if cache_key in self.entries:
                return
            
            # Create embedding
            embedding = self.embedder.embed(prompt)
            if not embedding:
                return
            
            # Create cache entry
            entry = SemanticCacheEntry(
                cache_key=cache_key,
                content_hash=hashlib.md5(response.encode()).hexdigest(),
                prompt_text=prompt,
                response_text=response,
                embedding=embedding,
                metadata=metadata or {},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=0,
                quality_score=quality_score
            )
            
            self.entries[cache_key] = entry
            
            # Cleanup and eviction
            self._cleanup_expired()
            self._evict_lru()
            
            # Re-fit embedder periodically
            if len(self.entries) % 50 == 0:
                texts = [e.prompt_text for e in self.entries.values()]
                self.embedder.fit(texts)
            
            # Save periodically
            if len(self.entries) % 10 == 0:
                self._save_cache()
            
            logger.info(f"Added semantic cache entry with quality {quality_score:.3f}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.entries:
            return {"total_entries": 0}
        
        now = datetime.now()
        access_counts = [entry.access_count for entry in self.entries.values()]
        quality_scores = [entry.quality_score for entry in self.entries.values()]
        ages = [(now - entry.created_at).total_seconds() / 3600 for entry in self.entries.values()]
        
        return {
            "total_entries": len(self.entries),
            "average_access_count": np.mean(access_counts),
            "average_quality_score": np.mean(quality_scores),
            "average_age_hours": np.mean(ages),
            "embedder_fitted": self.embedder.is_fitted,
            "similarity_threshold": self.similarity_threshold,
            "cache_hit_potential": len([e for e in self.entries.values() if e.access_count > 0])
        }
    
    def clear_low_quality(self, min_quality: float = 0.3):
        """Remove low-quality cache entries."""
        with self.lock:
            low_quality_keys = [
                key for key, entry in self.entries.items()
                if entry.quality_score < min_quality
            ]
            
            for key in low_quality_keys:
                del self.entries[key]
            
            if low_quality_keys:
                logger.info(f"Removed {len(low_quality_keys)} low-quality cache entries")
                self._save_cache()

# Global semantic cache instance
semantic_cache = SemanticCache()

def get_semantic_cached_response(prompt: str, 
                                generation_type: str,
                                metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Get semantically cached response."""
    cache_metadata = {"generation_type": generation_type, **(metadata or {})}
    return semantic_cache.get(prompt, cache_metadata)

def cache_semantic_response(prompt: str,
                          response: str,
                          generation_type: str,
                          quality_score: float,
                          metadata: Optional[Dict[str, Any]] = None):
    """Cache response with semantic indexing."""
    cache_metadata = {"generation_type": generation_type, **(metadata or {})}
    semantic_cache.put(prompt, response, quality_score, cache_metadata)

def get_semantic_cache_stats() -> Dict[str, Any]:
    """Get semantic cache statistics."""
    return semantic_cache.get_stats()
