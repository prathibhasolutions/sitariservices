# from django.utils import timezone
# from datetime import timedelta
# from .models import AttendanceSession

# def close_stale_sessions():
#     cutoff = timezone.now() - timedelta(seconds=70)
#     stale_sessions = AttendanceSession.objects.filter(
#         logout_time__isnull=True,
#         last_ping__lt=cutoff
#     )
#     for session in stale_sessions:
#         session.logout_time = timezone.now()
#         session.logout_reason = "Auto-logout: Tab closed"
#         session.save(update_fields=['logout_time', 'logout_reason'])
