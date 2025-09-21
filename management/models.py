from django.db import models
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import datetime
import uuid
from django.conf import settings
import os
from django.db.models import Sum, F, ExpressionWrapper, fields
import calendar

class Department(models.Model):
    name = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.name


from datetime import datetime, timedelta
from calendar import monthrange

class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=15, unique=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    pf = models.DecimalField("Provident Fund (PF)", max_digits=10, decimal_places=2, null=True, blank=True)
    esi = models.DecimalField("Employee State Insurance (ESI)", max_digits=10, decimal_places=2, null=True, blank=True)
    joining_date = models.DateField()
    department = models.ForeignKey('Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='employees')
    working_start_time = models.TimeField(null=True, blank=True)
    working_end_time = models.TimeField(null=True, blank=True)
    password = models.CharField(max_length=128, default="123")

    def is_active(self):
        # Assuming you have an AttendanceSession model with a 'logout_time'
        return self.attendance_sessions.filter(logout_time__isnull=True).exists()

    def __str__(self):
        return f"{self.employee_id} - {self.name}{' 🟢 Active' if self.is_active() else ''}"

    def net_salary(self):
        if self.salary is None:
            return 0
        pf_deduction = self.pf or 0
        esi_deduction = self.esi or 0
        return self.salary - pf_deduction - esi_deduction

    def get_current_month_earnings(self):
        """
        Calculates all earnings for the current month.
        This version is corrected to properly sum direct commission amounts.
        """
        from .models import ApplicationAssignment, Worksheet, MonthlyDeduction # Local import to avoid circular dependency

        now = timezone.now()
        current_month = now.month
        current_year = now.year

        earnings = {
            'attendance_salary': Decimal('0.00'),
            'application_commissions': Decimal('0.00'),
            'worksheet_commissions': Decimal('0.00'),
            'monthly_deductions_list': [],
            'deduction_amount': Decimal('0.00'),
            'total_earnings': Decimal('0.00'),
        }

       # --- 1. ATTENDANCE SALARY CALCULATION (Unchanged) ---
        if self.working_start_time and self.working_end_time:
            start_dt = datetime.combine(datetime.today(), self.working_start_time)
            end_dt = datetime.combine(datetime.today(), self.working_end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            daily_working_seconds = (end_dt - start_dt).total_seconds()
        else:
            daily_working_seconds = 8 * 3600 # 8 hours default

        days_in_month = monthrange(current_year, current_month)[1]
        expected_seconds = days_in_month * daily_working_seconds
        
        attendance_sessions_qs = self.attendance_sessions.filter(
            login_time__year=current_year,
            login_time__month=current_month
        )
        
        attended_seconds = sum([s.duration().total_seconds() for s in attendance_sessions_qs if s.duration()])

        break_sessions_qs = self.break_sessions.filter(
            start_time__year=current_year,
            start_time__month=current_month,
            approved=True,
            end_time__isnull=False
        )
        approved_break_seconds = sum([(bs.end_time - bs.start_time).total_seconds() for bs in break_sessions_qs])
        
        total_work_seconds = attended_seconds + approved_break_seconds

        if expected_seconds > 0:
            salary_ratio = Decimal(total_work_seconds) / Decimal(expected_seconds)
            earnings['attendance_salary'] = self.salary * salary_ratio

        # --- 2. APPLICATION COMMISSIONS (Corrected Logic) ---
        application_commissions = self.applicationassignment_set.filter(
            application__approved=True,
            application__date_created__year=current_year,
            application__date_created__month=current_month
        ).aggregate(total=Sum('commission_amount'))['total'] or Decimal('0.00')
        earnings['application_commissions'] = application_commissions

        # --- 3. WORKSHEET COMMISSIONS (Assuming 5% commission) ---
        worksheet_commission = Decimal('0.00')
        if hasattr(self, 'worksheet_set'): # Default related_name is 'modelname_set'
            worksheet_sum = self.worksheet_set.filter(
                date__year=current_year,
                date__month=current_month,
                approved=True
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            worksheet_commission = worksheet_sum * Decimal('0.05')
        earnings['worksheet_commissions'] = worksheet_commission

        # --- 4. DEDUCTIONS ---
        deductions_qs = self.monthly_deductions.filter(month=current_month, year=current_year)
        total_deduction_amount = deductions_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        earnings['monthly_deductions_list'] = deductions_qs
        earnings['deduction_amount'] = total_deduction_amount

        # --- 5. FINAL TOTAL ---
        total_before_deduction = (
            earnings['attendance_salary'] + 
            earnings['application_commissions'] + 
            earnings['worksheet_commissions']
        )
        earnings['total_earnings'] = total_before_deduction - earnings['deduction_amount']

        return earnings






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


class GlobalIPSettings(models.Model):
    allow_all_ips = models.BooleanField(
        default=False,
        help_text="If checked, the IP restriction middleware will be disabled and all IPs will be allowed."
    )

    def __str__(self):
        return "Global IP Restriction Settings"

    def save(self, *args, **kwargs):
        # Ensure only one instance of this model ever exists
        self.pk = 1
        super().save(*args, **kwargs)
        # Clear the IP cache whenever this setting is saved
        from django.core.cache import cache
        cache.clear()

    class Meta:
        verbose_name_plural = "Global IP Settings"

        

class Invoice(models.Model):
    invoice_id = models.AutoField(primary_key=True)
    date = models.DateField(default=timezone.now)
    customer_name = models.CharField(max_length=255)

class Particular(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='particulars', on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)


# management/models.py
from django.db import models
from django.utils import timezone
from decimal import Decimal

# Ensure your Employee model is defined or imported above this point

class Application(models.Model):
    """
    This is the central model for a client's job.
    """
    id = models.AutoField(primary_key=True)
    date_created = models.DateTimeField(auto_now_add=True)
    application_name = models.CharField(max_length=255)
    customer_name = models.CharField(max_length=150)
    customer_mobile_number = models.CharField(max_length=15)
    description = models.TextField()
    
    # --- UPDATED FIELD ---
    expected_date_of_completion = models.DateField(
        null=True, blank=True, help_text="Expected date to complete the work"
    )
    
    total_commission = models.DecimalField(max_digits=10, decimal_places=2)
    approved = models.BooleanField(default=False)
    assigned_employees = models.ManyToManyField(Employee, through='ApplicationAssignment', related_name='applications')

    def __str__(self):
        return f"Application#{self.id} ({self.application_name}) for {self.customer_name}"


class ApplicationAssignment(models.Model):
    """
    Manages the relationship between an Application and an Employee,
    storing the specific commission amount for that assignment.
    """
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    
    # --- UPDATED FIELD ---
    commission_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text="The exact commission amount for this employee"
    )

    class Meta:
        unique_together = ('application', 'employee')

    def __str__(self):
        return f"{self.employee.name} has commission of ₹{self.commission_amount} for {self.application.application_name}"

# In management/models.py

class ApplicationDateExtension(models.Model):
    """
    Stores a record of each time an application's completion date is extended.
    """
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='date_extensions')
    previous_date = models.DateField(null=True, blank=True)
    new_date = models.DateField()
    extended_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Extension for App #{self.application.id}: from {self.previous_date} to {self.new_date}"


class ChatMessage(models.Model):
    # ... (This model remains unchanged)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='chat_messages')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    message = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message by {self.employee.name} on {self.application.application_name} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class Commission(models.Model):
    # ... (This model remains unchanged)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='commissions')
    month = models.PositiveSmallIntegerField()  # 1 to 12
    year = models.PositiveSmallIntegerField()
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"Commission for {self.employee.name} - {self.month}/{self.year} : ₹{self.total_commission}"



class Worksheet(models.Model):
    # Common fields
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='worksheet_entries')
    date = models.DateField(default=timezone.now)
    payment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    department_name = models.CharField(max_length=50, editable=False)
    
    # NEW: Approval status field
    approved = models.BooleanField(default=False)

    # Department-Specific Fields (all optional)
    token_no = models.CharField(max_length=100, blank=True, null=True)
    customer_name = models.CharField(max_length=150, blank=True, null=True)
    customer_mobile = models.CharField(max_length=15, blank=True, null=True)

    service = models.CharField(max_length=200, blank=True, null=True)
    certificate_number = models.CharField(max_length=100, blank=True, null=True)
    transaction_num = models.CharField("Transaction Number", max_length=100, blank=True, null=True)
    enrollment_no = models.CharField("Enrollment Number", max_length=100, blank=True, null=True)
    login_mobile_no = models.CharField("Login Mobile No.", max_length=15, blank=True, null=True)
    application_no = models.CharField("Application No.", max_length=100, blank=True, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)
    particulars = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        approval_status = "Approved" if self.approved else "Pending"
        return f"Entry by {self.employee.name} on {self.date} for {self.department_name} ({approval_status})"


class Notification(models.Model):
    """
    Represents the core notification message.
    """
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    # The relationship is managed through the UserNotificationStatus model
    recipients = models.ManyToManyField(Employee, through='UserNotificationStatus', related_name='notifications')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.description[:50]

class UserNotificationStatus(models.Model):
    """
    Acts as a "through" model, linking each Employee to a Notification
    and tracking their individual read status.
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)

    class Meta:
        # Ensures an employee can't have multiple statuses for the same notification
        unique_together = ('employee', 'notification')

    def __str__(self):
        status = 'Read' if self.is_read else 'Unread'
        return f"{self.employee.name} - '{self.notification.description[:20]}...' ({status})"
    


# models.py

class MonthlyDeduction(models.Model):
    """
    NEW: Stores monthly miscellaneous deductions for an employee.
    This allows admins to make adjustments on a per-month basis.
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='monthly_deductions')
    month = models.PositiveSmallIntegerField() # 1 to 12
    year = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.CharField(max_length=255, blank=True, help_text="Reason for the deduction (e.g., 'Late fees', 'Advance adjustment')")

    class Meta:
        ordering = ['-year', '-month']

    def __str__(self):
        return f"Deduction for {self.employee.name} - {self.month}/{self.year}: ₹{self.amount}"





# management/models.py

class UploadService(models.Model):
    """A list of services that can be associated with a file upload."""
    name = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    

# management/models.py

class EmployeeUpload(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='file_uploads')
    # --- NEW FIELD ---
    service = models.ForeignKey(
        UploadService, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=False # This makes the field required in the form
    )
    description = models.TextField(help_text="A brief description of the uploaded file.")
    file = models.FileField(upload_to='employee_uploads/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        # Updated string representation
        service_name = self.service.name if self.service else "Uncategorized"
        return f"File from {self.employee.name} for {service_name}"

