from .models import UserNotificationStatus

def notifications_context(request):
    """
    Makes the unread notification count available to all templates.
    """
    if request.session.get('employee_id'):
        employee_id = request.session.get('employee_id')
        count = UserNotificationStatus.objects.filter(employee_id=employee_id, is_read=False).count()
        return {'unread_notification_count': count}
    return {'unread_notification_count': 0}
