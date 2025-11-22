from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse
from management.models import AttendanceSession, Employee
from django.utils import timezone

class EmployeeAttendanceSessionMiddleware(MiddlewareMixin):
    """
    Middleware to ensure employee has an active AttendanceSession for all employee-only pages.
    If not, logs out the user and redirects to login.
    """
    def process_request(self, request):
        path = request.path
        # List of URL prefixes for employee-only pages
        employee_prefixes = [
            '/employee/dashboard/', '/employee/attendance/', '/employee/attendance_ping/', '/employee/refresh_session/',
            '/worksheet/', '/notifications/', '/change-password/', '/upload-file/', '/todos/', '/applications/', '/links/',
            '/assigned-tasks/', '/create-invoice/', '/invoice/'
        ]
        # Exclude admin, api, and logout URLs
        if (
            not path.startswith('/admin/') and
            not path.startswith('/api/') and
            not path.startswith('/logout/') and
            (
                path == '/' or
                any(path.startswith(prefix) for prefix in employee_prefixes)
            )
        ):
            employee_id = request.session.get('employee_id')
            if employee_id:
                has_active = AttendanceSession.objects.filter(
                    employee_id=employee_id,
                    logout_time__isnull=True,
                    session_closed=False
                ).exists()
                if not has_active:
                    request.session.flush()
                    return redirect(reverse('login'))
        return None
from django.utils.deprecation import MiddlewareMixin

class AuditlogIPMiddleware(MiddlewareMixin):
    """
    Middleware to attach the user's IP address to the request for audit logging.
    """
    def process_request(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip:
            ip = ip.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        request.auditlog_ip = ip
from django.shortcuts import redirect
from django.urls import reverse
from management.models import AttendanceSession, Employee
from django.utils import timezone

class SingleDeviceSessionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        employee_id = request.session.get('employee_id')
        if not employee_id:
            return None
        # Exclude login/logout/refresh endpoints to avoid recursion
        path = request.path
        if any(path.startswith(p) for p in [reverse('login'), reverse('logout'), '/employee/refresh_session/']):
            return None
        try:
            employee = Employee.objects.get(employee_id=employee_id)
        except Employee.DoesNotExist:
            return None
        # Only one active session allowed
        open_sessions = AttendanceSession.objects.filter(employee=employee, logout_time__isnull=True, session_closed=False).order_by('-login_time')
        if open_sessions.count() > 1:
            now = timezone.now()
            latest_session = open_sessions[0]
            closed_any = False
            for s in open_sessions[1:]:
                s.logout_time = now
                s.logout_reason = "Auto-logout: Multiple sessions detected"
                s.session_closed = True
                s.session_status = "ended"
                s.save(update_fields=["logout_time", "logout_reason", "session_closed", "session_status"])
                if request.session.get('attendance_session_id') == s.id:
                    request.session.flush()
                    closed_any = True
            # If this request was for a closed session, redirect to login
            if closed_any:
                return redirect(reverse('login'))
            # Otherwise, set the session id to the latest
            request.session['attendance_session_id'] = latest_session.id
        elif open_sessions.count() == 1:
            request.session['attendance_session_id'] = open_sessions[0].id
        return None
