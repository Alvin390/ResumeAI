from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    photo_filename = models.CharField(max_length=255, blank=True, default="")
    photo_content_type = models.CharField(max_length=150, blank=True, default="")
    photo_blob = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile({self.user_id})"


class Document(models.Model):
    TYPE_CV = "cv"
    TYPE_COVER = "cover_letter"
    TYPE_CHOICES = (
        (TYPE_CV, "CV"),
        (TYPE_COVER, "Cover Letter"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    version = models.PositiveIntegerField(default=1)
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=150)
    file_blob = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "doc_type", "version"], name="uniq_user_doctype_version"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Document({self.user_id}, {self.doc_type}, v{self.version})"


class JobDescription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_descriptions")
    text = models.TextField()
    extracted_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"JobDescription({self.user_id}, len={len(self.text)})"


class GenerationJob(models.Model):
    TYPE_BOTH = "both"
    TYPE_COVER = "cover_letter"
    TYPE_CV = "generated_cv"
    JOB_TYPES = [
        (TYPE_BOTH, "Both"),
        (TYPE_COVER, "Cover Letter"),
        (TYPE_CV, "Generated CV"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"
    STATUSES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_DONE, "Done"),
        (STATUS_ERROR, "Error"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="generation_jobs")
    job_type = models.CharField(max_length=20, choices=JOB_TYPES, default=TYPE_BOTH)
    job_description = models.ForeignKey(JobDescription, on_delete=models.CASCADE, related_name="generation_jobs")
    template = models.CharField(max_length=64, blank=True, default="classic")
    source_cv = models.ForeignKey('Document', null=True, blank=True, on_delete=models.SET_NULL, related_name="source_for_jobs")

    status = models.CharField(max_length=12, choices=STATUSES, default=STATUS_QUEUED)
    logs = models.TextField(blank=True, default="")

    result_generated_cv = models.ForeignKey('Document', null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_cv_jobs")
    result_cover_letter = models.ForeignKey('Document', null=True, blank=True, on_delete=models.SET_NULL, related_name="cover_letter_jobs")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GenerationJob({self.user_id}, {self.job_type}, {self.status})"


class AuditLog(models.Model):
    CATEGORY_CHOICES = (
        ("auth", "Authentication"),
        ("profile", "Profile"),
        ("ai", "AI"),
        ("system", "System"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    action = models.CharField(max_length=100)
    path = models.CharField(max_length=500, blank=True, default="")
    method = models.CharField(max_length=10, blank=True, default="")
    status_code = models.IntegerField(null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["category", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"AuditLog({self.category}:{self.action}, user={self.user_id})"
