from django.contrib import admin
from .models import (
    Employee,
    Attendance,
    Order,
    Department,
    Invoice,
    Particular
)

# Register all models for admin site access
admin.site.register(Employee)
admin.site.register(Attendance)
admin.site.register(Order)

admin.site.register(Department)
admin.site.register(Invoice)
admin.site.register(Particular)
