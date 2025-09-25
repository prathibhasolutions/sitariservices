# your_app/admin.py

from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Sum, DurationField, ExpressionWrapper, F
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime

# Import all your models
from .models import (
    Employee,
    Meeting, 
    MeetingAttendance,
    MonthlyBonus,
    Department,
    BreakSession,
    Application,
    ApplicationAssignment,
    Commission,
    Worksheet,
    AllowedIP,
    Notification,
    UserNotificationStatus,
    MonthlyDeduction,
    UploadService, 
    EmployeeUpload,
)

# Import the filters
from admin_auto_filters.filters import AutocompleteFilter
from rangefilter.filters import DateRangeFilter


from .forms import EmployeeLinksForm
from .models import ManagedLink # Ensure ManagedLink is imported

@admin.register(ManagedLink)
class ManagedLinkAdmin(admin.ModelAdmin):
    list_display = ('description', 'url', 'created_at')
    search_fields = ('description',)
    ordering = ('description',)

# --- UNIFIED EmployeeAdmin CLASS ---
# In your management/admin.py file

# In your management/admin.py file

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    # --- 1. General Settings (Unchanged) ---
    search_fields = ['name', 'mobile_number']
    list_display = ['employee_id', 'name', 'mobile_number', 'department', 'display_status']
    list_filter = ['department']
    
    # --- 2. Custom Template for Attendance Report Button (Unchanged) ---
    change_list_template = "admin/employee_changelist.html"
    
    # --- 3. CORRECTED Fieldsets to manage all fields ---
    # This now includes 'assigned_links', removing the need for a custom form.
    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'mobile_number', 'department', 'joining_date')
        }),
        ('Salary & Compensation', {
            'fields': ('salary', 'pf', 'esi')
        }),
        ('Working Hours', {
            'fields': ('working_start_time', 'working_end_time')
        }),
        ('Advances', {
            'fields': ('advances',),
            'description': 'Enter the total outstanding advance amount for this employee.'
        }),
        # --- The assigned_links field is now handled here ---
        ('Assigned Links', {
            'fields': ('assigned_links',),
        }),
        ('Security', {
            'fields': ('password',),
            'classes': ('collapse',),
        }),
    )

    # --- 4. User-friendly widget for ManyToMany field ---
    # This makes selecting links much easier.
    filter_horizontal = ('assigned_links',)

    # --- 5. Your existing custom methods (Unchanged) ---
    def display_status(self, obj):
        if obj.is_active():
            return format_html('<span style="color: green;">&#128994; Active</span>')
        return format_html('<span style="color: red;">&#128308; Inactive</span>')
    display_status.short_description = 'Status'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'attendance-report/',
                self.admin_site.admin_view(self.attendance_report_view),
                name='employee-attendance-report'
            ),
        ]
        return custom_urls + urls

    def attendance_report_view(self, request):
        employee_id = request.GET.get('employee_id')
        month_str = request.GET.get('month')
        employee, daily_summary, total_wage = None, [], 0
        if employee_id and month_str:
            try:
                employee = Employee.objects.get(pk=employee_id)
                year, month = map(int, month_str.split('-'))
                daily_summary, total_wage = employee.get_daily_attendance_summary(year, month)
            except (Employee.DoesNotExist, ValueError):
                pass
        context = {
            'title': 'Monthly Attendance Report',
            'all_employees': Employee.objects.all(),
            'selected_employee': employee,
            'selected_month_str': month_str,
            'daily_summary_records': daily_summary,
            'total_monthly_wage': total_wage,
        }
        return render(request, 'admin/attendance_report.html', context)
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['report_url'] = 'attendance-report/'
        return super().changelist_view(request, extra_context=extra_context)
    
    # --- The custom change_view and change_form_template have been REMOVED ---
    # They are no longer needed and were the source of the problem.


# --- Don't forget to register the MonthlyBonus admin ---
@admin.register(MonthlyBonus)
class MonthlyBonusAdmin(admin.ModelAdmin):
    list_display = ('employee', 'year', 'month', 'meetings_bonus', 'trainings_bonus', 'performance_bonus')
    list_filter = ('year', 'month', 'employee')
    search_fields = ('employee__name',)
    autocomplete_fields = ['employee'] # Makes selecting an employee easy


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
        'employee__department',  # Add this for department-wise filtering
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
        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)
        totals = queryset.aggregate(
            total_payment=Sum('payment'),
            total_amount=Sum('amount')
        )
        first_entry = queryset.first()
        department = first_entry.employee.department if first_entry and first_entry.employee else None
        employee_id = request.GET.get('employee__employee_id__exact')
        employee = None
        if employee_id:
            try:
                employee = Employee.objects.get(pk=employee_id)
            except Employee.DoesNotExist:
                employee = None
        elif first_entry:
            employee = first_entry.employee
        context = {
            'queryset': queryset,
            'department': department,
            'employee': employee,
            'total_payment': totals.get('total_payment') or 0,
            'total_amount': totals.get('total_amount') or 0,
        }
        return render(request, "admin/reports/worksheet_print.html", context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['query_string'] = request.GET.urlencode()
        return super().changelist_view(request, extra_context)


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

    def enable_allow_all(self, request):
        AllowedIP.objects.filter(description='GLOBAL_BLOCK').delete()
        AllowedIP.objects.update_or_create(
            description='GLOBAL_ALLOW_ALL',
            defaults={'ip_address': '0.0.0.0/0', 'is_active': True}
        )
        cache.clear()
        self.message_user(request, "Success: IP restrictions are globally DISABLED. All IPs are now allowed.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def block_all_ips(self, request):
        AllowedIP.objects.filter(description='GLOBAL_ALLOW_ALL').delete()
        AllowedIP.objects.update_or_create(
            description='GLOBAL_BLOCK',
            defaults={'ip_address': '0.0.0.0/0', 'is_active': True}
        )
        cache.clear() 
        self.message_user(request, "CRITICAL: IP restrictions are globally ENABLED. ALL IPs are now blocked.", messages.ERROR)
        return HttpResponseRedirect("../")

    def enforce_ip_list(self, request):
        AllowedIP.objects.filter(description__in=['GLOBAL_ALLOW_ALL', 'GLOBAL_BLOCK']).delete()
        cache.clear() 
        self.message_user(request, "Success: Global overrides have been removed. Access is now determined by your IP list.", messages.WARNING)
        return HttpResponseRedirect("../")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.clear()
    
@admin.register(MonthlyDeduction)
class MonthlyDeductionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'month', 'year', 'amount', 'notes')
    list_filter = ('year', 'month', 'employee')
    search_fields = ('employee__name', 'notes')

@admin.register(UploadService)
class UploadServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(EmployeeUpload)
class EmployeeUploadAdmin(admin.ModelAdmin):
    list_display = ('employee', 'service', 'description', 'file_link', 'uploaded_at')
    list_filter = ('service', 'employee', 'uploaded_at')
    search_fields = ('employee__name', 'service__name', 'description')
    readonly_fields = ('uploaded_at',)

    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.file.url, obj.file.name)
        return "No file"
    
    file_link.short_description = 'File'



class ApplicationAssignmentInline(admin.TabularInline):
    model = ApplicationAssignment
    extra = 1
    autocomplete_fields = ['employee']


class AssignedEmployeeFilter(AutocompleteFilter):
    title = 'Assigned Employee'  # Title for the filter sidebar
    field_name = 'assigned_employees' # The ManyToManyField on your Application model


from django.contrib import admin
from django.shortcuts import get_object_or_404, render
from .models import Application, ApplicationAssignment # Make sure to import your models

# Assuming ApplicationAssignmentInline is defined elsewhere
# from .inlines import ApplicationAssignmentInline 

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    inlines = [ApplicationAssignmentInline]
    list_display = ('application_name', 'customer_name', 'total_commission', 'date_created', 'approved')
    
    # 1. MODIFICATION: Update list_filter
    list_filter = (
        AssignedEmployeeFilter,  # Use the new filter here
        ('date_created', DateRangeFilter), # Add the date range filter
        'approved',
    )

    search_fields = ('application_name', 'customer_name')
    actions = ['approve_applications']
    
    # 2. MODIFICATION: Override the changelist template to add the print button
    change_list_template = 'admin/management/application/change_list.html'
    
    change_form_template = 'admin/management/application/change_form_detail.html'

    def approve_applications(self, request, queryset):
        queryset.update(approved=True)
        self.message_user(request, "Selected applications have been approved.")
    approve_applications.short_description = "Approve selected applications"

    # 3. ADDITION: Add get_urls and print_view methods for printing
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('print/', self.admin_site.admin_view(self.print_view), name='application-print'),
        ]
        return custom_urls + urls

    def print_view(self, request):
        # This view uses the current filters from the admin URL to get the right queryset
        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)
        
        context = {
            'title': ' Application Report',
            'applications': queryset,
            'site_header': self.admin_site.site_header,
        }
        return render(request, 'admin/management/application/print_template.html', context)

    # Your change_view method remains unchanged
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        application = get_object_or_404(Application, pk=object_id)
        assignments = application.applicationassignment_set.all().select_related('employee')
        extension_history = application.date_extensions.all().order_by('-timestamp')
        chat_messages = application.chat_messages.all().order_by('timestamp').select_related('employee')
        is_shared = application.assigned_employees.count() > 1
        is_chat_active = is_shared and not application.approved
        extra_context['assignments'] = assignments
        extra_context['extension_history'] = extension_history
        extra_context['chat_messages'] = chat_messages
        extra_context['is_chat_active'] = is_chat_active
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )

from decimal import Decimal

class MeetingAttendanceInline(admin.TabularInline):
    model = MeetingAttendance
    extra = 1  # Start with one empty slot for adding an employee
    autocomplete_fields = ['employee'] # Makes selecting employees easy

@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('date', 'topic', 'amount')
    list_filter = ('date',)
    search_fields = ('topic',)
    inlines = [MeetingAttendanceInline]

    def save_formset(self, request, form, formset, change):
        """
        This is the core logic. It runs after you save the meeting attendance.
        It automatically finds or creates the MonthlyBonus record for each employee
        and updates their meetings_bonus.
        """
        super().save_formset(request, form, formset, change)

        for f in formset.forms:
            if f.cleaned_data:
                # Get the meeting instance and the amount
                meeting = f.cleaned_data['meeting']
                meeting_amount = meeting.amount
                
                # Get the employee and the date of the meeting
                employee = f.cleaned_data['employee']
                year = meeting.date.year
                month = meeting.date.month

                # Find or create the MonthlyBonus record for that employee for that month
                bonus_obj, created = MonthlyBonus.objects.get_or_create(
                    employee=employee,
                    year=year,
                    month=month
                )

                # Recalculate the total meeting bonus for that month
                total_bonus = Decimal('0.00')
                attended_meetings = MeetingAttendance.objects.filter(
                    employee=employee, 
                    attended=True,
                    meeting__date__year=year,
                    meeting__date__month=month
                )
                
                for attendance in attended_meetings:
                    total_bonus += attendance.meeting.amount
                
                # Update the bonus object with the new total and save it
                bonus_obj.meetings_bonus = total_bonus
                bonus_obj.save()
        
        self.message_user(request, "Meeting attendance saved and monthly bonuses have been updated.")


# --- Register All Other Models with Default Admin ---
admin.site.register(Department)
admin.site.register(BreakSession)
admin.site.register(Commission)
admin.site.register(Notification)
admin.site.register(UserNotificationStatus)
