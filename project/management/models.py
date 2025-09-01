from django.db import models

class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)  # This becomes the PK
    name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=15, unique=True)
    password = models.CharField(max_length=128)  # Use Django hashing on save!
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    joining_date = models.DateField()

    def __str__(self):
        return f"{self.employee_id} - {self.name}"

class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    present = models.BooleanField(default=False)

    class Meta:
        unique_together = ('employee', 'date')
        verbose_name_plural = 'Attendance records'

    def __str__(self):
        status = "Present" if self.present else "Absent"
        return f"{self.employee.name} - {self.date} - {status}"

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


class Notification(models.Model):
    description = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date_created.strftime('%Y-%m-%d %H:%M')} - {self.description[:30]}"