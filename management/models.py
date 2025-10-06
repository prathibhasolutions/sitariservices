from django.db import models
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import datetime,time
import uuid
from django.conf import settings
import os
from django.db.models import Sum, F, ExpressionWrapper, fields
import calendar
from calendar import monthrange
from collections import defaultdict

class Department(models.Model):
    name = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.name


class ManagedLink(models.Model):
    """
    Stores a link with a description, managed by an admin.
    (This model remains the same)
    """
    description = models.CharField(
        max_length=200, 
        help_text="A short, descriptive name for the link (e.g., 'Company Policy Document')."
    )
    url = models.URLField(
        max_length=500, 
        help_text="The full URL of the link (e.g., 'https://example.com/policy.pdf')."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.description

    class Meta:
        ordering = ['description'] # Ordering by description is more user-friendly
        verbose_name = "Managed Link"
        verbose_name_plural = "Managed Links"

from datetime import datetime, timedelta
from calendar import monthrange

class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', 
        default='default_profile.jpg', 
        blank=True, null=True
    )
    mobile_number = models.CharField(max_length=15, unique=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    pf = models.DecimalField("Provident Fund (PF)", max_digits=10, decimal_places=2, null=True, blank=True)
    esi = models.DecimalField("Employee State Insurance (ESI)", max_digits=10, decimal_places=2, null=True, blank=True)
    joining_date = models.DateField()
    department = models.ForeignKey('Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='employees')
    working_start_time = models.TimeField(null=True, blank=True)
    working_end_time = models.TimeField(null=True, blank=True)
    password = models.CharField(max_length=128, default="123")
    assigned_links = models.ManyToManyField(
        ManagedLink, 
        blank=True, 
        related_name="assigned_employees"
    )
    advances = models.DecimalField(
        "Current Advance",
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Total outstanding advance amount taken by the employee."
    )

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
    
    # In models.py, inside the Employee class

# In models.py, inside the Employee class

    def get_daily_attendance_summary(self, year, month):
        """
        Generates a day-by-day attendance summary with updated logic for daily wage calculation,
        basing it on total working hours minus 2.
        """
        from .models import AttendanceSession, BreakSession
        from django.utils import timezone
        from calendar import monthrange
        from datetime import datetime, time, timedelta
        from decimal import Decimal

        days_in_month = monthrange(year, month)[1]
        daily_records = []
        total_monthly_wage = Decimal('0.00')

        start_work_time = self.working_start_time or time(9, 0)
        end_work_time = self.working_end_time or time(17, 0)
        
        start_dt_base = datetime.combine(datetime.today(), start_work_time)
        end_dt_base = datetime.combine(datetime.today(), end_work_time)
        if end_dt_base < start_dt_base:
            end_dt_base += timedelta(days=1)
        
        # --- START OF MODIFICATION ---
        
        # 1. Calculate the total scheduled work seconds for a full day.
        scheduled_work_seconds = (end_dt_base - start_dt_base).total_seconds()
        
        # 2. Subtract 2 hours (7200 seconds) to get the new target for a full day's wage.
        wage_target_seconds = scheduled_work_seconds - (2 * 3600)
        
        # 3. Add a safeguard: If the shift is 2 hours or less, use the original duration
        #    to prevent division by zero or negative targets.
        if wage_target_seconds <= 0:
            wage_target_seconds = scheduled_work_seconds

        # --- END OF MODIFICATION ---
            
        base_daily_wage = self.salary / Decimal(days_in_month) if days_in_month > 0 else Decimal('0.00')

        all_attendance_sessions = list(AttendanceSession.objects.filter(
            employee=self, login_time__year=year, login_time__month=month
        ).order_by('login_time'))
        
        all_break_sessions = list(BreakSession.objects.filter(
            employee=self, start_time__year=year, start_time__month=month
        ).order_by('start_time'))

        for day in range(1, days_in_month + 1):
            current_date = datetime(year, month, day).date()
            work_start_datetime = timezone.make_aware(datetime.combine(current_date, start_work_time))
            work_end_datetime = timezone.make_aware(datetime.combine(current_date, end_work_time))

            day_attendance = [
                s for s in all_attendance_sessions 
                if timezone.localtime(s.login_time).date() == current_date and s.login_time < work_end_datetime
            ]

            day_breaks = []
            for b in all_break_sessions:
                if timezone.localtime(b.start_time).date() == current_date:
                    break_end = b.end_time or work_end_datetime
                    if b.start_time < work_end_datetime and break_end > work_start_datetime:
                        day_breaks.append(b)

            login_time = None
            logout_time = None
            total_active_seconds = 0
            
            if day_attendance:
                earliest_actual_login = min([s.login_time for s in day_attendance])
                login_time = max(earliest_actual_login, work_start_datetime)

                logouts = [s.logout_time for s in day_attendance if s.logout_time]
                if logouts:
                    latest_actual_logout = max(logouts)
                    logout_time = min(latest_actual_logout, work_end_datetime)
                else:
                    logout_time = work_end_datetime

                if login_time >= logout_time:
                    total_active_seconds = 0
                else:
                    work_seconds = 0
                    for s in day_attendance:
                        if s.logout_time:
                            overlap_start = max(s.login_time, login_time)
                            overlap_end = min(s.logout_time, logout_time)
                            if overlap_end > overlap_start:
                                work_seconds += (overlap_end - overlap_start).total_seconds()

                    approved_break_seconds = 0
                    for b in day_breaks:
                        if b.approved and b.end_time:
                            overlap_start = max(b.start_time, login_time)
                            overlap_end = min(b.end_time, logout_time)
                            if overlap_end > overlap_start:
                                approved_break_seconds += (overlap_end - overlap_start).total_seconds()

                    total_active_seconds = work_seconds + approved_break_seconds

            # --- MODIFIED: Use the new wage_target_seconds for the calculation ---
            daily_wage = Decimal('0.00')
            if wage_target_seconds > 0:
                # Calculate the work ratio against the adjusted target time
                work_ratio = Decimal(total_active_seconds) / Decimal(wage_target_seconds)
                # Employee can earn more than 100% of their daily wage if they work longer
                # than the adjusted target time. The wage is not capped.
                daily_wage = base_daily_wage * work_ratio
                daily_wage = max(Decimal('0.00'), daily_wage) # Ensure wage is not negative

            total_monthly_wage += daily_wage

            # Formatting logic (remains the same)
            break_details = []
            for b in day_breaks:
                duration_str = "Ongoing"
                if b.end_time:
                    td = b.end_time - b.start_time
                    h, rem = divmod(td.total_seconds(), 3600)
                    m, _ = divmod(rem, 60)
                    duration_str = f"{int(h)}h {int(m)}m"
                
                break_details.append({
                    'timings': f"{timezone.localtime(b.start_time).strftime('%H:%M')} - {timezone.localtime(b.end_time).strftime('%H:%M') if b.end_time else 'Active'}",
                    'reason': b.logout_reason,
                    'duration': duration_str,
                    'approved': b.approved
                })

            h, rem = divmod(total_active_seconds, 3600)
            m, _ = divmod(rem, 60)
            total_duration_str = f"{int(h)}h {int(m)}m"

            daily_records.append({
                'sl_no': day,
                'date': current_date,
                'login_time': timezone.localtime(login_time) if login_time else None,
                'logout_time': timezone.localtime(logout_time) if logout_time else None,
                'break_sessions': break_details,
                'total_duration': total_duration_str,
                'daily_wage': round(daily_wage, 2),
            })

        return daily_records, round(total_monthly_wage, 2)



# In models.py, replace the existing get_current_month_earnings method with this one



# In models.py, inside the Employee class

    def get_current_month_earnings(self, year=None, month=None):
        """
        Calculates all earnings and deductions for a given month/year.
        This updated version uses the new event-based models for all bonuses.
        """
        # Import necessary models inside the function to avoid circular imports
        from .models import (
            ApplicationAssignment, Worksheet, MonthlyDeduction, 
            TrainingBonus, PerformanceBonus, MeetingAttendance
        )
        from django.db.models import Sum
        from django.utils import timezone
        from decimal import Decimal
        from collections import defaultdict

        # Default to the current month if no year or month is provided
        if year is None or month is None:
            now = timezone.localtime(timezone.now())
            year = now.year
            month = now.month

        # 1. Get the accurate attendance-based salary
        # This assumes your get_daily_attendance_summary function exists and returns the salary
        _, attendance_salary = self.get_daily_attendance_summary(year, month)

        # 2. Calculate Application Commissions (Logic remains the same)
        application_commissions = ApplicationAssignment.objects.filter(
            employee=self,
            application__approved=True,
            application__date_created__year=year,
            application__date_created__month=month
        ).aggregate(total=Sum('commission_amount'))['total'] or Decimal('0.00')

        # 3. Calculate Worksheet Commissions (Logic remains the same)
        total_worksheet_commission = Decimal('0.00')
        monthly_worksheets = self.worksheet_entries.filter(
            date__year=year,
            date__month=month,
            approved=True
        )
        
        is_xerox_dept = self.department and self.department.name == 'Xerox'
        if is_xerox_dept:
            daily_totals = defaultdict(Decimal)
            for entry in monthly_worksheets:
                daily_totals[entry.date] += entry.amount
            
            for total_amount in daily_totals.values():
                if total_amount > 500:
                    total_worksheet_commission += (total_amount - 500) * Decimal('0.05')
        else:
            total_monthly_amount = monthly_worksheets.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            total_worksheet_commission = total_monthly_amount * Decimal('0.05')

        # --- UPDATED BONUS CALCULATION LOGIC ---
        # 4. Calculate total bonuses by summing amounts from the new event-based models

        # Sum of bonuses from all meetings attended this month
        meetings_bonus = MeetingAttendance.objects.filter(
            employee=self, attended=True, meeting__date__year=year, meeting__date__month=month
        ).aggregate(total=Sum('meeting__amount'))['total'] or Decimal('0.00')
        
        # Sum of bonuses from all training sessions this month
        trainings_bonus = self.training_bonuses.filter(
            date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Sum of all performance incentives this month
        performance_bonus = self.performance_bonuses.filter(
            date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # 5. Calculate Deductions (Logic remains the same)
        deductions_qs = MonthlyDeduction.objects.filter(employee=self, year=year, month=month)
        total_deduction_amount = deductions_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # 6. Calculate Final Total Earnings
        total_before_deduction = (
            attendance_salary +
            application_commissions +
            total_worksheet_commission +
            meetings_bonus +
            trainings_bonus +
            performance_bonus
        )
        total_earnings = total_before_deduction - total_deduction_amount

        # 7. Return all calculated values in a dictionary
        return {
            'attendance_salary': attendance_salary,
            'application_commissions': application_commissions,
            'worksheet_commissions': total_worksheet_commission,
            'meetings_bonus': meetings_bonus,
            'trainings_bonus': trainings_bonus,
            'performance_bonus': performance_bonus,
            'monthly_deductions_list': deductions_qs,
            'deduction_amount': total_deduction_amount,
            'total_earnings': total_earnings,
        }


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


# In management/models.py

from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


# --- NEW MODEL: ServiceType ---
class ServiceType(models.Model):
    """
    Defines a type of service with pre-defined commission splits for sharing.
    """
    name = models.CharField(max_length=255, unique=True)
    
    # These fields represent the percentage split for shared applications
    referee_commission_percentage = models.DecimalField(
        "Referee Commission (%)",
        max_digits=5,
        decimal_places=2,
        default=50.00,
        help_text="Percentage of the total commission for the employee creating the application when it is shared."
    )
    partner_commission_percentage = models.DecimalField(
        "Partner Commission (%)",
        max_digits=5,
        decimal_places=2,
        default=50.00,
        help_text="Percentage of the total commission for the employee the application is shared with."
    )

    def __str__(self):
        return self.name

    def clean(self):
        """
        VALIDATION UPDATED:
        Ensures the sum of employee commissions does not exceed 100%.
        """
        total_employee_commission = self.referee_commission_percentage + self.partner_commission_percentage
        
        # Check if the total percentage is greater than 100
        if total_employee_commission > Decimal('100.00'):
            raise ValidationError("The sum of referee and partner commission percentages cannot exceed 100%.")

# --- MODIFIED MODEL: Application ---
class Application(models.Model):
    """
    This is the central model for a client's job.
    'application_name' is now 'service_type' and 'description' is removed.
    """
    id = models.AutoField(primary_key=True)
    date_created = models.DateTimeField(auto_now_add=True)
    

    service_type = models.ForeignKey(
        ServiceType, 
        on_delete=models.PROTECT, 
        related_name='applications',
        help_text="Select the type of service for this application.",
        blank=True,
        null = True
    )

    customer_name = models.CharField(max_length=150)
    customer_mobile_number = models.CharField(max_length=15)
    
    expected_date_of_completion = models.DateField(
        null=True, blank=True, help_text="Expected date to complete the work"
    )
    
    total_commission = models.DecimalField(max_digits=10, decimal_places=2)
    approved = models.BooleanField(default=False)
    assigned_employees = models.ManyToManyField(Employee, through='ApplicationAssignment', related_name='applications')

    def __str__(self):
        # Updated to reflect the new structure
        service_name = self.service_type.name if self.service_type else "[No Service Type]"
        
        # Return the new string format
        return f"App#{self.id} ({service_name}) for {self.customer_name}"

# The rest of your models (ApplicationAssignment, ApplicationDateExtension, etc.)
# can remain the same as they do not need changes for this request.


# In management/models.py

class ApplicationAssignment(models.Model):
    """
    Manages the relationship between an Application and an Employee,
    storing the specific commission amount for that assignment.
    """
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    
    commission_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text="The exact commission amount for this employee"
    )

    class Meta:
        unique_together = ('application', 'employee')

    def __str__(self):
        """
        CORRECTED: Safely displays the service type name instead of application_name.
        """
        # Safely get the service name from the related application
        service_name = self.application.service_type.name if self.application and self.application.service_type else "[No Service Type]"
        
        # Return the corrected string
        return f"{self.employee.name} has commission of ₹{self.commission_amount} for {service_name}"


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
    
    # NEW field for 'Notary and Bonds'
    bonds_sno = models.CharField("Bonds Sl. No", max_length=100, blank=True, null=True)

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
    


from django.utils.timezone import now

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
    date = models.DateField(default=now, null=True, blank=True, help_text="Creation date of the deduction record")

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




class EmployeeLinkAssignment(models.Model):
    """
    Assigns a ManagedLink to a specific Employee.
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="link_assignments")
    link = models.ForeignKey(ManagedLink, on_delete=models.CASCADE, related_name="employee_assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"'{self.link.description}' assigned to {self.employee.name}"

    class Meta:
        # Ensures that the same link cannot be assigned to the same employee more than once
        unique_together = ('employee', 'link')
        ordering = ['-assigned_at']
        verbose_name = "Employee Link Assignment"
        verbose_name_plural = "Employee Link Assignments"


class TodoTask(models.Model):
    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, related_name="personal_todos")
    description = models.CharField(max_length=255)
    due_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.description
    



# --- ADD THIS NEW MODEL for Meetings ---
class Meeting(models.Model):
    date = models.DateField(default=timezone.now)
    topic = models.CharField(max_length=255, help_text="e.g., Weekly Sync, Project Kick-off")
    amount = models.DecimalField(
        "Bonus Amount",
        max_digits=10, 
        decimal_places=2,
        help_text="Amount to be paid to each employee who attends."
    )
    attendees = models.ManyToManyField(
        Employee,
        through='MeetingAttendance',  # This specifies the intermediate model
        related_name='meetings_attended'
    )

    def __str__(self):
        return f"Meeting on {self.date} - {self.topic}"

# --- ADD THIS NEW 'THROUGH' MODEL for Attendance Tracking ---
class MeetingAttendance(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    attended = models.BooleanField(default=False)

    class Meta:
        # Ensures an employee can't be listed twice for the same meeting
        unique_together = ('meeting', 'employee')

    def __str__(self):
        status = "Attended" if self.attended else "Absent"
        return f"{self.employee.name} - {self.meeting.topic} ({status})"


        # --- NEW MODEL: PerformanceBonus ---
class PerformanceBonus(models.Model):
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='performance_bonuses')
    date = models.DateField(default=timezone.now)
    reason = models.CharField(max_length=255, help_text="e.g., Exceeded Sales Target, Project Completion Bonus")
    amount = models.DecimalField("Bonus Amount", max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Performance Bonus for {self.employee.name} on {self.date} - {self.reason}"


class TrainingBonus(models.Model):
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='training_bonuses')
    date = models.DateField(default=timezone.now)
    reason = models.CharField(max_length=255, help_text="e.g., Advanced Python Course, Safety Protocol Training")
    amount = models.DecimalField("Bonus Amount", max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Training Bonus for {self.employee.name} on {self.date} - {self.reason}"


# --- NEW MODEL FOR RESOURCE REPAIR CHECKLIST ---
class ResourceRepairReport(models.Model):
    """Stores the daily resource condition report submitted by an employee."""
    STATUS_CHOICES = [
        ('OK', 'OK'),
        ('Repair', 'Needs Repair')
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='repair_reports')
    date = models.DateField(default=timezone.now)
    
    monitor_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OK')
    cpu_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OK')
    keyboard_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OK')
    mouse_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OK')
    cables_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OK')
    printer_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OK')
    bike_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OK')
    
    remarks = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-date', 'employee']
        # This constraint ensures an employee can only submit one report per day
        constraints = [
            models.UniqueConstraint(fields=['employee', 'date'], name='unique_daily_report_per_employee')
        ]

    def __str__(self):
        return f"Repair Report for {self.employee.name} on {self.date}"
