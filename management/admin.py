from django.contrib import admin
from .models import Employee,Attendance,Order,Notification

# Register your models here.
admin.site.register(Employee)
admin.site.register(Attendance)
admin.site.register(Order)
admin.site.register(Notification)