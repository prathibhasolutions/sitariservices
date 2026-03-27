from django.utils import timezone

from .models import Department, Employee, UserNotificationStatus
from .utils import format_hour_label, get_employee_next_day_alert_state

def notifications_context(request):
    """
    Makes the unread notification count and department-head flag available to all templates.
    """
    if request.session.get('employee_id'):
        employee_id = request.session.get('employee_id')
        count = UserNotificationStatus.objects.filter(employee_id=employee_id, is_read=False).count()
        is_department_head = Department.objects.filter(department_head__employee_id=employee_id).exists()
        return {
            'unread_notification_count': count,
            'is_department_head': is_department_head,
        }
    return {'unread_notification_count': 0, 'is_department_head': False}


def employee_next_day_alert_context(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return {
            'employee_next_day_alert_pending': False,
            'employee_next_day_alert_response': None,
        }

    state = getattr(request, 'employee_next_day_alert_state', None)
    if state is None:
        employee = Employee.objects.filter(employee_id=employee_id).first()
        state = get_employee_next_day_alert_state(employee) if employee else None

    if not state:
        return {
            'employee_next_day_alert_pending': False,
            'employee_next_day_alert_response': None,
        }

    now_local = timezone.localtime(timezone.now())
    end_at = now_local.replace(hour=state['end_hour'], minute=0, second=0, microsecond=0)
    ms_until_auto_no = max(int((end_at - now_local).total_seconds() * 1000), 0)

    return {
        'employee_next_day_alert_pending': state['pending'],
        'employee_next_day_alert_response': state['response'],
        'employee_next_day_alert_target_date': state['target_date'],
        'employee_next_day_alert_start_label': format_hour_label(state['start_hour']),
        'employee_next_day_alert_end_label': format_hour_label(state['end_hour']),
        'employee_next_day_alert_start_hour': state['start_hour'],
        'employee_next_day_alert_end_hour': state['end_hour'],
        'employee_next_day_alert_ms_until_auto_no': ms_until_auto_no,
        'employee_next_day_alert_auto_marked': state['auto_marked'],
    }
