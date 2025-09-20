from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Sum

# Import all your models
from .models import (
    Employee,
    Department,
    AttendanceSession,
    BreakSession,
    Application,
    ApplicationAssignment,
    Commission,
    Worksheet,
    Invoice,
    Particular,
    AllowedIP,
    Notification,
    UserNotificationStatus,
    MonthlyDeduction,
)
from .models import EmployeeUpload

# Import the filters
from admin_auto_filters.filters import AutocompleteFilter
from rangefilter.filters import DateRangeFilter
from django.utils.html import format_html

# --- ModelAdmin for Employee (CRUCIAL FOR THE FILTER) ---
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    search_fields = ['name', 'mobile_number']
    # Add 'display_status' to the list of columns
    list_display = ['employee_id', 'name', 'mobile_number', 'department', 'display_status']
    list_filter = ['department']

    def display_status(self, obj):
        """
        Custom method to display the active status with a colored icon.
        """
        if obj.is_active():
            return format_html('<span style="color: green;">&#128994; Active</span>')
        return format_html('<span style="color: red;">&#128308; Inactive</span>')
    
    display_status.short_description = 'Status' # Sets the column header text

# --- Your Custom WorksheetAdmin (Unchanged) ---
class EmployeeFilter(AutocompleteFilter):
    title = 'Employee'
    field_name = 'employee'

@admin.register(Worksheet)
class WorksheetAdmin(admin.ModelAdmin):
    list_filter = [
        EmployeeFilter,
        ('date', DateRangeFilter),
        'approved',
    ]
    search_fields = ('employee__name', 'customer_name', 'customer_mobile', 'token_no', 'transaction_num')
    
    def get_list_display(self, request):
        employee_id = request.GET.get('employee__employee_id__exact')
        if employee_id:
            try:
                employee = Employee.objects.get(pk=employee_id)
                dept_name = employee.department.name
                base_cols = ['employee', 'date']
                if dept_name in ["Mee Seva", "Online Hub"]:
                    return base_cols + ['token_no', 'customer_name', 'customer_mobile', 'service', 'transaction_num', 'certificate_number', 'payment', 'amount', 'approved']
                elif dept_name == "Aadhaar":
                    return base_cols + ['token_no', 'customer_name', 'customer_mobile', 'service', 'enrollment_no', 'certificate_number', 'payment', 'amount', 'approved']
                elif dept_name == "Bhu Bharathi":
                    return base_cols + ['token_no', 'customer_name', 'login_mobile_no', 'application_no', 'status', 'payment', 'amount', 'approved']
                elif dept_name == "xerox":
                    return base_cols + ['particulars', 'amount', 'approved']
            except (Employee.DoesNotExist, AttributeError):
                pass
        return ['employee', 'date', 'department_name', 'amount', 'approved']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('print/', self.admin_site.admin_view(self.print_view), name='worksheet-print'),
        ]
        return custom_urls + urls

    def print_view(self, request):
        """
        This view renders the printable report. It now calculates totals
        and gets the specific employee for the report header.
        """
        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)

        # --- NEW: Calculate totals from the filtered queryset ---
        totals = queryset.aggregate(
            total_payment=Sum('payment'),
            total_amount=Sum('amount')
        )

        first_entry = queryset.first()
        department = first_entry.employee.department if first_entry and first_entry.employee else None

        # --- NEW: Get the specific employee if one was selected in the filter ---
        employee_id = request.GET.get('employee__employee_id__exact')
        employee = None
        if employee_id:
            try:
                employee = Employee.objects.get(pk=employee_id)
            except Employee.DoesNotExist:
                employee = None
        # If no employee is filtered but there are results, get the employee from the first entry
        elif first_entry:
            employee = first_entry.employee

        context = {
            'queryset': queryset,
            'department': department,
            'employee': employee,  # Pass the employee object
            'total_payment': totals.get('total_payment') or 0,  # Pass the calculated total
            'total_amount': totals.get('total_amount') or 0,  # Pass the calculated total
        }
        return render(request, "admin/reports/worksheet_print.html", context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['query_string'] = request.GET.urlencode()
        return super().changelist_view(request, extra_context)


from django.http import HttpResponseRedirect
from django.contrib import messages
from django.core.cache import cache

# --- Your Other Custom Admins (Unchanged) ---
@admin.register(AllowedIP)
class AllowedIPAdmin(admin.ModelAdmin):
    change_list_template = "admin/management/allowedip/change_list.html"
    list_display = ('ip_address', 'subnet_prefix', 'description', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('ip_address', 'subnet_prefix', 'description')
    list_editable = ('is_active',)
    ordering = ('-created_at',)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('allow-all/', self.admin_site.admin_view(self.enable_allow_all), name='ip-allow-all'),
            path('enforce-list/', self.admin_site.admin_view(self.enforce_ip_list), name='ip-enforce-list'),
            path('block-all/', self.admin_site.admin_view(self.block_all_ips), name='ip-block-all'),
        ]
        return custom_urls + urls

    # --- BUTTON LOGIC ---

    def enable_allow_all(self, request):
        # Delete any conflicting BLOCK rule first
        AllowedIP.objects.filter(description='GLOBAL_BLOCK').delete()
        # Create or update the unique ALLOW rule
        AllowedIP.objects.update_or_create(
            description='GLOBAL_ALLOW_ALL',
            defaults={'ip_address': '0.0.0.0/0', 'is_active': True}
        )
        cache.clear()
        self.message_user(request, "Success: IP restrictions are globally DISABLED. All IPs are now allowed.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def block_all_ips(self, request):
        # Delete any conflicting ALLOW rule first
        AllowedIP.objects.filter(description='GLOBAL_ALLOW_ALL').delete()
        # Create or update the unique BLOCK rule
        AllowedIP.objects.update_or_create(
            description='GLOBAL_BLOCK',
            defaults={'ip_address': '0.0.0.0/0', 'is_active': True} # The IP doesn't matter, only the description
        )
        cache.clear() 
        self.message_user(request, "CRITICAL: IP restrictions are globally ENABLED. ALL IPs are now blocked.", messages.ERROR)
        return HttpResponseRedirect("../")

    def enforce_ip_list(self, request):
        # Remove all global override rules
        AllowedIP.objects.filter(description__in=['GLOBAL_ALLOW_ALL', 'GLOBAL_BLOCK']).delete()
        cache.clear() 
        self.message_user(request, "Success: Global overrides have been removed. Access is now determined by your IP list.", messages.WARNING)
        return HttpResponseRedirect("../")

    # --- CACHE CLEARING ---
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from django.core.cache import cache
        cache.clear()


    
@admin.register(MonthlyDeduction)
class MonthlyDeductionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'month', 'year', 'amount', 'notes')
    list_filter = ('year', 'month', 'employee')
    search_fields = ('employee__name', 'notes')


@admin.register(EmployeeUpload)
class EmployeeUploadAdmin(admin.ModelAdmin):
    list_display = ('employee', 'description', 'file_link', 'uploaded_at')
    list_filter = ('uploaded_at', 'employee')
    search_fields = ('employee__name', 'description')
    readonly_fields = ('uploaded_at',)

    # Makes the file path a clickable link in the admin
    def file_link(self, obj):
        from django.utils.html import format_html
        if obj.file:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.file.url, obj.file.name)
        return "No file"
    file_link.short_description = 'File'



from django.db.models import DurationField, ExpressionWrapper, F
from django.utils import timezone
import calendar
from datetime import datetime

# ... (keep your other admin classes) ...


# --- NEW: Custom Admin for AttendanceSession ---

@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    # --- 1. FILTERS & SEARCH ---
    list_filter = [
        EmployeeFilter,  # Re-use the same employee filter
        ('login_time', DateRangeFilter), # Use the date range filter
    ]
    search_fields = ('employee__name', 'logout_reason')
    list_display = ('employee', 'login_time', 'logout_time', 'duration_display')

    # --- 2. Custom Display Field for Duration ---
    def duration_display(self, obj):
        if obj.logout_time:
            return str(obj.logout_time - obj.login_time).split('.')[0]
        return "Active"
    duration_display.short_description = 'Duration'

    # --- 3. PRINT BUTTON & CALCULATION LOGIC ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('print/', self.admin_site.admin_view(self.print_view), name='attendance-print'),
        ]
        return custom_urls + urls

    def print_view(self, request):
        """
        Renders a printable report of attendance sessions based on the admin filters
        and calculates the salary for that specific period.
        """
        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)

        calculated_salary = 0
        employee_id = request.GET.get('employee__employee_id__exact')
        employee = None
        department = None
        
        if employee_id:
            try:
                employee = Employee.objects.get(pk=employee_id)
                department = employee.department
                sessions_for_employee = queryset.filter(employee=employee)

                if sessions_for_employee.exists():
                    min_date = sessions_for_employee.earliest('login_time').login_time
                    max_date = sessions_for_employee.latest('login_time').login_time

                    approved_breaks_qs = BreakSession.objects.filter(
                        employee=employee,
                        approved=True,
                        end_time__isnull=False,
                        start_time__date__range=[min_date.date(), max_date.date()]
                    )
                    approved_break_duration = approved_breaks_qs.annotate(
                        duration=ExpressionWrapper(F('end_time') - F('start_time'), output_field=DurationField())
                    ).aggregate(total_duration=Sum('duration'))['total_duration'] or timezone.timedelta(0)

                    # --- THIS IS THE FIX ---
                    # The sum() function for timedeltas needs a second argument to define the start value.
                    attended_duration = sum(
                        [s.duration() for s in sessions_for_employee if s.duration() is not None], 
                        timezone.timedelta(0)
                    )
                    # --- END OF FIX ---

                    total_work_seconds = attended_duration.total_seconds() + approved_break_duration.total_seconds()

                    daily_working_seconds = 8 * 3600 
                    if employee.working_start_time and employee.working_end_time:
                        start_dt = datetime.combine(datetime.today(), employee.working_start_time)
                        end_dt = datetime.combine(datetime.today(), employee.working_end_time)
                        daily_working_seconds = (end_dt - start_dt).total_seconds()

                    days_in_period = (max_date.date() - min_date.date()).days + 1
                    expected_seconds = days_in_period * daily_working_seconds
                    
                    if expected_seconds > 0:
                        salary_ratio = total_work_seconds / expected_seconds
                        calculated_salary = float(employee.salary) * salary_ratio

            except Employee.DoesNotExist:
                employee = None

        context = {
            'queryset': queryset,
            'employee': employee,
            'department': department,
            'calculated_salary': calculated_salary,
            'request': request,
        }
        return render(request, 'admin/reports/attendance_print.html', context)


# --- Register All Other Models with Default Admin ---
# These models will just show up in the admin with no special customizations.
admin.site.register(Department)

admin.site.register(BreakSession)
admin.site.register(Application)
admin.site.register(ApplicationAssignment)
admin.site.register(Commission)
admin.site.register(Notification)
admin.site.register(UserNotificationStatus)
