"""
Real-time A/B Testing Framework with Statistical Analysis
Enables testing different AI generation strategies and measuring performance.
"""

import os
import json
import hashlib
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import logging
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

@dataclass
class ABTestConfig:
    """Configuration for an A/B test."""
    test_id: str
    name: str
    description: str
    variants: List[str]  # e.g., ["control", "variant_a", "variant_b"]
    traffic_split: Dict[str, float]  # e.g., {"control": 0.5, "variant_a": 0.3, "variant_b": 0.2}
    start_date: datetime
    end_date: Optional[datetime]
    target_metric: str  # e.g., "quality_score", "user_satisfaction", "generation_time"
    minimum_sample_size: int
    statistical_significance: float  # e.g., 0.05 for 95% confidence
    is_active: bool
    created_by: str
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['start_date'] = self.start_date.isoformat()
        data['end_date'] = self.end_date.isoformat() if self.end_date else None
        return data

@dataclass
class ABTestEvent:
    """Individual event in an A/B test."""
    test_id: str
    user_id: str
    variant: str
    timestamp: datetime
    metrics: Dict[str, float]  # e.g., {"quality_score": 0.85, "generation_time_ms": 1200}
    metadata: Dict[str, Any]  # Additional context
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

class ABTestManager:
    """Manages A/B tests and statistical analysis."""
    
    def __init__(self, data_file: str = "ab_test_data.json"):
        self.data_file = data_file
        self.tests: Dict[str, ABTestConfig] = {}
        self.events: List[ABTestEvent] = []
        self.lock = threading.Lock()
        self._load_data()
    
    def _load_data(self):
        """Load existing A/B test data."""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    
                    # Load tests
                    for test_data in data.get('tests', []):
                        test_config = ABTestConfig(
                            test_id=test_data['test_id'],
                            name=test_data['name'],
                            description=test_data['description'],
                            variants=test_data['variants'],
                            traffic_split=test_data['traffic_split'],
                            start_date=datetime.fromisoformat(test_data['start_date']),
                            end_date=datetime.fromisoformat(test_data['end_date']) if test_data['end_date'] else None,
                            target_metric=test_data['target_metric'],
                            minimum_sample_size=test_data['minimum_sample_size'],
                            statistical_significance=test_data['statistical_significance'],
                            is_active=test_data['is_active'],
                            created_by=test_data['created_by']
                        )
                        self.tests[test_config.test_id] = test_config
                    
                    # Load events
                    for event_data in data.get('events', []):
                        event = ABTestEvent(
                            test_id=event_data['test_id'],
                            user_id=event_data['user_id'],
                            variant=event_data['variant'],
                            timestamp=datetime.fromisoformat(event_data['timestamp']),
                            metrics=event_data['metrics'],
                            metadata=event_data['metadata']
                        )
                        self.events.append(event)
                        
        except Exception as e:
            logger.warning(f"Could not load A/B test data: {e}")
    
    def _save_data(self):
        """Save A/B test data to file."""
        try:
            data = {
                'tests': [test.to_dict() for test in self.tests.values()],
                'events': [event.to_dict() for event in self.events],
                'last_updated': datetime.now().isoformat()
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save A/B test data: {e}")
    
    def create_test(self, 
                   test_id: str,
                   name: str,
                   description: str,
                   variants: List[str],
                   traffic_split: Dict[str, float],
                   target_metric: str,
                   duration_days: int = 30,
                   minimum_sample_size: int = 100,
                   statistical_significance: float = 0.05,
                   created_by: str = "system") -> ABTestConfig:
        """Create a new A/B test."""
        
        # Validate traffic split
        if abs(sum(traffic_split.values()) - 1.0) > 0.01:
            raise ValueError("Traffic split must sum to 1.0")
        
        if set(variants) != set(traffic_split.keys()):
            raise ValueError("Variants and traffic split keys must match")
        
        with self.lock:
            if test_id in self.tests:
                raise ValueError(f"Test {test_id} already exists")
            
            test_config = ABTestConfig(
                test_id=test_id,
                name=name,
                description=description,
                variants=variants,
                traffic_split=traffic_split,
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=duration_days),
                target_metric=target_metric,
                minimum_sample_size=minimum_sample_size,
                statistical_significance=statistical_significance,
                is_active=True,
                created_by=created_by
            )
            
            self.tests[test_id] = test_config
            self._save_data()
            
            logger.info(f"Created A/B test: {test_id} - {name}")
            return test_config
    
    def assign_variant(self, test_id: str, user_id: str) -> Optional[str]:
        """Assign a user to a test variant."""
        if test_id not in self.tests:
            return None
        
        test = self.tests[test_id]
        
        # Check if test is active and within date range
        now = datetime.now()
        if not test.is_active or now < test.start_date:
            return None
        
        if test.end_date and now > test.end_date:
            return None
        
        # Use deterministic assignment based on user_id hash
        hash_input = f"{test_id}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        random_value = (hash_value % 10000) / 10000.0
        
        # Assign variant based on traffic split
        cumulative_probability = 0.0
        for variant, probability in test.traffic_split.items():
            cumulative_probability += probability
            if random_value <= cumulative_probability:
                return variant
        
        # Fallback to first variant
        return test.variants[0]
    
    def record_event(self, 
                    test_id: str,
                    user_id: str,
                    variant: str,
                    metrics: Dict[str, float],
                    metadata: Optional[Dict[str, Any]] = None):
        """Record an event for A/B test analysis."""
        
        if test_id not in self.tests:
            logger.warning(f"Unknown test ID: {test_id}")
            return
        
        event = ABTestEvent(
            test_id=test_id,
            user_id=user_id,
            variant=variant,
            timestamp=datetime.now(),
            metrics=metrics,
            metadata=metadata or {}
        )
        
        with self.lock:
            self.events.append(event)
            
            # Save periodically
            if len(self.events) % 10 == 0:
                self._save_data()
    
    def get_test_results(self, test_id: str) -> Dict[str, Any]:
        """Get statistical analysis results for a test."""
        if test_id not in self.tests:
            return {"error": "Test not found"}
        
        test = self.tests[test_id]
        test_events = [e for e in self.events if e.test_id == test_id]
        
        if not test_events:
            return {"error": "No events recorded"}
        
        # Group events by variant
        variant_data = defaultdict(list)
        for event in test_events:
            if test.target_metric in event.metrics:
                variant_data[event.variant].append(event.metrics[test.target_metric])
        
        # Calculate statistics for each variant
        variant_stats = {}
        for variant, values in variant_data.items():
            if values:
                variant_stats[variant] = {
                    "count": len(values),
                    "mean": np.mean(values),
                    "std": np.std(values),
                    "median": np.median(values),
                    "min": np.min(values),
                    "max": np.max(values),
                    "confidence_interval": self._calculate_confidence_interval(values, test.statistical_significance)
                }
        
        # Statistical significance testing
        significance_results = self._perform_significance_tests(variant_data, test.statistical_significance)
        
        # Determine winner
        winner = self._determine_winner(variant_stats, significance_results)
        
        # Calculate sample size adequacy
        sample_adequacy = self._check_sample_adequacy(variant_data, test.minimum_sample_size)
        
        return {
            "test_config": test.to_dict(),
            "variant_statistics": variant_stats,
            "significance_tests": significance_results,
            "winner": winner,
            "sample_adequacy": sample_adequacy,
            "total_events": len(test_events),
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def _calculate_confidence_interval(self, values: List[float], alpha: float) -> Tuple[float, float]:
        """Calculate confidence interval for a set of values."""
        if len(values) < 2:
            return (0.0, 0.0)
        
        mean = np.mean(values)
        sem = stats.sem(values)
        confidence_level = 1 - alpha
        h = sem * stats.t.ppf((1 + confidence_level) / 2, len(values) - 1)
        
        return (mean - h, mean + h)
    
    def _perform_significance_tests(self, variant_data: Dict[str, List[float]], alpha: float) -> Dict[str, Any]:
        """Perform statistical significance tests between variants."""
        variants = list(variant_data.keys())
        results = {}
        
        if len(variants) < 2:
            return {"error": "Need at least 2 variants for significance testing"}
        
        # Pairwise t-tests
        for i, variant_a in enumerate(variants):
            for variant_b in variants[i+1:]:
                data_a = variant_data[variant_a]
                data_b = variant_data[variant_b]
                
                if len(data_a) < 2 or len(data_b) < 2:
                    continue
                
                # Perform two-sample t-test
                t_stat, p_value = stats.ttest_ind(data_a, data_b)
                
                # Effect size (Cohen's d)
                pooled_std = np.sqrt(((len(data_a) - 1) * np.var(data_a) + 
                                    (len(data_b) - 1) * np.var(data_b)) / 
                                   (len(data_a) + len(data_b) - 2))
                cohens_d = (np.mean(data_a) - np.mean(data_b)) / pooled_std if pooled_std > 0 else 0
                
                results[f"{variant_a}_vs_{variant_b}"] = {
                    "t_statistic": float(t_stat),
                    "p_value": float(p_value),
                    "is_significant": p_value < alpha,
                    "effect_size_cohens_d": float(cohens_d),
                    "sample_size_a": len(data_a),
                    "sample_size_b": len(data_b)
                }
        
        # ANOVA for multiple variants
        if len(variants) > 2:
            variant_values = [variant_data[v] for v in variants if len(variant_data[v]) > 0]
            if len(variant_values) > 1:
                f_stat, p_value = stats.f_oneway(*variant_values)
                results["anova"] = {
                    "f_statistic": float(f_stat),
                    "p_value": float(p_value),
                    "is_significant": p_value < alpha
                }
        
        return results
    
    def _determine_winner(self, variant_stats: Dict[str, Dict], significance_results: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the winning variant based on statistical analysis."""
        if not variant_stats:
            return {"winner": None, "reason": "No data available"}
        
        # Find variant with highest mean
        best_variant = max(variant_stats.keys(), key=lambda v: variant_stats[v]["mean"])
        best_mean = variant_stats[best_variant]["mean"]
        
        # Check if the difference is statistically significant
        significant_wins = []
        for comparison, result in significance_results.items():
            if "anova" not in comparison and result.get("is_significant", False):
                variants = comparison.split("_vs_")
                if len(variants) == 2:
                    # Determine which variant performed better
                    mean_a = variant_stats[variants[0]]["mean"]
                    mean_b = variant_stats[variants[1]]["mean"]
                    winner = variants[0] if mean_a > mean_b else variants[1]
                    significant_wins.append(winner)
        
        # Determine overall winner
        if best_variant in significant_wins:
            return {
                "winner": best_variant,
                "mean_performance": best_mean,
                "confidence": "high",
                "reason": "Statistically significant improvement"
            }
        elif significant_wins:
            # Multiple significant winners, choose the one with highest mean among them
            winner_means = {v: variant_stats[v]["mean"] for v in significant_wins}
            winner = max(winner_means.keys(), key=lambda v: winner_means[v])
            return {
                "winner": winner,
                "mean_performance": winner_means[winner],
                "confidence": "medium",
                "reason": "Statistically significant among multiple variants"
            }
        else:
            return {
                "winner": best_variant,
                "mean_performance": best_mean,
                "confidence": "low",
                "reason": "Highest mean but not statistically significant"
            }
    
    def _check_sample_adequacy(self, variant_data: Dict[str, List[float]], minimum_sample_size: int) -> Dict[str, Any]:
        """Check if sample sizes are adequate for reliable results."""
        adequacy = {}
        
        for variant, values in variant_data.items():
            sample_size = len(values)
            is_adequate = sample_size >= minimum_sample_size
            adequacy[variant] = {
                "sample_size": sample_size,
                "minimum_required": minimum_sample_size,
                "is_adequate": is_adequate,
                "adequacy_ratio": sample_size / minimum_sample_size
            }
        
        overall_adequate = all(v["is_adequate"] for v in adequacy.values())
        
        return {
            "overall_adequate": overall_adequate,
            "variant_adequacy": adequacy,
            "recommendation": "Continue test" if not overall_adequate else "Test ready for conclusion"
        }
    
    def stop_test(self, test_id: str, reason: str = "Manual stop"):
        """Stop an active A/B test."""
        if test_id in self.tests:
            with self.lock:
                self.tests[test_id].is_active = False
                self.tests[test_id].end_date = datetime.now()
                self._save_data()
                logger.info(f"Stopped A/B test {test_id}: {reason}")
    
    def get_active_tests(self) -> List[ABTestConfig]:
        """Get all currently active tests."""
        now = datetime.now()
        return [
            test for test in self.tests.values()
            if test.is_active and test.start_date <= now and (not test.end_date or test.end_date > now)
        ]
    
    def get_test_summary(self) -> Dict[str, Any]:
        """Get summary of all tests."""
        active_tests = self.get_active_tests()
        total_events = len(self.events)
        
        return {
            "total_tests": len(self.tests),
            "active_tests": len(active_tests),
            "total_events": total_events,
            "active_test_ids": [test.test_id for test in active_tests],
            "recent_events": len([e for e in self.events if e.timestamp > datetime.now() - timedelta(days=7)])
        }

# Global A/B test manager instance
ab_test_manager = ABTestManager()

def assign_generation_variant(user_id: str, generation_type: str) -> str:
    """Assign a user to a generation variant for A/B testing."""
    test_id = f"{generation_type}_optimization"
    
    # Check if there's an active test for this generation type
    variant = ab_test_manager.assign_variant(test_id, user_id)
    
    if variant:
        return variant
    else:
        # Default to control if no active test
        return "control"

def record_generation_metrics(user_id: str, 
                            generation_type: str,
                            variant: str,
                            quality_score: float,
                            generation_time_ms: int,
                            provider: str,
                            metadata: Optional[Dict[str, Any]] = None):
    """Record metrics for A/B test analysis."""
    test_id = f"{generation_type}_optimization"
    
    metrics = {
        "quality_score": quality_score,
        "generation_time_ms": generation_time_ms
    }
    
    test_metadata = {
        "provider": provider,
        "generation_type": generation_type,
        **(metadata or {})
    }
    
    ab_test_manager.record_event(test_id, user_id, variant, metrics, test_metadata)

def create_generation_ab_test(generation_type: str,
                            variants: List[str],
                            traffic_split: Dict[str, float],
                            duration_days: int = 14) -> ABTestConfig:
    """Create an A/B test for generation optimization."""
    test_id = f"{generation_type}_optimization"
    
    return ab_test_manager.create_test(
        test_id=test_id,
        name=f"{generation_type.title()} Generation Optimization",
        description=f"Testing different {generation_type} generation strategies",
        variants=variants,
        traffic_split=traffic_split,
        target_metric="quality_score",
        duration_days=duration_days,
        minimum_sample_size=50,
        statistical_significance=0.05,
        created_by="system"
    )

def get_ab_test_results(generation_type: str) -> Dict[str, Any]:
    """Get A/B test results for a generation type."""
    test_id = f"{generation_type}_optimization"
    return ab_test_manager.get_test_results(test_id)

def get_ab_test_dashboard_data() -> Dict[str, Any]:
    """Get comprehensive A/B test data for dashboard."""
    summary = ab_test_manager.get_test_summary()
    active_tests = ab_test_manager.get_active_tests()
    
    test_results = {}
    for test in active_tests:
        test_results[test.test_id] = ab_test_manager.get_test_results(test.test_id)
    
    return {
        "summary": summary,
        "active_tests": [test.to_dict() for test in active_tests],
        "test_results": test_results,
        "last_updated": datetime.now().isoformat()
    }
