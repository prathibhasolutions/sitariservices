from django.utils import timezone
from datetime import timedelta
from .models import AttendanceSession
from django.db.models import Q

def close_stale_sessions():
    """
    Closes any attendance session that is considered stale.
    A session is stale if it is still active (no logout_time) and meets one of the following criteria:
    1. It has received a ping, but the last_ping was more than 15 minutes ago.
    2. It has never received a ping, and the login_time was more than 15 minutes ago.
    """
    cutoff = timezone.now() - timedelta(minutes=15)

    # Build the query to find all stale sessions
    # This uses an OR condition to check both scenarios
    stale_sessions = AttendanceSession.objects.filter(
        logout_time__isnull=True
    ).filter(
        # Condition 1: Stale ping
        Q(last_ping__lt=cutoff) |
        
        # Condition 2: No ping ever, check against login time
        Q(last_ping__isnull=True, login_time__lt=cutoff)
    )

    count = stale_sessions.count()
    if count > 0:
        print(f"Found {count} stale sessions to close.")

    for session in stale_sessions:
        session.logout_time = timezone.now()
        
        # Set a clear reason based on why it was closed
        if session.last_ping is None:
            session.logout_reason = "Auto-logout: Tab closed"
        else:
            session.logout_reason = "Auto-logout: Tab closed"
            
        session.save(update_fields=['logout_time', 'logout_reason'])

