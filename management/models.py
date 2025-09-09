from django.db import models
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import datetime
import uuid

class Department(models.Model):
    name = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.name

class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=15, unique=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    pf = models.DecimalField("Provident Fund (PF)", max_digits=10, decimal_places=2, null=True, blank=True)
    esi = models.DecimalField("Employee State Insurance (ESI)", max_digits=10, decimal_places=2, null=True, blank=True)
    joining_date = models.DateField()
    department = models.ForeignKey('Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='employees')
    working_start_time = models.TimeField(null=True, blank=True)  # e.g., 09:00
    working_end_time = models.TimeField(null=True, blank=True)    # e.g., 18:00

    def is_active(self):
        return self.attendance_sessions.filter(logout_time__isnull=True).exists()
    
    def __str__(self):
        return f"{self.employee_id} - {self.name}{' 🟢 Active' if self.is_active() else ''}"

class AttendanceSession(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_sessions')
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)
    logout_reason = models.CharField(max_length=250, blank=True)
    session_closed = models.BooleanField(default=False)
    last_ping = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = 'Attendance Sessions'
        ordering = ['-login_time']

    def duration(self):
        end_time = self.logout_time or timezone.now()
        return end_time - self.login_time

    def __str__(self):
        local_login = timezone.localtime(self.login_time)
        logout_str = timezone.localtime(self.logout_time).strftime("%H:%M") if self.logout_time else "Active"
        return f"S{self.uuid.hex[:5]}: {self.employee.name} {local_login.date()} {local_login.strftime('%H:%M')} - {logout_str}"

class BreakSession(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='break_sessions')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    logout_reason = models.CharField(max_length=250)
    approved = models.BooleanField(default=False)
    ended_by_login = models.BooleanField(default=False)

    def duration(self):
        if self.end_time:
            return self.end_time - self.start_time
        else:
            return timezone.now() - self.start_time

    def __str__(self):
        end_str = timezone.localtime(self.end_time).strftime("%d-%m %H:%M") if self.end_time else "Active"
        return f"B{self.uuid.hex[:5]}: {self.employee.name} {self.start_time.strftime('%d-%m %H:%M')} - {end_str} ({'Approved' if self.approved else 'Not Approved'})"

class AllowedIP(models.Model):
    ip_address = models.GenericIPAddressField(
        help_text="Enter full IP address (e.g., 192.168.1.100) or subnet (e.g., 192.168.1.0/24)"
    )
    subnet_prefix = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        help_text="For subnet matching, enter prefix (e.g., '192.168.1.' or '10.0.')"
    )
    description = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Description of this IP/location (e.g., 'Office WiFi', 'John's Home')"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to temporarily disable this IP without deleting"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Allowed IP Address"
        verbose_name_plural = "Allowed IP Addresses"
        ordering = ['-created_at']

    def __str__(self):
        if self.subnet_prefix:
            return f"{self.subnet_prefix}* - {self.description}"
        return f"{self.ip_address} - {self.description}"


class Invoice(models.Model):
    invoice_id = models.AutoField(primary_key=True)
    date = models.DateField(default=timezone.now)
    customer_name = models.CharField(max_length=255)

class Particular(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='particulars', on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)


class WorkOrder(models.Model):
    STAGE_CHOICES = [
        ('start', 'Start'),
        ('stage2', 'Stage 2'),
        ('stage3', 'Stage 3'),
        ('stage4', 'Stage 4'),
        ('complete', 'Complete'),
    ]

    date_created = models.DateTimeField(auto_now_add=True)
    work_name = models.CharField(max_length=255)
    customer_name = models.CharField(max_length=150)
    customer_mobile_number = models.CharField(max_length=15)
    description = models.TextField()
    stage = models.CharField(max_length=10, choices=STAGE_CHOICES, default='start')
    expected_days_to_complete = models.PositiveIntegerField(default=1,help_text="Expected number of days to complete the work")
    commission = models.DecimalField(max_digits=10, decimal_places=2)
    approved = models.BooleanField(default=False)
    assigned_employees = models.ManyToManyField(Employee, related_name='work_orders')

    def assigned_employee_count(self):
        return self.assigned_employees.count() or 1

    def __str__(self):
        return f"WorkOrder#{self.id} ({self.work_name}) for {self.customer_name} - {self.get_stage_display()}"

class Commission(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='commissions')
    month = models.PositiveSmallIntegerField()  # 1 to 12
    year = models.PositiveSmallIntegerField()
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"Commission for {self.employee.name} - {self.month}/{self.year} : ₹{self.total_commission}"

    @staticmethod
    def calculate_for_month(employee, month, year):
        qs = WorkOrder.objects.filter(
            approved=True,
            assigned_employees=employee,
            date_created__year=year,
            date_created__month=month,
        ).annotate(num_assignees=models.Count('assigned_employees'))

        total = 0
        for work_order in qs:
            total += work_order.commission / work_order.num_assignees

        obj, created = Commission.objects.get_or_create(employee=employee, month=month, year=year)
        obj.total_commission = total
        obj.save()
        return obj
