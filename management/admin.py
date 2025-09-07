from django.contrib import admin
from .models import (
    Employee,
    AttendanceSession,
    WorkOrder,
    Commission,
    Department,
    Invoice,
    Particular,
    BreakSession
)

# Register all models for admin site access
admin.site.register(Employee)
admin.site.register(AttendanceSession)
admin.site.register(WorkOrder)
admin.site.register(Commission)

admin.site.register(Department)
admin.site.register(Invoice)
admin.site.register(Particular)
admin.site.register(BreakSession)
