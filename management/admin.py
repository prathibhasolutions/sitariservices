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
    Worksheet,
    AllowedIP,
    Notification,
    UserNotificationStatus,
    MonthlyDeduction,
    UploadService, 
    EmployeeUpload,
)




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

from django.templatetags.static import static # Import the static tag function
from .forms import EmployeeAdminForm

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    form = EmployeeAdminForm
    # --- 1. Display and Search Settings ---
    list_display = ['profile_pic_thumbnail', 'employee_id', 'name', 'mobile_number', 'department', 'display_status']
    search_fields = ['name', 'mobile_number']
    list_filter = ['department']
    change_list_template = "admin/employee_changelist.html"
    
    # --- 2. THIS IS THE FIX: Fieldset and Readonly Field Configuration ---
    # We define a readonly field to show the image preview.
    readonly_fields = ('profile_pic_preview',)

    fieldsets = (
        ('Personal Information', {
            'fields': (
                # Display the preview and the upload button on the same line
                ('profile_pic_preview', 'profile_picture'), 
                'name', 
                'mobile_number', 
                'department', 
                'joining_date'
            )
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
        ('Assigned Links', {
            'fields': ('assigned_links',),
        }),
        ('Security', {
            'fields': ('password',),
            'classes': ('collapse',),
        }),
    )

    filter_horizontal = ('assigned_links',)

    # --- 3. Custom Methods for Display ---

    @admin.display(description='')
    def profile_pic_preview(self, obj):
        """Creates a preview of the current profile picture."""
        if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 150px; border-radius: 8px;" />',
                obj.profile_picture.url
            )
        return "(No Image)"

    @admin.display(description='Picture')
    def profile_pic_thumbnail(self, obj):
        """Creates a small thumbnail for the list view."""
        if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover;" />',
                obj.profile_picture.url
            )
        default_image_url = static('images/default_profile.png')
        return format_html(
            '<img src="{}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover;" />',
            default_image_url
        )
    

    # --- 5. Custom Methods (Unchanged) ---
    def display_status(self, obj):
        if obj.is_active():
            return format_html('<span style="color: green;">&#128994; Active</span>')
        return format_html('<span style="color: red;">&#128308; Inactive</span>')
    display_status.short_description = 'Status'

    # --- 6. MODIFIED: Add the new Salary Report URL ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # Your existing attendance report URL
            path(
                'attendance-report/',
                self.admin_site.admin_view(self.attendance_report_view),
                name='employee-attendance-report'
            ),
            # --- ADD THIS NEW URL ---
            path(
                'salary-report/',
                self.admin_site.admin_view(self.salary_report_view),
                name='employee-salary-report'
            ),
        ]
        return custom_urls + urls

    # --- 7. Existing Attendance Report View (Unchanged) ---
    # Make sure you have this import at the top of your admin.py file
# Make sure you have this import at the top of your admin.py file
    from datetime import datetime

    # ... inside your EmployeeAdmin class

    def attendance_report_view(self, request):
        employee_id = request.GET.get('employee_id')
        month_str = request.GET.get('month')
        employee, daily_summary, total_wage = None, [], 0
        working_day_count = 0  # Initialize the counter

        if employee_id and month_str:
            try:
                employee = Employee.objects.get(pk=employee_id)
                year, month = map(int, month_str.split('-'))
                
                # This method returns a list of DICTIONARIES
                daily_summary_dicts, total_wage = employee.get_daily_attendance_summary(year, month)

                # --- START: FINAL Corrected Logic ---
                
                # Use a default start time if not set for the employee
                employee_start_time = employee.working_start_time or datetime.strptime("23:59", "%H:%M").time()

                processed_summary = []
                for record_dict in daily_summary_dicts:
                    # Get the login time from the dictionary
                    login_datetime = record_dict.get('login_time')
                    
                    # Initialize the remark
                    record_dict['remark'] = ''
                    
                    # Check for late login only if a login time exists
                    if login_datetime:
                        # --- THE FIX: Extract just the .time() component for comparison ---
                        login_time_only = login_datetime.time()
                        if login_time_only > employee_start_time:
                            record_dict['remark'] = 'Late Login'
                    
                    # Increment the counter if both login and logout times exist
                    if record_dict.get('login_time') and record_dict.get('logout_time'):
                        working_day_count += 1
                    
                    processed_summary.append(record_dict)
                
                # Use the newly processed list for the context
                daily_summary = processed_summary
                
                # --- END: Corrected Logic ---
                        
            except (Employee.DoesNotExist, ValueError):
                pass
                
        context = {
            **self.admin_site.each_context(request),
            'title': 'Monthly Attendance Report',
            'all_employees': Employee.objects.all(),
            'selected_employee': employee,
            'selected_month_str': month_str,
            'daily_summary_records': daily_summary, # This now contains the 'remark' key
            'total_monthly_wage': total_wage,
            'working_day_count': working_day_count,
        }
        return render(request, 'admin/attendance_report.html', context)


    def salary_report_view(self, request):
         # --- DEBUGGING: Print the raw GET parameters from the URL ---
        print(f"--- DEBUG: Received employee_id = {request.GET.get('employee')} ---")
        print(f"--- DEBUG: Received month_str = {request.GET.get('month')} ---")
        employee_id = request.GET.get('employee')
        month_str = request.GET.get('month') # Expects "YYYY-MM"

        selected_employee = None
        earnings_data = {}
        attended_meetings = []
        all_employees = Employee.objects.all().order_by('name')

        if month_str:
            try:
                dt = datetime.strptime(month_str, "%Y-%m")
                year, month = dt.year, dt.month
            except ValueError:
                now = timezone.now()
                year, month = now.year, now.month
        else:
            now = timezone.now()
            year, month = now.year, now.month
        
        # --- CORRECTION: Create a proper date object for the template ---
        from datetime import date
        selected_date_object = date(year, month, 1)
        
        if employee_id:
            try:
                selected_employee = Employee.objects.get(pk=employee_id)
                earnings_data = selected_employee.get_current_month_earnings(year, month)
                attended_meetings = MeetingAttendance.objects.filter(
                    employee=selected_employee,
                    attended=True,
                    meeting__date__year=year,
                    meeting__date__month=month
                ).order_by('-meeting__date')
            except Employee.DoesNotExist:
                pass

        context = {
            **self.admin_site.each_context(request),
            'title': 'Employee Salary Report',
            'all_employees': all_employees,
            'selected_employee': selected_employee,
            'selected_month_str': f"{year}-{month:02d}", # Keep this string for the input field
            'selected_date': selected_date_object,       # --- ADD THIS for displaying the date ---
            'current_month_earnings': earnings_data,
            'attended_meetings': attended_meetings,
        }
        print(f"--- DEBUG: Context['selected_employee'] = {context.get('selected_employee')} ---")
        print(f"--- DEBUG: Context['selected_date'] = {context.get('selected_date')} ---")
        return render(request, 'admin/salary_report.html', context)


    # --- 9. Existing changelist_view (Unchanged) ---
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['report_url'] = 'attendance-report/'
        return super().changelist_view(request, extra_context=extra_context)
    
    

# --- Don't forget to register the MonthlyBonus admin ---
@admin.register(MonthlyBonus)
class MonthlyBonusAdmin(admin.ModelAdmin):
    list_display = ('employee', 'year', 'month', 'meetings_bonus', 'trainings_bonus', 'performance_bonus')
    list_filter = ('year', 'month', 'employee')
    search_fields = ('employee__name',)
    autocomplete_fields = ['employee'] # Makes selecting an employee easy


from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Sum
from .models import Worksheet, Employee


@admin.register(Worksheet)
class WorksheetAdmin(admin.ModelAdmin):
    """
    Consolidated and corrected admin class for the Worksheet model.
    This version uses only native Django and Jazzmin features.
    """
    
    # --- THIS IS THE CORRECT, NATIVE WAY ---
    list_filter = [
        # For the Foreign Key autocomplete filter, just use the field name
        'employee',
        
        # For the date filter, use Django's built-in DateFieldListFilter
        ('date', admin.DateFieldListFilter),
        
        # Standard filters
        'approved',
        'employee__department',
    ]

    # --- THIS IS THE KEY TO THE AUTOCOMPLETE WIDGET ---
    # This tells the admin to use an autocomplete search box for the 'employee' ForeignKey field.
    # It replaces the need for the `EmployeeFilter` class.
    autocomplete_fields = ['employee']

    # Add 'employee__name' to make the autocomplete filter searchable
    search_fields = ('employee__name', 'customer_name', 'customer_mobile', 'token_no', 'transaction_num')

    # --- Your existing custom methods remain unchanged ---
    
    def get_list_display(self, request):
        employee_id = request.GET.get('employee__id__exact')  # Correct lookup for FK
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
                elif dept_name == "Forms":
                    return base_cols + ['particulars', 'amount', 'approved']
                elif dept_name == "Xerox":
                    return base_cols + ['amount', 'approved']
                elif dept_name == "Notary and Bonds":
                    return base_cols + ['token_no', 'customer_name', 'service', 'bonds_sno', 'payment', 'amount', 'approved']
            except (Employee.DoesNotExist, AttributeError):
                pass
        return ['employee', 'date', 'employee__department__name', 'amount', 'approved']

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
        
        employee_id = request.GET.get('employee__id__exact') # Correct lookup
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
    

from django.contrib import admin
# ... (other imports)
from .models import Worksheet, Employee, ResourceRepairReport # Import new model

# ... (WorksheetAdmin class is unchanged) ...

# your_app/admin.py

@admin.register(ResourceRepairReport)
class ResourceRepairReportAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 'date', 'monitor_status', 'cpu_status', 'keyboard_status', 
        'mouse_status', 'cables_status', 'printer_status', 'bike_status'
    )
    
    # --- THIS IS THE CORRECT, NATIVE WAY ---
    list_filter = (
        # Use Django's built-in date filter
        ('date', admin.DateFieldListFilter), 
        
        # Use the native filter for the 'employee' foreign key
        'employee',
        
        # The rest of your filters are fine
        'monitor_status', 
        'cpu_status', 
        'keyboard_status', 
        'mouse_status', 
        'cables_status', 
        'printer_status', 
        'bike_status'
    )

    # --- THIS IS THE KEY TO THE AUTOCOMPLETE WIDGET ---
    # This tells the admin to use an autocomplete search box for the 'employee' filter.
    autocomplete_fields = ['employee']

    search_fields = ('employee__name', 'remarks')
    list_per_page = 25

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employee')


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


from django.contrib import admin
from django.shortcuts import get_object_or_404, render
from .models import Application, ApplicationAssignment # Make sure to import your models

# Assuming ApplicationAssignmentInline is defined elsewhere
# from .inlines import ApplicationAssignmentInline 

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """
    Consolidated and corrected admin class for the Application model.
    This version uses only native Django and Jazzmin features.
    """
    
    inlines = [ApplicationAssignmentInline]
    list_display = ('application_name', 'customer_name', 'total_commission', 'date_created', 'approved')
    
    # --- THIS IS THE CORRECT, NATIVE WAY ---
    list_filter = (
        # For the ManyToMany autocomplete filter, just use the field name
        'assigned_employees',  
        
        # For a date filter, use Django's built-in DateFieldListFilter
        ('date_created', admin.DateFieldListFilter), 
        
        # Standard boolean filter
        'approved',
    )

    # --- THIS IS THE KEY TO THE AUTOCOMPLETE WIDGET ---
    # This tells the admin to use an autocomplete search box for this M2M field in filters.
    # It replaces the need for the `AssignedEmployeeFilter` class entirely.
    autocomplete_fields = ['assigned_employees']

    # Add 'assigned_employees__name' to make the autocomplete filter searchable by employee name
    search_fields = ('application_name', 'customer_name', 'assigned_employees__name')
    
    actions = ['approve_applications']
    
    # You can keep your template override for the print button
    change_list_template = 'admin/management/application/change_list.html'
    change_form_template = 'admin/management/application/change_form_detail.html'

    # --- Custom Methods (Unchanged) ---

    def approve_applications(self, request, queryset):
        queryset.update(approved=True)
        self.message_user(request, "Selected applications have been approved.")
    approve_applications.short_description = "Approve selected applications"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('print/', self.admin_site.admin_view(self.print_view), name='application-print'),
        ]
        return custom_urls + urls

    def print_view(self, request):
        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)
        context = {
            'title': 'Application Report',
            'applications': queryset,
            'site_header': self.admin_site.site_header,
        }
        return render(request, 'admin/management/application/print_template.html', context)

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


# your_app/admin.py

from django.contrib import admin
from django.utils.html import format_html

# ... other imports and admin classes ...

# your_app/admin.py

from django.contrib import admin
from django.utils.html import format_html

# ... other imports and admin classes ...

@admin.register(BreakSession)
class BreakSessionAdmin(admin.ModelAdmin):
    """
    Custom admin interface for the BreakSession model with a bulk approval action.
    """
    
    # --- 1. Display and Filter Settings (Unchanged) ---
    list_display = ('get_employee_name', 'start_time', 'end_time', 'get_approved_status')
    list_filter = ('employee', ('start_time', admin.DateFieldListFilter), 'approved')
    autocomplete_fields = ['employee']
    search_fields = ['employee__name']
    
    # --- 2. ADD THIS: Register the custom action ---
    actions = ['approve_selected_breaks']

    # --- 3. ADD THIS: Define the custom action method ---
    @admin.action(description='Approve selected break sessions')
    def approve_selected_breaks(self, request, queryset):
        """
        This action finds all selected BreakSession objects and sets their
        'approved' field to True.
        """
        # Perform the bulk update
        rows_updated = queryset.update(approved=True)
        
        # Display a success message to the admin user
        self.message_user(request, f'{rows_updated} break session(s) were successfully approved.')

    # --- 4. Helper methods for display (Unchanged) ---
    @admin.display(description='Employee Name', ordering='employee__name')
    def get_employee_name(self, obj):
        return obj.employee.name

    @admin.display(description='Approved Status', ordering='approved', boolean=True)
    def get_approved_status(self, obj):
        return obj.approved


# --- Register All Other Models with Default Admin ---
admin.site.register(Department)
# your_app/admin.py

from django.contrib import admin
from .models import Notification, UserNotificationStatus, Employee # Ensure models are imported

# --- 1. Define the Inline for the 'through' model ---
# This class tells the admin how to display the recipient list within a Notification.

class UserNotificationStatusInline(admin.TabularInline):
    """
    Displays the relationship between Notifications and Employees,
    allowing you to add recipients directly.
    """
    model = UserNotificationStatus
    extra = 1  # Start with one empty slot for adding an employee.
    
    # Use an autocomplete widget for a better user experience when selecting employees.
    autocomplete_fields = ['employee']
    
    # Make the 'is_read' field visible but not editable here.
    readonly_fields = ('is_read',)
    
    # We set can_delete to False because you typically wouldn't delete a recipient's
    # status, just the notification itself.
    can_delete = False


# --- 2. Define the Main Admin for the Notification model ---
# This class uses the inline defined above.

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Custom admin for creating notifications and managing their recipients.
    """
    inlines = [UserNotificationStatusInline]
    list_display = ('description_preview', 'created_at', 'recipient_count')
    search_fields = ('description',)
    ordering = ('-created_at',)
    
    # By default, ManyToMany fields aren't shown in the add/change form when
    # a 'through' model is used. The inline handles this, but we can add
    # an empty fieldset to make the layout cleaner if needed.
    fieldsets = (
        (None, {
            'fields': ('description',)
        }),
    )

    # --- Custom methods for a more informative list display ---

    @admin.display(description='Description')
    def description_preview(self, obj):
        """Shows the first 50 characters of the notification."""
        return obj.description[:50]

    @admin.display(description='Recipients')
    def recipient_count(self, obj):
        """Shows how many employees have received the notification."""
        return obj.recipients.count()


