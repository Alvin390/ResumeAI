from rest_framework import serializers
from django.urls import reverse
from .models import Profile, Document, JobDescription, GenerationJob


class ProfileSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "full_name",
            "phone",
            "photo_url",
            "user",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "photo_url", "user"]

    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.photo_blob:
            url = reverse("profile-photo")
            return request.build_absolute_uri(url) if request else url
        return None

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "username": obj.user.username,
            "email": obj.user.email,
            "date_joined": obj.user.date_joined,
        }


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "doc_type",
            "file_name",
            "content_type",
            "version",
            "created_at",
        ]
        read_only_fields = ["id", "version", "created_at"]


class JobDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobDescription
        fields = ["id", "text", "extracted_json", "created_at"]
        read_only_fields = ["id", "extracted_json", "created_at"]


class GenerationJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationJob
        fields = [
            "id",
            "job_type",
            "template",
            "status",
            "job_description",
            "source_cv",
            "result_generated_cv",
            "result_cover_letter",
            "logs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "result_generated_cv",
            "result_cover_letter",
            "logs",
            "created_at",
            "updated_at",
        ]
