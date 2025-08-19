"""
Machine Learning Quality Prediction Models for AI Generation
Predicts quality scores for generated content before actual generation.
"""

import os
import json
import pickle
import numpy as np
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import threading
import logging

# Simple ML implementations without external dependencies
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

logger = logging.getLogger(__name__)

@dataclass
class QualityFeatures:
    """Features extracted for quality prediction."""
    # Content features
    content_length: int
    word_count: int
    sentence_count: int
    paragraph_count: int
    
    # CV-JD alignment features
    cv_jd_keyword_overlap: float
    skills_match_score: float
    experience_relevance_score: float
    
    # Industry and context features
    industry_type: str
    template_type: str
    generation_variant: str
    
    # Provider and timing features
    provider_used: str
    generation_time_ms: int
    
    # Historical features
    user_feedback_history: float
    provider_success_rate: float
    
    # Text quality features
    readability_score: float
    keyword_density: float
    professional_tone_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class QualityTarget:
    """Target quality scores for training."""
    overall_quality: float
    relevance_score: float
    professionalism_score: float
    ats_compatibility: float
    user_satisfaction: float  # From feedback
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class QualityDataCollector:
    """Collects training data for quality prediction models."""
    
    def __init__(self, data_file: str = "quality_training_data.json"):
        self.data_file = data_file
        self.training_data: List[Dict] = []
        self.lock = threading.Lock()
        self._load_existing_data()
    
    def _load_existing_data(self):
        """Load existing training data from file."""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    self.training_data = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load training data: {e}")
            self.training_data = []
    
    def collect_generation_data(self, 
                              features: QualityFeatures,
                              actual_content: str,
                              quality_scores: Dict[str, float],
                              user_feedback: Optional[float] = None):
        """Collect data point for training."""
        with self.lock:
            data_point = {
                "timestamp": datetime.now().isoformat(),
                "features": features.to_dict(),
                "actual_content": actual_content,
                "quality_scores": quality_scores,
                "user_feedback": user_feedback,
                "content_hash": hashlib.md5(actual_content.encode()).hexdigest()
            }
            
            self.training_data.append(data_point)
            
            # Save periodically
            if len(self.training_data) % 10 == 0:
                self._save_data()
    
    def _save_data(self):
        """Save training data to file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.training_data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save training data: {e}")
    
    def get_training_dataset(self, min_samples: int = 50) -> Tuple[List[Dict], List[Dict]]:
        """Get training dataset with features and targets."""
        if len(self.training_data) < min_samples:
            return [], []
        
        features = []
        targets = []
        
        for data_point in self.training_data:
            if data_point.get("quality_scores"):
                features.append(data_point["features"])
                targets.append(data_point["quality_scores"])
        
        return features, targets

class FeatureExtractor:
    """Extracts features for quality prediction."""
    
    def __init__(self):
        self.tfidf_vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        self.is_fitted = False
    
    def extract_features(self, 
                        jd_text: str,
                        cv_text: str,
                        generated_content: str,
                        industry: str,
                        template: str,
                        variant: str,
                        provider: str,
                        generation_time_ms: int,
                        skills_match: Dict,
                        experience_scores: List[Dict]) -> QualityFeatures:
        """Extract comprehensive features for quality prediction."""
        
        # Content analysis
        content_length = len(generated_content)
        word_count = len(generated_content.split())
        sentence_count = len([s for s in generated_content.split('.') if s.strip()])
        paragraph_count = len([p for p in generated_content.split('\n\n') if p.strip()])
        
        # CV-JD alignment
        cv_jd_overlap = self._calculate_keyword_overlap(cv_text, jd_text)
        skills_score = skills_match.get('match_score', 0.0)
        exp_score = np.mean([exp.get('relevance_score', 0.0) for exp in experience_scores]) if experience_scores else 0.0
        
        # Text quality metrics
        readability = self._calculate_readability_score(generated_content)
        keyword_density = self._calculate_keyword_density(generated_content, jd_text)
        professional_tone = self._calculate_professional_tone_score(generated_content)
        
        # Provider performance
        provider_success_rate = self._get_provider_success_rate(provider)
        
        return QualityFeatures(
            content_length=content_length,
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            cv_jd_keyword_overlap=cv_jd_overlap,
            skills_match_score=skills_score,
            experience_relevance_score=exp_score,
            industry_type=industry,
            template_type=template,
            generation_variant=variant,
            provider_used=provider,
            generation_time_ms=generation_time_ms,
            user_feedback_history=0.0,  # Will be updated with historical data
            provider_success_rate=provider_success_rate,
            readability_score=readability,
            keyword_density=keyword_density,
            professional_tone_score=professional_tone
        )
    
    def _calculate_keyword_overlap(self, text1: str, text2: str) -> float:
        """Calculate keyword overlap between two texts."""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_readability_score(self, text: str) -> float:
        """Simple readability score based on sentence and word length."""
        if not text:
            return 0.0
        
        sentences = [s for s in text.split('.') if s.strip()]
        if not sentences:
            return 0.0
        
        avg_sentence_length = np.mean([len(s.split()) for s in sentences])
        avg_word_length = np.mean([len(word) for word in text.split()])
        
        # Simple readability formula (lower is better)
        readability = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_word_length / len(text.split()))
        return max(0.0, min(1.0, readability / 100))
    
    def _calculate_keyword_density(self, content: str, jd_text: str) -> float:
        """Calculate density of job description keywords in content."""
        if not content or not jd_text:
            return 0.0
        
        jd_words = set(jd_text.lower().split())
        content_words = content.lower().split()
        
        keyword_count = sum(1 for word in content_words if word in jd_words)
        return keyword_count / len(content_words) if content_words else 0.0
    
    def _calculate_professional_tone_score(self, text: str) -> float:
        """Calculate professional tone score."""
        if not text:
            return 0.0
        
        professional_indicators = [
            'experience', 'skills', 'expertise', 'professional', 'accomplished',
            'achieved', 'managed', 'led', 'developed', 'implemented'
        ]
        
        casual_indicators = [
            'awesome', 'cool', 'super', 'amazing', 'totally', 'really'
        ]
        
        text_lower = text.lower()
        professional_count = sum(1 for word in professional_indicators if word in text_lower)
        casual_count = sum(1 for word in casual_indicators if word in text_lower)
        
        total_words = len(text.split())
        professional_ratio = professional_count / total_words if total_words else 0.0
        casual_penalty = casual_count / total_words if total_words else 0.0
        
        return max(0.0, min(1.0, professional_ratio - casual_penalty))
    
    def _get_provider_success_rate(self, provider: str) -> float:
        """Get historical success rate for provider."""
        # This would be implemented with actual provider statistics
        provider_rates = {
            "gemini": 0.92,
            "deepseek": 0.88,
            "groq": 0.85,
            "mock": 1.0,
            "intelligent_fallback": 0.75
        }
        return provider_rates.get(provider, 0.8)

class QualityPredictor:
    """Machine learning model for predicting content quality."""
    
    def __init__(self, model_file: str = "quality_model.pkl"):
        self.model_file = model_file
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_trained = False
        self.lock = threading.Lock()
        
        # Try to load existing model
        self._load_model()
    
    def _load_model(self):
        """Load existing trained model."""
        try:
            if os.path.exists(self.model_file):
                with open(self.model_file, 'rb') as f:
                    model_data = pickle.load(f)
                    self.model = model_data['model']
                    self.scaler = model_data['scaler']
                    self.feature_names = model_data['feature_names']
                    self.is_trained = True
                    logger.info("Loaded existing quality prediction model")
        except Exception as e:
            logger.warning(f"Could not load existing model: {e}")
    
    def _save_model(self):
        """Save trained model."""
        try:
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'trained_at': datetime.now().isoformat()
            }
            with open(self.model_file, 'wb') as f:
                pickle.dump(model_data, f)
            logger.info("Saved quality prediction model")
        except Exception as e:
            logger.error(f"Could not save model: {e}")
    
    def train(self, features_list: List[Dict], targets_list: List[Dict]):
        """Train the quality prediction model."""
        if len(features_list) < 10:
            logger.warning("Insufficient training data for quality prediction")
            return
        
        with self.lock:
            # Convert features to numerical format
            X, feature_names = self._features_to_matrix(features_list)
            
            # Extract target scores (overall quality as primary target)
            y = np.array([target.get('overall_quality', 0.5) for target in targets_list])
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train ensemble model
            self.model = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=6,
                random_state=42
            )
            
            self.model.fit(X_train_scaled, y_train)
            self.feature_names = feature_names
            self.is_trained = True
            
            # Evaluate model
            y_pred = self.model.predict(X_test_scaled)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            logger.info(f"Quality model trained - MSE: {mse:.4f}, R²: {r2:.4f}")
            
            # Save model
            self._save_model()
    
    def predict_quality(self, features: QualityFeatures) -> Dict[str, float]:
        """Predict quality scores for given features."""
        if not self.is_trained:
            # Return default scores if model not trained
            return {
                "predicted_overall": 0.7,
                "confidence": 0.5,
                "recommendation": "insufficient_training_data"
            }
        
        try:
            # Convert features to matrix format
            X, _ = self._features_to_matrix([features.to_dict()])
            X_scaled = self.scaler.transform(X)
            
            # Predict
            prediction = self.model.predict(X_scaled)[0]
            
            # Calculate confidence based on feature importance and historical accuracy
            confidence = self._calculate_prediction_confidence(features)
            
            # Generate recommendation
            recommendation = self._generate_recommendation(prediction, confidence, features)
            
            return {
                "predicted_overall": max(0.0, min(1.0, prediction)),
                "confidence": confidence,
                "recommendation": recommendation,
                "feature_importance": self._get_feature_importance()
            }
            
        except Exception as e:
            logger.error(f"Quality prediction error: {e}")
            return {
                "predicted_overall": 0.6,
                "confidence": 0.3,
                "recommendation": "prediction_error"
            }
    
    def _features_to_matrix(self, features_list: List[Dict]) -> Tuple[np.ndarray, List[str]]:
        """Convert feature dictionaries to numerical matrix."""
        if not features_list:
            return np.array([]), []
        
        # Define numerical features
        numerical_features = [
            'content_length', 'word_count', 'sentence_count', 'paragraph_count',
            'cv_jd_keyword_overlap', 'skills_match_score', 'experience_relevance_score',
            'generation_time_ms', 'user_feedback_history', 'provider_success_rate',
            'readability_score', 'keyword_density', 'professional_tone_score'
        ]
        
        # Define categorical features for one-hot encoding
        categorical_features = ['industry_type', 'template_type', 'generation_variant', 'provider_used']
        
        # Extract numerical features
        X_numerical = []
        for features in features_list:
            row = [features.get(feat, 0.0) for feat in numerical_features]
            X_numerical.append(row)
        
        X_numerical = np.array(X_numerical)
        
        # One-hot encode categorical features
        X_categorical = []
        categorical_names = []
        
        for cat_feat in categorical_features:
            unique_values = set()
            for features in features_list:
                unique_values.add(features.get(cat_feat, 'unknown'))
            
            for value in sorted(unique_values):
                categorical_names.append(f"{cat_feat}_{value}")
                column = [1 if features.get(cat_feat) == value else 0 for features in features_list]
                X_categorical.append(column)
        
        if X_categorical:
            X_categorical = np.array(X_categorical).T
            X = np.hstack([X_numerical, X_categorical])
            feature_names = numerical_features + categorical_names
        else:
            X = X_numerical
            feature_names = numerical_features
        
        return X, feature_names
    
    def _calculate_prediction_confidence(self, features: QualityFeatures) -> float:
        """Calculate confidence in prediction based on feature quality."""
        confidence_factors = []
        
        # Provider reliability
        confidence_factors.append(features.provider_success_rate)
        
        # Skills match quality
        confidence_factors.append(features.skills_match_score)
        
        # Content completeness
        if features.content_length > 100:
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.4)
        
        # Professional tone
        confidence_factors.append(features.professional_tone_score)
        
        return np.mean(confidence_factors)
    
    def _generate_recommendation(self, prediction: float, confidence: float, features: QualityFeatures) -> str:
        """Generate recommendation based on prediction."""
        if prediction >= 0.8 and confidence >= 0.7:
            return "high_quality_expected"
        elif prediction >= 0.6 and confidence >= 0.6:
            return "moderate_quality_expected"
        elif prediction < 0.5:
            return "consider_regeneration"
        elif confidence < 0.5:
            return "low_confidence_prediction"
        else:
            return "standard_quality_expected"
    
    def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from trained model."""
        if not self.is_trained or not hasattr(self.model, 'feature_importances_'):
            return {}
        
        importance_dict = {}
        for i, importance in enumerate(self.model.feature_importances_):
            if i < len(self.feature_names):
                importance_dict[self.feature_names[i]] = float(importance)
        
        return importance_dict

# Global instances
quality_collector = QualityDataCollector()
feature_extractor = FeatureExtractor()
quality_predictor = QualityPredictor()

def predict_generation_quality(jd_text: str,
                             cv_text: str,
                             industry: str,
                             template: str,
                             variant: str,
                             provider: str,
                             skills_match: Dict,
                             experience_scores: List[Dict]) -> Dict[str, Any]:
    """Main function to predict generation quality before actual generation."""
    
    # Extract features (using placeholder content for prediction)
    placeholder_content = "Generated content placeholder for prediction"
    
    features = feature_extractor.extract_features(
        jd_text=jd_text,
        cv_text=cv_text,
        generated_content=placeholder_content,
        industry=industry,
        template=template,
        variant=variant,
        provider=provider,
        generation_time_ms=1000,  # Estimated
        skills_match=skills_match,
        experience_scores=experience_scores
    )
    
    # Predict quality
    prediction = quality_predictor.predict_quality(features)
    
    return {
        "predicted_quality": prediction,
        "features_used": features.to_dict(),
        "model_trained": quality_predictor.is_trained,
        "training_samples": len(quality_collector.training_data)
    }

def collect_quality_feedback(features: QualityFeatures,
                           actual_content: str,
                           quality_scores: Dict[str, float],
                           user_feedback: Optional[float] = None):
    """Collect feedback for model training."""
    quality_collector.collect_generation_data(
        features=features,
        actual_content=actual_content,
        quality_scores=quality_scores,
        user_feedback=user_feedback
    )

def retrain_quality_model():
    """Retrain the quality prediction model with collected data."""
    features_list, targets_list = quality_collector.get_training_dataset()
    
    if len(features_list) >= 10:
        quality_predictor.train(features_list, targets_list)
        return True
    return False
