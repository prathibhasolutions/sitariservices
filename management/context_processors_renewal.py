from datetime import date
from .models import EmployeeUpload

def renewal_alerts_processor(request):
    """
    Context processor to add renewal date alerts to admin pages
    """
    # Only add context for admin index page
    if hasattr(request, 'path') and request.path == '/admin/':
        today = date.today()
        expired_uploads = EmployeeUpload.objects.filter(
            renewal_date__lte=today,
            renewal_date__isnull=False
        ).select_related('employee', 'service').order_by('renewal_date')
        
        return {
            'expired_uploads': expired_uploads,
            'expired_count': expired_uploads.count(),
            'show_renewal_alert': expired_uploads.exists(),
            'today': today,
        }
    return {}