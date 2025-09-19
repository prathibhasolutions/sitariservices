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

# --- ModelAdmin for Employee (CRUCIAL FOR THE FILTER) ---
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    # This search_fields is required for the autocomplete filter to work
    search_fields = ['name', 'mobile_number']
    list_display = ['employee_id', 'name', 'mobile_number', 'department']
    list_filter = ['department']

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

# --- Your Other Custom Admins (Unchanged) ---
@admin.register(AllowedIP)
class AllowedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'subnet_prefix', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('ip_address', 'subnet_prefix', 'description')
    list_editable = ('is_active',)
    ordering = ('-created_at',)
    fieldsets = (
        ('IP Configuration', {'fields': ('ip_address', 'subnet_prefix', 'description')}),
        ('Status', {'fields': ('is_active',)}),
    )

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

    
# --- Register All Other Models with Default Admin ---
# These models will just show up in the admin with no special customizations.
admin.site.register(Department)
admin.site.register(AttendanceSession)
admin.site.register(BreakSession)
admin.site.register(Application)
admin.site.register(ApplicationAssignment)
admin.site.register(Commission)
admin.site.register(Notification)
admin.site.register(UserNotificationStatus)
