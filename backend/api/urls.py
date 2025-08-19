from django.urls import path
from .views import (
    health,
    ProfileView,
    UserUpdateView,
    DocumentListCreateView,
    DocumentDownloadView,
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
