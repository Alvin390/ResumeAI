from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.http import JsonResponse, HttpResponse
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
import io
import base64
from .serializers import ProfileSerializer, DocumentSerializer, JobDescriptionSerializer, GenerationJobSerializer
from .models import Profile, Document, JobDescription, GenerationJob, AuditLog
from .tasks import generate_documents

@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return JsonResponse({"status": "ok"})

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        return Response(ProfileSerializer(profile, context={"request": request}).data)

    def patch(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        try:
            ser = ProfileSerializer(profile, data=request.data, partial=True, context={"request": request})
            ser.is_valid(raise_exception=True)
            ser.save()
            try:
                AuditLog.objects.create(
                    user=request.user,
                    category="profile",
                    action="profile_update",
                    path=request.path,
                    method=request.method,
                    status_code=200,
                    extra={"fields": list(request.data.keys())},
                )
            except Exception:
                pass
            return Response(ser.data)
        except Exception as e:
            try:
                AuditLog.objects.create(
                    user=request.user,
                    category="profile",
                    action="profile_update_error",
                    path=request.path,
                    method=request.method,
                    status_code=400,
                    extra={"error": str(e)},
                )
            except Exception:
                pass
            raise


class AuditLogListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", "50"))
        except ValueError:
            limit = 50
        qs = AuditLog.objects.filter(user=request.user).order_by("-created_at")[: max(1, min(limit, 200))]
        items = [
            {
                "id": al.id,
                "category": al.category,
                "action": al.action,
                "path": al.path,
                "method": al.method,
                "status_code": al.status_code,
                "extra": al.extra,
                "created_at": al.created_at,
            }
            for al in qs
        ]
        return Response({"results": items})


class DocumentListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    def get(self, request):
        dt = (request.query_params.get("doc_type") or "cv").strip().lower()
        if dt == "cover":
            dtype = Document.TYPE_COVER
        else:
            dtype = Document.TYPE_CV
        docs = Document.objects.filter(user=request.user, doc_type=dtype).order_by("-created_at")
        return Response(DocumentSerializer(docs, many=True).data)

    def post(self, request):
        # upload a CV file (PDF or DOCX) as blob; versioning: latest + keep only 3 previous
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            content = upload.read()
            # compute next version
            latest = Document.objects.filter(user=request.user, doc_type=Document.TYPE_CV).order_by("-version").first()
            next_version = (latest.version + 1) if latest else 1
            doc = Document.objects.create(
                user=request.user,
                doc_type=Document.TYPE_CV,
                version=next_version,
                file_name=upload.name,
                content_type=upload.content_type or "application/octet-stream",
                file_blob=content,
            )
            # trim older versions beyond 4 (latest + 3 previous)
            qs = Document.objects.filter(user=request.user, doc_type=Document.TYPE_CV).order_by("-version")
            to_delete = qs[4:]
            if to_delete:
                Document.objects.filter(id__in=[d.id for d in to_delete]).delete()
            try:
                AuditLog.objects.create(
                    user=request.user,
                    category="profile",
                    action="cv_upload",
                    path=request.path,
                    method=request.method,
                    status_code=201,
                    extra={"filename": doc.file_name, "version": doc.version},
                )
            except Exception:
                pass
            return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            try:
                AuditLog.objects.create(
                    user=request.user,
                    category="profile",
                    action="cv_upload_error",
                    path=request.path,
                    method=request.method,
                    status_code=400,
                    extra={"error": str(e)},
                )
            except Exception:
                pass
            raise


class DocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, pk: int):
        try:
            doc = Document.objects.get(id=pk, user=request.user)
        except Document.DoesNotExist:
            try:
                AuditLog.objects.create(
                    user=request.user,
                    category="documents",
                    action="document_download_not_found",
                    path=request.path,
                    method=request.method,
                    status_code=404,
                    extra={"doc_id": pk, "fmt": request.query_params.get("format") or request.query_params.get("fmt")},
                )
            except Exception:
                pass
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        fmt = request.query_params.get("format") or request.query_params.get("fmt")
        try:
            AuditLog.objects.create(
                user=request.user,
                category="documents",
                action="document_download_request",
                path=request.path,
                method=request.method,
                status_code=200,
                extra={"doc_id": doc.id, "fmt": fmt, "content_type": doc.content_type, "file_name": doc.file_name},
            )
        except Exception:
            pass
        # On-the-fly conversion for common text-based documents
        if fmt in ("docx", "pdf"):
            # If the stored document already matches the requested format, just return it.
            ct = (doc.content_type or "").lower()
            fn = (doc.file_name or "").lower()
            if fmt == "pdf" and (ct == "application/pdf" or fn.endswith(".pdf")):
                resp = HttpResponse(bytes(doc.file_blob), content_type="application/pdf")
                safe_name = (doc.file_name or "document").replace("\"", "")
                resp["Content-Disposition"] = f"attachment; filename=\"{safe_name}\""
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        category="documents",
                        action="document_download_serve_original",
                        path=request.path,
                        method=request.method,
                        status_code=200,
                        extra={"doc_id": doc.id, "fmt": fmt, "served": "pdf"},
                    )
                except Exception:
                    pass
                return resp
            if fmt == "docx" and (ct == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or fn.endswith(".docx")):
                resp = HttpResponse(bytes(doc.file_blob), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                safe_name = (doc.file_name or "document").replace("\"", "")
                resp["Content-Disposition"] = f"attachment; filename=\"{safe_name}\""
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        category="documents",
                        action="document_download_serve_original",
                        path=request.path,
                        method=request.method,
                        status_code=200,
                        extra={"doc_id": doc.id, "fmt": fmt, "served": "docx"},
                    )
                except Exception:
                    pass
                return resp
            # Only attempt conversion if we have text-like content
            text = None
            try:
                if (doc.content_type or "").startswith("text/"):
                    text = bytes(doc.file_blob).decode("utf-8", errors="ignore")
            except Exception:
                text = None
            if text is None:
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        category="documents",
                        action="document_download_convert_unsupported",
                        path=request.path,
                        method=request.method,
                        status_code=400,
                        extra={"doc_id": doc.id, "fmt": fmt, "content_type": doc.content_type},
                    )
                except Exception:
                    pass
                return Response({"detail": "Conversion only supported for text/* documents"}, status=status.HTTP_400_BAD_REQUEST)
            base_name = (doc.file_name.rsplit(".", 1)[0] or "document").replace("\"", "")
            if fmt == "docx":
                try:
                    from docx import Document as DocxDocument  # type: ignore
                except Exception:
                    return Response({"detail": "DOCX generation unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                docx_doc = DocxDocument()
                for line in text.splitlines() or [""]:
                    docx_doc.add_paragraph(line)
                buf = io.BytesIO()
                docx_doc.save(buf)
                buf.seek(0)
                resp = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                resp["Content-Disposition"] = f"attachment; filename=\"{base_name}.docx\""
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        category="documents",
                        action="document_download_converted_docx",
                        path=request.path,
                        method=request.method,
                        status_code=200,
                        extra={"doc_id": doc.id},
                    )
                except Exception:
                    pass
                return resp
            if fmt == "pdf":
                try:
                    from fpdf import FPDF  # type: ignore
                except Exception:
                    return Response({"detail": "PDF generation unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                pdf = FPDF()
                pdf.set_auto_page_break(True, margin=15)
                pdf.add_page()
                # Use a core font available by default
                pdf.set_font("Helvetica", size=12)
                try:
                    for raw in text.splitlines() or [""]:
                        # Sanitize to latin-1 to avoid FPDF unicode write errors
                        line = raw.replace("\t", "    ")
                        safe = line.encode("latin1", "ignore").decode("latin1")
                        pdf.multi_cell(0, 8, safe)
                    try:
                        pdf_bytes = pdf.output(dest="S").encode("latin1", errors="ignore")
                    except Exception:
                        # Fallback to file-like
                        buf = io.BytesIO()
                        pdf.output(buf)
                        pdf_bytes = buf.getvalue()
                    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                    resp["Content-Disposition"] = f"attachment; filename=\"{base_name}.pdf\""
                    try:
                        AuditLog.objects.create(
                            user=request.user,
                            category="documents",
                            action="document_download_converted_pdf",
                            path=request.path,
                            method=request.method,
                            status_code=200,
                            extra={"doc_id": doc.id},
                        )
                    except Exception:
                        pass
                    return resp
                except Exception as e:
                    # Log error and attempt a single sanitized dump
                    try:
                        AuditLog.objects.create(
                            user=request.user,
                            category="documents",
                            action="document_download_pdf_error",
                            path=request.path,
                            method=request.method,
                            status_code=500,
                            extra={"doc_id": doc.id, "error": str(e)},
                        )
                    except Exception:
                        pass
                    try:
                        pdf = FPDF()
                        pdf.set_auto_page_break(True, margin=15)
                        pdf.add_page()
                        pdf.set_font("Helvetica", size=12)
                        sanitized = text.encode("latin1", "ignore").decode("latin1")
                        pdf.multi_cell(0, 8, sanitized)
                        buf = io.BytesIO()
                        pdf.output(buf)
                        pdf_bytes = buf.getvalue()
                        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                        resp["Content-Disposition"] = f"attachment; filename=\"{base_name}.pdf\""
                        return resp
                    except Exception as e2:
                        return Response({"detail": f"PDF generation failed: {e2}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Default: return stored blob
        resp = HttpResponse(bytes(doc.file_blob), content_type=doc.content_type)
        resp["Content-Disposition"] = f"attachment; filename=\"{doc.file_name}\""
        try:
            AuditLog.objects.create(
                user=request.user,
                category="documents",
                action="document_download_serve_raw",
                path=request.path,
                method=request.method,
                status_code=200,
                extra={"doc_id": doc.id, "content_type": doc.content_type, "file_name": doc.file_name},
            )
        except Exception:
            pass
        return resp


class DocumentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int):
        try:
            doc = Document.objects.get(id=pk, user=request.user)
        except Document.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        data = DocumentSerializer(doc).data
        text = None
        try:
            if (doc.content_type or "").startswith("text/"):
                text = bytes(doc.file_blob).decode("utf-8", errors="ignore")
        except Exception:
            text = None
        data["text"] = text
        return Response(data)


class DocumentSaveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Create a new version of a text-based document (cover_letter or cv) from provided content.
        Body: { doc_type: "cover_letter"|"cv", content: str, content_type?: str, file_name?: str }
        Keeps latest + 3 previous versions per doc_type.
        """
        doc_type = (request.data.get("doc_type") or "").strip()
        content = request.data.get("content")
        content_type = (request.data.get("content_type") or "text/plain").strip()
        file_name = (request.data.get("file_name") or "").strip() or (
            ("edited_" + doc_type + ".txt") if content_type.startswith("text/") else ("edited_" + doc_type)
        )
        if doc_type not in {Document.TYPE_CV, Document.TYPE_COVER}:
            return Response({"detail": "Invalid doc_type"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(content, str) or not content:
            return Response({"detail": "content is required"}, status=status.HTTP_400_BAD_REQUEST)
        # Compute next version
        latest = Document.objects.filter(user=request.user, doc_type=doc_type).order_by("-version").first()
        next_version = (latest.version + 1) if latest else 1
        new_doc = Document.objects.create(
            user=request.user,
            doc_type=doc_type,
            version=next_version,
            file_name=file_name,
            content_type=content_type,
            file_blob=content.encode("utf-8"),
        )
        # Trim to latest + 3 previous
        qs = Document.objects.filter(user=request.user, doc_type=doc_type).order_by("-version")
        to_delete = qs[4:]
        if to_delete:
            Document.objects.filter(id__in=[d.id for d in to_delete]).delete()
        try:
            AuditLog.objects.create(
                user=request.user,
                category="profile",
                action="document_save_version",
                path=request.path,
                method=request.method,
                status_code=201,
                extra={"doc_type": doc_type, "version": new_doc.version, "file_name": new_doc.file_name},
            )
        except Exception:
            pass
        return Response(DocumentSerializer(new_doc).data, status=status.HTTP_201_CREATED)


class JobDescriptionCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        text = request.data.get("text", "").strip()
        if not text:
            return Response({"detail": "text is required"}, status=status.HTTP_400_BAD_REQUEST)
        jd = JobDescription.objects.create(user=request.user, text=text)
        return Response(JobDescriptionSerializer(jd).data, status=status.HTTP_201_CREATED)


class GenerationStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        job_type = request.data.get("job_type") or GenerationJob.TYPE_BOTH
        template = request.data.get("template") or "classic"
        jd_id = request.data.get("job_description_id")
        cv_id = request.data.get("source_cv_id")

        if not jd_id:
            return Response({"detail": "job_description_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            jd = JobDescription.objects.get(id=jd_id, user=request.user)
        except JobDescription.DoesNotExist:
            return Response({"detail": "Job description not found"}, status=status.HTTP_404_NOT_FOUND)

        source_cv = None
        if cv_id:
            try:
                source_cv = Document.objects.get(id=cv_id, user=request.user)
            except Document.DoesNotExist:
                return Response({"detail": "CV not found"}, status=status.HTTP_404_NOT_FOUND)

        gen = GenerationJob.objects.create(
            user=request.user,
            job_type=job_type,
            job_description=jd,
            template=template,
            source_cv=source_cv,
            status=GenerationJob.STATUS_QUEUED,
        )
        # Enqueue async processing
        try:
            generate_documents.delay(gen.id)
        except Exception as e:
            # If Celery not running, leave queued; frontend can still see queued status
            try:
                AuditLog.objects.create(
                    user=request.user,
                    category="ai",
                    action="enqueue_error",
                    path=request.path,
                    method=request.method,
                    status_code=503,
                    extra={"error": str(e), "job_id": gen.id},
                )
            except Exception:
                pass
        try:
            AuditLog.objects.create(
                user=request.user,
                category="ai",
                action="generation_start",
                path=request.path,
                method=request.method,
                status_code=201,
                extra={"job_id": gen.id, "job_type": job_type, "template": template, "jd_id": jd.id, "cv_id": getattr(source_cv, 'id', None)},
            )
        except Exception:
            pass
        return Response(GenerationJobSerializer(gen).data, status=status.HTTP_201_CREATED)


class GenerationStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int):
        try:
            gen = GenerationJob.objects.get(id=pk, user=request.user)
        except GenerationJob.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            AuditLog.objects.create(
                user=request.user,
                category="ai",
                action="generation_status",
                path=request.path,
                method=request.method,
                status_code=200,
                extra={"job_id": gen.id, "status": gen.status},
            )
        except Exception:
            pass
        return Response(GenerationJobSerializer(gen).data)


class JobDescriptionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", "20"))
        except ValueError:
            limit = 20
        qs = JobDescription.objects.filter(user=request.user).order_by("-created_at")[: max(1, min(limit, 100))]
        return Response(JobDescriptionSerializer(qs, many=True).data)


class GenerationJobListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", "20"))
        except ValueError:
            limit = 20
        qs = GenerationJob.objects.filter(user=request.user).order_by("-created_at")[: max(1, min(limit, 100))]
        return Response(GenerationJobSerializer(qs, many=True).data)


class GenerationDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int):
        try:
            gen = GenerationJob.objects.get(id=pk, user=request.user)
        except GenerationJob.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(GenerationJobSerializer(gen).data)


class ProfilePhotoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if not profile.photo_blob:
            # Return a 1x1 transparent PNG as a safe placeholder instead of 404
            transparent_png_b64 = (
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y0D3a8AAAAASUVORK5CYII="
            )
            png_bytes = base64.b64decode(transparent_png_b64)
            resp = HttpResponse(png_bytes, content_type="image/png")
            resp["Content-Disposition"] = "inline; filename=\"placeholder.png\""
            return resp
        resp = HttpResponse(bytes(profile.photo_blob), content_type=profile.photo_content_type or "application/octet-stream")
        resp["Content-Disposition"] = f"inline; filename=\"{profile.photo_filename or 'photo'}\""
        try:
            AuditLog.objects.create(
                user=request.user,
                category="profile",
                action="photo_get",
                path=request.path,
                method=request.method,
                status_code=200,
            )
        except Exception:
            pass
        return resp

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        upload = request.FILES.get("photo")
        if not upload:
            return Response({"detail": "photo is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            profile.photo_filename = upload.name
            profile.photo_content_type = upload.content_type or "application/octet-stream"
            profile.photo_blob = upload.read()
            profile.save(update_fields=["photo_filename", "photo_content_type", "photo_blob"])
            try:
                AuditLog.objects.create(
                    user=request.user,
                    category="profile",
                    action="photo_upload",
                    path=request.path,
                    method=request.method,
                    status_code=200,
                    extra={"filename": profile.photo_filename, "content_type": profile.photo_content_type},
                )
            except Exception:
                pass
            return Response({"detail": "uploaded"}, status=status.HTTP_200_OK)
        except Exception as e:
            try:
                AuditLog.objects.create(
                    user=request.user,
                    category="profile",
                    action="photo_upload_error",
                    path=request.path,
                    method=request.method,
                    status_code=400,
                    extra={"error": str(e)},
                )
            except Exception:
                pass
            raise
