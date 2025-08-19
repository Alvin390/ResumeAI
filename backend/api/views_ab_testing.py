"""
A/B Testing Dashboard API Views
Provides endpoints for managing and viewing A/B test results.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import json
import logging

try:
    from .ab_testing import (
        ab_test_manager,
        create_generation_ab_test,
        get_ab_test_results,
        get_ab_test_dashboard_data
    )
    from .semantic_cache import get_semantic_cache_stats
    from .ml_quality_predictor import quality_predictor, retrain_quality_model
    AB_TESTING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"A/B testing components not available: {e}")
    AB_TESTING_AVAILABLE = False

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ab_test_dashboard(request):
    """Get comprehensive A/B testing dashboard data."""
    if not AB_TESTING_AVAILABLE:
        return Response(
            {"error": "A/B testing not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        dashboard_data = get_ab_test_dashboard_data()
        
        # Add ML and caching stats
        dashboard_data["ml_stats"] = {
            "model_trained": quality_predictor.is_trained,
            "training_samples": len(quality_predictor.feature_names) if quality_predictor.is_trained else 0
        }
        
        dashboard_data["cache_stats"] = get_semantic_cache_stats()
        
        return Response(dashboard_data)
        
    except Exception as e:
        logger.error(f"Dashboard data error: {e}")
        return Response(
            {"error": "Failed to load dashboard data"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_ab_test(request):
    """Create a new A/B test."""
    if not AB_TESTING_AVAILABLE:
        return Response(
            {"error": "A/B testing not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['generation_type', 'variants', 'traffic_split']
        for field in required_fields:
            if field not in data:
                return Response(
                    {"error": f"Missing required field: {field}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create the test
        test_config = create_generation_ab_test(
            generation_type=data['generation_type'],
            variants=data['variants'],
            traffic_split=data['traffic_split'],
            duration_days=data.get('duration_days', 14)
        )
        
        return Response({
            "message": "A/B test created successfully",
            "test_config": test_config.to_dict()
        })
        
    except ValueError as e:
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"A/B test creation error: {e}")
        return Response(
            {"error": "Failed to create A/B test"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ab_test_results(request, generation_type):
    """Get results for a specific A/B test."""
    if not AB_TESTING_AVAILABLE:
        return Response(
            {"error": "A/B testing not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        results = get_ab_test_results(generation_type)
        return Response(results)
        
    except Exception as e:
        logger.error(f"A/B test results error: {e}")
        return Response(
            {"error": "Failed to get test results"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_ab_test(request, test_id):
    """Stop an active A/B test."""
    if not AB_TESTING_AVAILABLE:
        return Response(
            {"error": "A/B testing not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        reason = request.data.get('reason', 'Manual stop via API')
        ab_test_manager.stop_test(test_id, reason)
        
        return Response({
            "message": f"A/B test {test_id} stopped successfully",
            "reason": reason
        })
        
    except Exception as e:
        logger.error(f"Stop A/B test error: {e}")
        return Response(
            {"error": "Failed to stop A/B test"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ml_quality_stats(request):
    """Get ML quality prediction statistics."""
    if not AB_TESTING_AVAILABLE:
        return Response(
            {"error": "ML components not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        stats = {
            "model_trained": quality_predictor.is_trained,
            "feature_count": len(quality_predictor.feature_names) if quality_predictor.is_trained else 0,
            "feature_names": quality_predictor.feature_names if quality_predictor.is_trained else [],
            "feature_importance": quality_predictor._get_feature_importance() if quality_predictor.is_trained else {}
        }
        
        return Response(stats)
        
    except Exception as e:
        logger.error(f"ML stats error: {e}")
        return Response(
            {"error": "Failed to get ML statistics"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retrain_ml_model(request):
    """Retrain the ML quality prediction model."""
    if not AB_TESTING_AVAILABLE:
        return Response(
            {"error": "ML components not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        success = retrain_quality_model()
        
        if success:
            return Response({
                "message": "ML model retrained successfully",
                "model_trained": quality_predictor.is_trained,
                "feature_count": len(quality_predictor.feature_names)
            })
        else:
            return Response({
                "message": "Insufficient training data for retraining",
                "model_trained": quality_predictor.is_trained
            })
        
    except Exception as e:
        logger.error(f"ML retrain error: {e}")
        return Response(
            {"error": "Failed to retrain ML model"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def semantic_cache_stats(request):
    """Get semantic cache statistics."""
    if not AB_TESTING_AVAILABLE:
        return Response(
            {"error": "Semantic cache not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        stats = get_semantic_cache_stats()
        return Response(stats)
        
    except Exception as e:
        logger.error(f"Semantic cache stats error: {e}")
        return Response(
            {"error": "Failed to get cache statistics"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_low_quality_cache(request):
    """Clear low-quality entries from semantic cache."""
    if not AB_TESTING_AVAILABLE:
        return Response(
            {"error": "Semantic cache not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        min_quality = request.data.get('min_quality', 0.3)
        
        from .semantic_cache import semantic_cache
        semantic_cache.clear_low_quality(min_quality)
        
        return Response({
            "message": f"Cleared cache entries with quality < {min_quality}",
            "remaining_entries": len(semantic_cache.entries)
        })
        
    except Exception as e:
        logger.error(f"Cache cleanup error: {e}")
        return Response(
            {"error": "Failed to clear cache"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_performance_overview(request):
    """Get comprehensive system performance overview."""
    if not AB_TESTING_AVAILABLE:
        return Response(
            {"error": "Performance monitoring not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        # Gather all system stats
        overview = {
            "ab_testing": get_ab_test_dashboard_data(),
            "ml_quality": {
                "model_trained": quality_predictor.is_trained,
                "feature_count": len(quality_predictor.feature_names) if quality_predictor.is_trained else 0,
                "feature_importance": quality_predictor._get_feature_importance() if quality_predictor.is_trained else {}
            },
            "semantic_cache": get_semantic_cache_stats(),
            "system_health": {
                "components_enabled": {
                    "ab_testing": AB_TESTING_AVAILABLE,
                    "ml_quality": quality_predictor.is_trained,
                    "semantic_cache": True
                }
            }
        }
        
        return Response(overview)
        
    except Exception as e:
        logger.error(f"Performance overview error: {e}")
        return Response(
            {"error": "Failed to get performance overview"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
