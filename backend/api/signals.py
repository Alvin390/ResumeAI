from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Profile, AuditLog
try:
    from allauth.socialaccount.signals import social_account_added, social_account_updated
    from allauth.socialaccount.models import SocialAccount
except Exception:  # allauth not installed in some contexts
    social_account_added = None
    social_account_updated = None
    SocialAccount = None

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


def _try_update_profile_from_social(profile: Profile, extra: dict, provider: str):
    # Set full name
    full_name = None
    if provider == 'google':
        # Google OpenID Connect fields
        full_name = extra.get('name') or (
            (extra.get('given_name') or '') + ' ' + (extra.get('family_name') or '')
        ).strip()
        picture_url = extra.get('picture')
    elif provider.startswith('linkedin'):
        first = extra.get('localizedFirstName')
        last = extra.get('localizedLastName')
        full_name = (f"{first or ''} {last or ''}").strip()
        picture_url = None  # LinkedIn basic scopes often omit a direct picture URL
    else:
        picture_url = None

    updated = False
    if full_name and not profile.full_name:
        profile.full_name = full_name
        updated = True

    # Optionally, try to fetch picture if URL available
    if picture_url and not profile.photo_blob:
        try:
            from urllib.request import urlopen
            with urlopen(picture_url, timeout=5) as resp:
                data = resp.read()
                ctype = resp.headers.get('Content-Type', 'image/jpeg')
                profile.photo_blob = data
                profile.photo_content_type = ctype
                profile.photo_filename = 'avatar'
                updated = True
        except Exception:
            pass

    if updated:
        profile.save()


if social_account_added:
    @receiver(social_account_added)
    def on_social_account_added(request, sociallogin, **kwargs):
        user = sociallogin.user
        profile, _ = Profile.objects.get_or_create(user=user)
        extra = sociallogin.account.extra_data or {}
        _try_update_profile_from_social(profile, extra, sociallogin.account.provider)


# Auth auditing
@receiver(user_logged_in)
def on_user_logged_in(sender, user, request, **kwargs):
    try:
        AuditLog.objects.create(
            user=user,
            category="auth",
            action="login_success",
            path=getattr(request, "path", ""),
            method=getattr(request, "method", ""),
            status_code=200,
            extra={"ip": request.META.get("REMOTE_ADDR")},
        )
    except Exception:
        pass


@receiver(user_logged_out)
def on_user_logged_out(sender, user, request, **kwargs):
    try:
        AuditLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            category="auth",
            action="logout",
            path=getattr(request, "path", ""),
            method=getattr(request, "method", ""),
            status_code=200,
            extra={"ip": request.META.get("REMOTE_ADDR")},
        )
    except Exception:
        pass


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    try:
        AuditLog.objects.create(
            user=None,
            category="auth",
            action="login_failed",
            path=getattr(request, "path", ""),
            method=getattr(request, "method", ""),
            status_code=401,
            extra={"username": credentials.get("username") or credentials.get("email")},
        )
    except Exception:
        pass

if social_account_updated:
    @receiver(social_account_updated)
    def on_social_account_updated(request, sociallogin, **kwargs):
        user = sociallogin.user
        profile, _ = Profile.objects.get_or_create(user=user)
        extra = sociallogin.account.extra_data or {}
        _try_update_profile_from_social(profile, extra, sociallogin.account.provider)
