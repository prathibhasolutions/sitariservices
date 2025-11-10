

from auditlog.signals import post_log
from auditlog.models import LogEntry

# Try to get the request from thread-local storage set by AuditlogMiddleware
def get_request_from_auditlog_middleware():
    try:
        from auditlog.middleware import _thread_locals
        return getattr(_thread_locals, 'request', None)
    except Exception:
        return None


def set_ip_address(sender, instance, action, changes, log_entry, **kwargs):
    # Only log if the user is staff or superuser
    request = getattr(instance, '_auditlog_request', None)
    if not request:
        request = get_request_from_auditlog_middleware()
    # If no request or no user, skip logging
    user = getattr(request, 'user', None)
    if not user or not (user.is_authenticated and (user.is_staff or user.is_superuser)):
        # Delete the log entry if it was created for a non-staff/non-superuser
        if log_entry:
            log_entry.delete()
        return
    if hasattr(request, 'auditlog_ip') and log_entry:
        log_entry.remote_addr = request.auditlog_ip
        log_entry.save(update_fields=['remote_addr'])

post_log.connect(set_ip_address)
