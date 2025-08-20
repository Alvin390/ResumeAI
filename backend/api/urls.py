from django.urls import path
from .views import (
    health, ProfileView, UserUpdateView, 
    DocumentListCreateView, DocumentDownloadView,
    DocumentDetailView,
    DocumentSaveView,
    ProfilePhotoView,
    JobDescriptionCreateView,
    GenerationStartView,
    GenerationStatusView,
    JobDescriptionListView,
    GenerationJobListView,
    GenerationDetailView,
    AuditLogListView,
)

# A/B Testing and ML endpoints
try:
    from .views_ab_testing import (
        ab_test_dashboard, create_ab_test, ab_test_results, stop_ab_test,
        ml_quality_stats, retrain_ml_model, semantic_cache_stats, 
        clear_low_quality_cache, system_performance_overview
    )
    AB_TESTING_URLS_AVAILABLE = True
except ImportError:
    AB_TESTING_URLS_AVAILABLE = False

urlpatterns = [
    path("health/", health, name="health"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/photo/", ProfilePhotoView.as_view(), name="profile-photo"),
    path("auth/user/", UserUpdateView.as_view(), name="user-update"),
    path("cv/", DocumentListCreateView.as_view(), name="cv-list-create"),
    path("cv/<int:pk>/download/", DocumentDownloadView.as_view(), name="cv-download"),
    # General document routes
    path("documents/<int:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path("documents/save/", DocumentSaveView.as_view(), name="document-save"),
    path("documents/<int:pk>/download/", DocumentDownloadView.as_view(), name="document-download"),
    path("jobs/", JobDescriptionCreateView.as_view(), name="jobs-create"),
    path("generate/", GenerationStartView.as_view(), name="generation-start"),
    path("generations/<int:pk>/status/", GenerationStatusView.as_view(), name="generation-status"),
    path("jobs/list/", JobDescriptionListView.as_view(), name="jobs-list"),
    path("generations/", GenerationJobListView.as_view(), name="generations-list"),
    path("generations/<int:pk>/", GenerationDetailView.as_view(), name="generation-detail"),
    path("audit-logs/", AuditLogListView.as_view(), name="audit-log-list"),
]

# Add A/B Testing and ML endpoints if available
if AB_TESTING_URLS_AVAILABLE:
    urlpatterns += [
        # A/B Testing Dashboard
        path("ab-testing/dashboard/", ab_test_dashboard, name="ab-test-dashboard"),
        path("ab-testing/create/", create_ab_test, name="ab-test-create"),
        path("ab-testing/results/<str:generation_type>/", ab_test_results, name="ab-test-results"),
        path("ab-testing/stop/<str:test_id>/", stop_ab_test, name="ab-test-stop"),
        
        # ML Quality Prediction
        path("ml/quality-stats/", ml_quality_stats, name="ml-quality-stats"),
        path("ml/retrain/", retrain_ml_model, name="ml-retrain"),
        
        # Semantic Caching
        path("cache/stats/", semantic_cache_stats, name="semantic-cache-stats"),
        path("cache/clear-low-quality/", clear_low_quality_cache, name="cache-clear-low-quality"),
        
        # System Performance
        path("system/performance/", system_performance_overview, name="system-performance"),
    ]
