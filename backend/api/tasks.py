from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import Max

from .models import GenerationJob, Document, JobDescription, AuditLog
from . import ai
from . import parsing


@shared_task(bind=True)
def generate_documents(self, generation_job_id: int):
    """
    Step 3b: Skeleton generation task.
    - Marks job running
    - Creates mock cover letter and generated CV documents
    - Marks job done (or error on failure)
    """
    try:
        with transaction.atomic():
            job = GenerationJob.objects.select_for_update().get(id=generation_job_id)
            job.status = GenerationJob.STATUS_RUNNING
            job.logs = (job.logs or '') + f"[{timezone.now()}] Job started\n"
            job.save(update_fields=["status", "logs", "updated_at"])

            user = job.user

            # Determine next versions per type to satisfy unique (user, doc_type, version)
            next_versions = {}
            for t in (Document.TYPE_COVER, Document.TYPE_CV):
                maxv = (
                    Document.objects.filter(user=user, doc_type=t)
                    .aggregate(m=Max("version"))
                    .get("m")
                ) or 0
                next_versions[t] = maxv + 1

            # Prepare inputs
            jd_text = JobDescription.objects.get(id=job.job_description_id).text
            cv_text = None
            if job.source_cv:
                cv_text = parsing.extract_text_from_document(job.source_cv)
                job.logs += f"[{timezone.now()}] Extracted source CV text length={len(cv_text or '')}\n"

            # Create cover letter (AI stub or provider)
            if job.job_type in (GenerationJob.TYPE_BOTH, GenerationJob.TYPE_COVER):
                import time as _t
                t0 = _t.perf_counter()
                provider, cover_text, attempts = ai.generate_cover_letter(jd_text=jd_text, cv_text=cv_text)
                dt_ms = int((_t.perf_counter() - t0) * 1000)
                cover = Document.objects.create(
                    user=user,
                    doc_type=Document.TYPE_COVER,
                    file_name=f"cover_letter_{job.id}.txt",
                    content_type="text/plain",
                    file_blob=cover_text.encode(),
                    version=next_versions[Document.TYPE_COVER],
                )
                job.result_cover_letter = cover
                job.logs += f"[{timezone.now()}] Cover letter generated via {provider} in {dt_ms}ms\n"
                for att in attempts or []:
                    job.logs += (
                        f"[{timezone.now()}] Cover attempt provider={att.get('provider')} status={att.get('status')} "
                        f"duration={att.get('duration_ms')}ms error={att.get('error','')}\n"
                    )
                try:
                    AuditLog.objects.create(
                        user=user,
                        category="ai",
                        action="cover_generate",
                        path=f"/api/generations/{job.id}/",
                        method="CELERY",
                        status_code=200,
                        extra={"provider": provider, "duration_ms": dt_ms, "job_id": job.id, "attempts": attempts},
                    )
                except Exception:
                    pass

            # Create generated CV (AI stub or provider)
            if job.job_type in (GenerationJob.TYPE_BOTH, GenerationJob.TYPE_CV):
                import time as _t
                t1 = _t.perf_counter()
                provider2, gcv_text, attempts2 = ai.generate_cv(jd_text=jd_text, cv_text=cv_text, template=job.template)
                dt2_ms = int((_t.perf_counter() - t1) * 1000)
                gcv = Document.objects.create(
                    user=user,
                    doc_type=Document.TYPE_CV,
                    file_name=f"generated_cv_{job.id}.txt",
                    content_type="text/plain",
                    file_blob=gcv_text.encode(),
                    version=next_versions[Document.TYPE_CV],
                )
                job.result_generated_cv = gcv
                job.logs += f"[{timezone.now()}] Generated CV via {provider2} in {dt2_ms}ms\n"
                for att in attempts2 or []:
                    job.logs += (
                        f"[{timezone.now()}] CV attempt provider={att.get('provider')} status={att.get('status')} "
                        f"duration={att.get('duration_ms')}ms error={att.get('error','')}\n"
                    )
                try:
                    AuditLog.objects.create(
                        user=user,
                        category="ai",
                        action="cv_generate",
                        path=f"/api/generations/{job.id}/",
                        method="CELERY",
                        status_code=200,
                        extra={"provider": provider2, "duration_ms": dt2_ms, "job_id": job.id, "template": job.template, "attempts": attempts2},
                    )
                except Exception:
                    pass

            job.status = GenerationJob.STATUS_DONE
            job.logs += f"[{timezone.now()}] Job finished\n"
            job.save(update_fields=[
                "status",
                "logs",
                "updated_at",
                "result_generated_cv",
                "result_cover_letter",
            ])
    except GenerationJob.DoesNotExist:
        return
    except Exception as e:
        try:
            job = GenerationJob.objects.get(id=generation_job_id)
            job.status = GenerationJob.STATUS_ERROR
            job.logs = (job.logs or '') + f"[{timezone.now()}] Error: {e}\n"
            job.save(update_fields=["status", "logs", "updated_at"])
            try:
                AuditLog.objects.create(
                    user=job.user,
                    category="ai",
                    action="generation_error",
                    path=f"/api/generations/{job.id}/",
                    method="CELERY",
                    status_code=500,
                    extra={"error": str(e)},
                )
            except Exception:
                pass
        except Exception:
            pass
        raise
