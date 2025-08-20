from django.conf import settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    - Auto-link social login to existing user with the same email (case-insensitive).
      This avoids the "An account already exists with this email" page when email
      is verified by the provider (Google/LinkedIn typically return verified emails).
    """

    def pre_social_login(self, request, sociallogin):  # type: ignore[override]
        # If the social account is already linked, nothing to do
        if sociallogin.is_existing:
            return

        # If user already logged in, don't auto-connect here
        if request.user and request.user.is_authenticated:
            return

        # Try to get email from the social login data
        email = None
        try:
            email = (sociallogin.user.email or "").strip()
        except Exception:
            email = None
        if not email:
            try:
                email = (sociallogin.account.extra_data or {}).get("email")
            except Exception:
                email = None
        if not email:
            return  # Can't match without an email

        User = get_user_model()
        try:
            existing = User.objects.filter(email__iexact=email).first()
        except Exception:
            existing = None
        if not existing:
            return

        # Link this new social account to the existing user
        try:
            sociallogin.connect(request, existing)
        except Exception:
            # If connect fails for any reason, fall back to default flow
            return


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    After successful login (including social), redirect to the SPA with JWT tokens
    embedded in the URL hash fragment for the frontend to capture.
    """

    def get_login_redirect_url(self, request):  # type: ignore[override]
        try:
            user = getattr(request, "user", None)
            refresh = RefreshToken.for_user(user)
            access = str(refresh.access_token)
            refresh_str = str(refresh)
        except Exception:
            # If token generation fails, send user to frontend login page
            frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
            return f"{frontend}/login"

        frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        # Use URL hash so tokens won't hit server logs as query params
        return f"{frontend}/oauth/callback#access={access}&refresh={refresh_str}"
