from django.db import models
from django.utils import timezone

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

    def __str__(self):
        return f"{self.employee_id} - {self.name}"

class AttendanceSession(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_sessions')
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)  # Null if session active

    class Meta:
        verbose_name_plural = 'Attendance Sessions'
        ordering = ['-login_time']

    def duration(self):
        if self.logout_time:
            return self.logout_time - self.login_time
        else:
            return timezone.now() - self.login_time

    def __str__(self):
        logout_str = self.logout_time.strftime("%H:%M") if self.logout_time else "Active"
        return f"{self.employee.name} - {self.login_time.date()} {self.login_time.strftime('%H:%M')} to {logout_str}"

class Order(models.Model):
    STAGE_CHOICES = [
        ('start', 'Start'),
        ('stage2', 'Stage 2'),
        ('stage3', 'Stage 3'),
        ('stage4', 'Stage 4'),
        ('complete', 'Complete'),
    ]

    order_id = models.AutoField(primary_key=True)  # This becomes the PK
    order_description = models.TextField()
    customer_mobile_number = models.CharField(max_length=15)
    assigned_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='orders')
    stage = models.CharField(max_length=10, choices=STAGE_CHOICES, default='start')
    commission = models.DecimalField(max_digits=10, decimal_places=2)
    order_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Order#{self.order_id} for {self.customer_mobile_number} ({self.get_stage_display()})"
    

class Invoice(models.Model):
    invoice_id = models.AutoField(primary_key=True)
    date = models.DateField(default=timezone.now)
    customer_name = models.CharField(max_length=255)

class Particular(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='particulars', on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)


class Worksheet(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='worksheets')
    date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"Worksheet {self.id} by {self.employee.name} on {self.date}"

class WorksheetParticular(models.Model):
    worksheet = models.ForeignKey(Worksheet, related_name='particulars', on_delete=models.CASCADE)
    ticket_no = models.CharField(max_length=50)
    customer_name = models.CharField(max_length=255)
    service = models.CharField(max_length=255)
    transaction_no = models.CharField(max_length=255, blank=True, null=True)
    certificate_no = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)