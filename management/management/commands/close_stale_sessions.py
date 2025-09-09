from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from management.models import AttendanceSession  # replace with your app if different

class Command(BaseCommand):
    help = "Closes attendance sessions where employee's tab is no longer active"

    def handle(self, *args, **kwargs):
        cutoff = timezone.now() - timedelta(seconds=70)  # or whatever timeout you set in JS + a buffer!
        stale_sessions = AttendanceSession.objects.filter(
            logout_time__isnull=True, last_ping__lt=cutoff
        )
        for session in stale_sessions:
            session.logout_time = cutoff
            session.logout_reason = "Auto-logout: tab/browser closed"
            session.save(update_fields=['logout_time', 'logout_reason'])
            self.stdout.write(self.style.SUCCESS(
                f"Closed stale session {session.pk} for employee {session.employee_id}"
            )) 
