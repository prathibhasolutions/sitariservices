from django.db.models import Sum
from django.utils import timezone

from .models import Department, Employee, EmployeeTarget, UserNotificationStatus, Worksheet, SalaryPayment
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


def employee_daily_stats_context(request):
    """
    Provides today's target, total worksheet amount collected, balance,
    and this month's commission due (earned minus paid) for the navbar.
    """
    from decimal import Decimal
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return {
            'navbar_daily_target': None,
            'navbar_daily_collected': None,
            'navbar_daily_balance': None,
            'navbar_daily_commission': None,
        }

    today = timezone.localtime(timezone.now()).date()

    target_obj = EmployeeTarget.objects.filter(employee__employee_id=employee_id, date=today).first()
    target = (target_obj.target_amount + target_obj.carry_forward) if target_obj else None

    collected = Worksheet.objects.filter(
        employee__employee_id=employee_id, date=today
    ).aggregate(total=Sum('amount'))['total'] or 0

    balance = (target - collected) if target is not None else None

    # Commission due = total commission earned this month - total commission paid this month
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        earnings = employee.get_current_month_earnings(today.year, today.month)
        commission_earned = (
            (earnings.get('worksheet_commissions') or Decimal('0')) +
            (earnings.get('application_commissions') or Decimal('0'))
        )
    except Employee.DoesNotExist:
        commission_earned = Decimal('0')

    commission_paid = SalaryPayment.objects.filter(
        employee__employee_id=employee_id,
        payment_type='commission',
        date__year=today.year,
        date__month=today.month,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    commission_due = commission_earned - Decimal(str(commission_paid))

    return {
        'navbar_daily_target': target,
        'navbar_daily_collected': collected,
        'navbar_daily_balance': balance,
        'navbar_daily_commission': commission_due,
    }
