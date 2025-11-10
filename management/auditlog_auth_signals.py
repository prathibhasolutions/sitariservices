
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(user_logged_in)
def log_admin_login(sender, request, user, **kwargs):
    # Only log if user is staff or superuser
    if not (user.is_staff or user.is_superuser):
        return
    LogEntry.objects.create(
        actor=user,
        action=4,  # Custom action code for login event
        content_type=ContentType.objects.get_for_model(User),
        object_id=user.pk,
        object_repr=f'Admin login: {user.username}',
        remote_addr=getattr(request, 'auditlog_ip', None),
        changes={'message': f'Admin user {user.username} logged in.'},
        timestamp=timezone.now(),
    )


@receiver(user_logged_out)
def log_admin_logout(sender, request, user, **kwargs):
    # Only log if user is staff or superuser
    if not (user.is_staff or user.is_superuser):
        return
    LogEntry.objects.create(
        actor=user,
        action=4,  # Custom action code for logout event
        content_type=ContentType.objects.get_for_model(User),
        object_id=user.pk,
        object_repr=f'Admin logout: {user.username}',
        remote_addr=getattr(request, 'auditlog_ip', None),
        changes={'message': f'Admin user {user.username} logged out.'},
        timestamp=timezone.now(),
    )
