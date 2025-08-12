from typing import Any, Optional
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.request import Request
from rest_framework.response import Response
from django.utils import timezone

from .models import AuditLog


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Optional[Response]:
    response = drf_exception_handler(exc, context)
    try:
        request: Optional[Request] = context.get("request")
        user = getattr(getattr(request, "user", None), "_wrapped", None) if request else None  # type: ignore[attr-defined]
        if request is not None:
            user_obj = getattr(request, "user", None)
        else:
            user_obj = None
        extra = {
            "exception": exc.__class__.__name__,
            "detail": getattr(exc, "detail", None),
            "context_view": context.get("view").__class__.__name__ if context.get("view") else None,
            "timestamp": timezone.now().isoformat(),
        }
        status_code = response.status_code if response is not None else None
        AuditLog.objects.create(
            user=user_obj if getattr(user_obj, "is_authenticated", False) else None,
            category="system",
            action="exception",
            path=getattr(request, "path", ""),
            method=getattr(request, "method", ""),
            status_code=status_code,
            extra=extra,
        )
    except Exception:
        # Avoid raising from logger
        pass
    return response
