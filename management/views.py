from django.shortcuts import render, redirect
from django.contrib import messages
from collections import defaultdict
from datetime import datetime,timedelta
from django.utils import timezone
from calendar import month_name,monthrange
from django.shortcuts import render, get_object_or_404
from django.db import models
from .models import Invoice
from django.http import JsonResponse
from .forms import InvoiceForm, ParticularFormSet,WorksheetEntryEditForm
from .utils import generate_otp, send_otp_whatsapp
from .models import Employee,AttendanceSession, BreakSession, Application, ApplicationAssignment, ChatMessage, Commission,Worksheet
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from django.db.models import Sum
from .forms import MeesevaWorksheetForm, AadharWorksheetForm, BhuBharathiWorksheetForm, XeroxWorksheetForm
from .models import UserNotificationStatus,Notification
from django.db.models.signals import post_save
from django.dispatch import receiver

def login_with_otp(request):
    if request.method == 'POST':
        mobile = request.POST.get('mobile')
        otp_entered = request.POST.get('otp')
        resend = request.POST.get('resend')

        if resend and mobile:
            otp = generate_otp()
            request.session['otp'] = otp
            request.session['mobile'] = mobile
            send_otp_whatsapp(mobile, otp)
            messages.success(request, f"OTP resent to {mobile}")
            return render(request, 'login.html', {'otp_sent': True, 'mobile': mobile})

        if otp_entered and mobile:
            expected_otp = request.session.get('otp')
            expected_mobile = request.session.get('mobile')

            if mobile != expected_mobile:
                messages.error(request, "Mobile number mismatch. Please request OTP again.")
                return redirect('login_with_otp')

            if otp_entered == expected_otp:
                try:
                    employee = Employee.objects.get(mobile_number=mobile)
                    request.session['employee_id'] = employee.employee_id

                    now = timezone.now()

                    # 1. Find and close any still-open AttendanceSession for this employee
                    open_attendance_sessions = AttendanceSession.objects.filter(
                        employee=employee,
                        logout_time__isnull=True
                    )
                    for old_session in open_attendance_sessions:
                        old_session.logout_time = now
                        old_session.logout_reason = "New Login Override"
                        old_session.session_closed = True
                        old_session.save()

                    # If a break session is still open (from idle/tab close/previous logout), end it NOW
                    last_break = BreakSession.objects.filter(
                        employee=employee,
                        end_time__isnull=True
                    ).order_by('-start_time').first()
                    if last_break:
                        last_break.end_time = now
                        last_break.ended_by_login = True  # optional for tracking
                        last_break.save()

                    # Create a new attendance session for this login
                    AttendanceSession.objects.create(
                        employee=employee,
                        login_time=now,
                        logout_time=None,
                        logout_reason=""
                    )

                    request.session.pop('otp', None)
                    request.session.pop('mobile', None)

                    return redirect('employee_dashboard')
                except Employee.DoesNotExist:
                    messages.error(request, "Employee with this mobile number not found.")
                    return redirect('login_with_otp')
            else:
                messages.error(request, "Invalid OTP. Please try again.")
                return render(request, 'login.html', {'otp_sent': True, 'mobile': mobile})

        if mobile and not otp_entered:
            try:
                Employee.objects.get(mobile_number=mobile)
            except Employee.DoesNotExist:
                messages.error(request, "Employee with this mobile number not found.")
                return render(request, 'login.html', {'otp_sent': False})

            otp = generate_otp()
            request.session['otp'] = otp
            request.session['mobile'] = mobile
            send_otp_whatsapp(mobile, otp)
            messages.success(request, f"OTP sent to {mobile}")
            return render(request, 'login.html', {'otp_sent': True, 'mobile': mobile})

    return render(request, 'login.html', {'otp_sent': False})




def change_password_request(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login_with_otp')  # Or your login page

    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        return redirect('login_with_otp')

    if request.method == 'POST':
        mobile = employee.mobile_number
        otp = generate_otp()
        request.session['change_pwd_otp'] = otp
        request.session['change_pwd_mobile'] = mobile
        send_otp_whatsapp(mobile, otp)
        messages.success(request, f"OTP sent to your registered mobile ({mobile}). Please verify to change password.")
        return redirect('change_password_verify')

    return render(request, 'change_password_request.html', {'employee': employee})


def change_password_verify(request):
    mobile = request.session.get('change_pwd_mobile')
    if not mobile:
        messages.error(request, "Please start the password change process again.")
        return redirect('change_password_request')

    otp_verified = request.session.get('otp_verified_for_pwd_change', False)

    if request.method == 'POST':
        if not otp_verified:
            # Verify OTP
            otp_entered = request.POST.get('otp')
            expected_otp = request.session.get('change_pwd_otp')

            if otp_entered != expected_otp:
                messages.error(request, "Invalid OTP. Please try again.")
                return render(request, 'change_password_verify.html')

            request.session['otp_verified_for_pwd_change'] = True
            messages.success(request, "OTP verified. Please set your new password.")
            return render(request, 'change_password_verify.html', {'otp_verified': True})

        else:
            # OTP already verified, set new password
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if not new_password:
                messages.error(request, "Password cannot be empty.")
                return render(request, 'change_password_verify.html', {'otp_verified': True})

            if new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return render(request, 'change_password_verify.html', {'otp_verified': True})

            try:
                employee = Employee.objects.get(mobile_number=mobile)
                employee.password = new_password  # Optionally hash here
                employee.save()
            except Employee.DoesNotExist:
                messages.error(request, "Employee not found during password update.")
                return redirect('change_password_request')

            # Clear session flags after password change
            request.session.pop('change_pwd_otp', None)
            request.session.pop('change_pwd_mobile', None)
            request.session.pop('otp_verified_for_pwd_change', None)

            messages.success(request, "Password changed successfully! You can now use the new password.")
            return redirect('employee_dashboard')

    # GET request
    return render(request, 'change_password_verify.html', {'otp_verified': otp_verified})



@csrf_exempt
def logout_view(request):
    employee_id = request.session.get('employee_id')
    logout_reason = ""
    if request.method == 'POST':
        logout_reason = request.POST.get('logout_reason', '')

    if employee_id:
        try:
            employee = Employee.objects.get(employee_id=employee_id)
            
            # Find the last open attendance session
            active_session = AttendanceSession.objects.filter(
                employee=employee,
                logout_time__isnull=True,
                session_closed=False
            ).order_by('-login_time').first()
            
            if active_session:
                now = timezone.now()
                reason = logout_reason if logout_reason else "Manual Logout"
                active_session.logout_time = now
                active_session.logout_reason = reason
                active_session.session_closed = True
                active_session.save()
                
                # Start a BreakSession (ends at next login)
                BreakSession.objects.create(
                    employee=employee,
                    start_time=now,
                    end_time=None,
                    logout_reason=reason if "idle" not in reason.lower() else "Inactive - Auto Logout",
                    approved=False,
                    ended_by_login=False
                )
        except Employee.DoesNotExist:
            pass

    request.session.flush()
    return redirect('login')


def calculate_employee_monthly_commission(employee, year, month):
    """
    Calculates the total commission for a given employee for a specific month and year.
    
    This function finds all approved applications the employee was assigned to
    in the given period and sums their commission based on their stored percentage share.
    """
    # Find all of the employee's assignments that were for applications
    # approved in the specified month and year.
    approved_assignments = ApplicationAssignment.objects.filter(
        employee=employee,
        application__approved=True,
        application__date_created__year=year,
        application__date_created__month=month
    ).select_related('application') # Use select_related to efficiently fetch the related Application

    total_commission = Decimal('0.0')
    for assignment in approved_assignments:
        # Calculate the share for this specific assignment
        commission_share = (assignment.commission_percentage / 100) * assignment.application.total_commission
        total_commission += commission_share
        
    return total_commission


# Make sure all required models and forms are imported
from .models import Employee, ApplicationAssignment 
from .forms import EmployeeUploadForm

# Make sure these models are imported at the top of your views.py
from .models import Employee, MeetingAttendance
from .forms import EmployeeUploadForm
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages

def employee_dashboard(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        request.session.flush()
        return redirect('login')

    # --- OTP and Session Management (Unchanged) ---
    otp_verified = request.session.get('otp_verified', False)
    show_sensitive = otp_verified
    otp_sent = request.session.get('otp_sent_flag', False)

    if request.method == 'POST':
        if 'send_otp' in request.POST:
            from .utils import generate_otp, send_otp_whatsapp
            otp = generate_otp()
            request.session['emp_otp'] = otp
            send_otp_whatsapp(employee.mobile_number, otp)
            request.session['otp_sent_flag'] = True
            messages.success(request, f"OTP sent to {employee.mobile_number}")
            return redirect('employee_dashboard')

        elif 'verify_otp' in request.POST:
            entered_otp = request.POST.get('otp')
            expected_otp = request.session.get('emp_otp')
            if entered_otp and entered_otp == expected_otp:
                request.session['otp_verified'] = True
                messages.success(request, "OTP verified. Sensitive data unlocked.")
                if 'emp_otp' in request.session:
                    del request.session['emp_otp']
            else:
                messages.error(request, "Invalid OTP. Please try again.")
                request.session['otp_sent_flag'] = True # Keep the form visible
            return redirect('employee_dashboard')

    # --- Data for Template (Unchanged) ---
    earnings_data = {}
    if show_sensitive:
        earnings_data = employee.get_current_month_earnings()

    # --- ADDITION: Fetch meetings attended this month ---
    now = timezone.now()
    attended_meetings = MeetingAttendance.objects.filter(
        employee=employee,
        attended=True,
        meeting__date__year=now.year,
        meeting__date__month=now.month
    ).select_related('meeting').order_by('-meeting__date')

    # --- Update the context to include the new meeting data ---
    context = {
        'employee': employee,
        'show_sensitive': show_sensitive,
        'otp_sent': otp_sent,
        'otp_verified': otp_verified,
        'current_month_earnings': earnings_data,
        'upload_form': EmployeeUploadForm(),
        'attended_meetings': attended_meetings,  # Pass the new data to the template
    }

    # --- Session Cleanup (Unchanged) ---
    if 'otp_verified' in request.session:
        del request.session['otp_verified']
    if 'otp_sent_flag' in request.session:
        if not 'emp_otp' in request.session:
             del request.session['otp_sent_flag']

    return render(request, 'employee_dashboard.html', context)



def attendance_view(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        request.session.flush()
        return redirect('login')

    today = timezone.localtime(timezone.now())
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    
    # --- Get the detailed daily summary from the model method ---
    daily_summary, total_wage = employee.get_daily_attendance_summary(year, month)

    # --- Logic for other sections (e.g., Today's sessions) ---
    if employee.working_start_time and employee.working_end_time:
        start_dt = datetime.combine(datetime.today().date(), employee.working_start_time)
        end_dt = datetime.combine(datetime.today().date(), employee.working_end_time)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        daily_working_hours = (end_dt - start_dt).total_seconds() / 3600
    else:
        daily_working_hours = 8.0

    todays_sessions_qs = AttendanceSession.objects.filter(
        employee=employee, 
        login_time__date=today.date()
    ).order_by('login_time')

    todays_sessions = []
    for session in todays_sessions_qs:
        duration = session.duration()
        total_seconds = duration.total_seconds() if duration else 0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        todays_sessions.append({
            'id': session.uuid.hex[:6],
            'login_time': timezone.localtime(session.login_time),
            'logout_time': timezone.localtime(session.logout_time) if session.logout_time else None,
            'duration_str': f"{hours}h {minutes}m",
            'logout_reason': session.logout_reason,
        })

    months = [{'value': i, 'display': month_name[i]} for i in range(1, 13)]
    current_year = today.year
    years = [current_year - i for i in range(5)][::-1]

    context = {
        'employee': employee,
        'months': months,
        'years': years,
        'selected_month': month,
        'selected_year': year,
        'selected_month_name': month_name[month],
        'today': today,
        'todays_sessions': todays_sessions,
        'daily_summary_records': daily_summary,
        'total_monthly_wage': total_wage,
        'calculated_salary': total_wage,
        'days_in_month': monthrange(year, month)[1],
        'daily_working_hours': daily_working_hours,
        'expected_hours': monthrange(year, month)[1] * daily_working_hours,
    }
    return render(request, 'attendance.html', context)


@csrf_exempt  # Only use csrf_exempt if you cannot get CSRF cookie in JS; otherwise, handle it securely
def attendance_ping(request):
    if request.method == "POST":
        employee_id = request.session.get('employee_id')
        if employee_id:
            from .models import AttendanceSession
            session = AttendanceSession.objects.filter(
                employee_id=employee_id, logout_time__isnull=True
            ).order_by('-login_time').first()
            if session:
                session.last_ping = timezone.now()
                session.save(update_fields=['last_ping'])
            return JsonResponse({'status': 'pong'})
    return JsonResponse({'status': 'notpong'}, status=400)



# --- Helper Functions ---

def get_logged_in_employee(request):
    """Retrieves the logged-in employee from the session."""
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return None
    try:
        return Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        return None

def require_employee(view_func):
    """Decorator to ensure an employee is logged in before accessing a view."""
    def wrapped_view(request, *args, **kwargs):
        employee = get_logged_in_employee(request)
        if not employee:
            messages.error(request, "You must be logged in to view this page.")
            return redirect('login') # Make sure you have a 'login' URL name
        # Pass the employee object to the view
        return view_func(request, employee, *args, **kwargs)
    return wrapped_view

# --- Main Views ---

# management/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from .models import Application, ApplicationAssignment, Employee, ChatMessage


@require_employee
def application_list_create_view(request, employee):
    """
    Handles viewing and creating work applications.
    This version requires a password for EVERY visit to the page.
    """
    
    # --- STEP 1: Handle POST requests ---
    if request.method == 'POST':
        # --- A) If it's a password verification attempt ---
        if 'verify_password' in request.POST:
            entered_password = request.POST.get('password')
            if entered_password == employee.password:
                # Password is correct. Proceed to load the main content.
                # We will gather all the context data and render the page below.
                pass # Fall through to the GET request logic at the end.
            else:
                # Password is wrong, show an error and re-render the prompt page.
                messages.error(request, "Incorrect password. Please try again.")
                return render(request, 'application_password_prompt.html', {'employee': employee})
        
        # --- B) If it's an application creation attempt ---
        else:
            try:
                assign_type = request.POST.get('assign_type')
                
                # Auto-calculate total commission if sharing
                if assign_type == 'sharing':
                    creator_amount = Decimal(request.POST.get('creator_share_amount', '0'))
                    partner_amount = Decimal(request.POST.get('partner_share_amount', '0'))
                    total_commission = creator_amount + partner_amount
                else:
                    total_commission = Decimal(request.POST.get('total_commission'))

                expected_date = request.POST.get('expected_date_of_completion') or None

                app = Application.objects.create(
                    application_name=request.POST.get('application_name'),
                    customer_name=request.POST.get('customer_name'),
                    customer_mobile_number=request.POST.get('customer_mobile_number'),
                    description=request.POST.get('description'),
                    expected_date_of_completion=expected_date,
                    total_commission=total_commission,
                    approved=False
                )

                if assign_type == 'own':
                    ApplicationAssignment.objects.create(application=app, employee=employee, commission_amount=total_commission)
                elif assign_type == 'sharing':
                    other_employee_id = request.POST.get('other_employee')
                    if not other_employee_id:
                        app.delete()
                        raise ValueError("Please select an employee to share with.")
                    
                    other_emp = Employee.objects.get(employee_id=other_employee_id)
                    ApplicationAssignment.objects.create(application=app, employee=employee, commission_amount=creator_amount)
                    ApplicationAssignment.objects.create(application=app, employee=other_emp, commission_amount=partner_amount)

                messages.success(request, f"Application '{app.application_name}' created successfully!")
                return redirect('applications')

            except (ValueError, TypeError, Employee.DoesNotExist) as e:
                messages.error(request, f"Error creating application: {e}")
                return redirect('applications')


    # --- STEP 2: Handle GET requests or successful password POST ---
    # If the request is a GET, the password hasn't been verified yet.
    if request.method == 'GET':
        # Always show the password prompt for a GET request.
        return render(request, 'application_password_prompt.html', {'employee': employee})
    
    # If we are here, it means it was a POST request with a correct password.
    # Now we gather all the data needed for the applications.html page.

    today = timezone.localtime(timezone.now())
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))

    your_applications = Application.objects.filter(assigned_employees=employee).order_by('-date_created').distinct()

    approved_assignments = ApplicationAssignment.objects.filter(
        employee=employee,
        application__approved=True,
        application__date_created__year=selected_year,
        application__date_created__month=selected_month
    ).select_related('application')
    
    total_monthly_commission = approved_assignments.aggregate(total=Sum('commission_amount'))['total'] or 0

    other_employees = Employee.objects.exclude(employee_id=employee.employee_id)
    months = [{'value': i, 'display': timezone.datetime(2000, i, 1).strftime('%B')} for i in range(1, 13)]
    selected_month_display = months[selected_month - 1]['display']
    current_year = timezone.now().year
    years = list(range(current_year - 5, current_year + 2))

    context = {
        'applications': your_applications,
        'approved_assignments': approved_assignments,
        'total_commission': total_monthly_commission,
        'other_employees': other_employees,
        'selected_month': selected_month,
        'selected_month_display': selected_month_display,
        'selected_year': selected_year,
        'months': months,
        'years': years,
    }
    
    return render(request, 'applications.html', context)


from .models import Application, ApplicationAssignment, ChatMessage, ApplicationDateExtension, Employee

@require_employee
def application_detail_view(request, employee, pk):
    """
    Displays application details, chat, and handles completion date extensions.
    """
    application = get_object_or_404(Application, pk=pk, assigned_employees=employee)
    
    # Check if the application is shared and not yet approved to enable chat
    is_shared = application.assigned_employees.count() > 1
    is_chat_active = is_shared and not application.approved

    # --- HANDLE POST REQUESTS ---
    if request.method == 'POST':
        # Check if the form submitted is the date extension form
        if 'extend_date' in request.POST:
            new_date_str = request.POST.get('new_completion_date')
            if new_date_str:
                new_date = timezone.datetime.strptime(new_date_str, '%Y-%m-%d').date()
                old_date = application.expected_date_of_completion

                # Create a record of the extension
                ApplicationDateExtension.objects.create(
                    application=application,
                    previous_date=old_date,
                    new_date=new_date,
                    extended_by=employee
                )
                
                # Update the main application with the new date
                application.expected_date_of_completion = new_date
                application.save()

                messages.success(request, f"Completion date extended to {new_date.strftime('%d %b %Y')}.")
            else:
                messages.error(request, "Please select a new date.")
            
            return redirect('application-detail', pk=application.pk)
        
        # Handle chat message submission (if chat is active)
        elif is_chat_active:
            message_text = request.POST.get('message')
            message_file = request.FILES.get('file')
            if message_text or message_file:
                ChatMessage.objects.create(
                    application=application,
                    employee=employee,
                    message=message_text,
                    file=message_file
                )
                return redirect('application-detail', pk=application.pk)

    # --- PREPARE DATA FOR TEMPLATE (GET REQUEST) ---
    assignments = application.applicationassignment_set.all().select_related('employee')
    extension_history = application.date_extensions.all().order_by('-timestamp')
    chat_messages = []
    if is_chat_active:
        chat_messages = application.chat_messages.all().order_by('timestamp').select_related('employee')

    context = {
        'application': application,
        'assignments': assignments,
        'is_chat_active': is_chat_active,
        'chat_messages': chat_messages,
        'extension_history': extension_history
    }
    return render(request, 'application_detail.html', context)




def create_invoice(request):
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        formset = ParticularFormSet(request.POST, prefix='form')
        if form.is_valid() and formset.is_valid():
            invoice = form.save()
            particulars = formset.save(commit=False)
            for p in particulars:
                p.invoice = invoice
                p.save()
            formset.save_m2m()  # Not strictly needed for FK, but safe
            return redirect('invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm()
        formset = ParticularFormSet(prefix='form')
    return render(request, 'create_invoice.html', {'form': form, 'formset': formset})


def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    particulars = invoice.particulars.all()
    total = sum([p.amount for p in particulars])
    return render(request, 'invoice_detail.html', {
        'invoice': invoice,
        'particulars': particulars,
        'total': total,
    })

from .models import EmployeeLinkAssignment

# your_app/views.py

def assigned_links_view(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')
    try:
        # The query is now much simpler
        employee = Employee.objects.prefetch_related('assigned_links').get(pk=employee_id)
    except Employee.DoesNotExist:
        request.session.flush()
        return redirect('login')

    context = {
        'employee': employee,
        # The links are now directly on the employee object
        'assigned_links': employee.assigned_links.all(),
    }
    return render(request, 'links.html', context)



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Employee, Worksheet, Department, ResourceRepairReport
from .forms import (
    MeesevaWorksheetForm, AadharWorksheetForm, BhuBharathiWorksheetForm, 
    FormsWorksheetForm, XeroxWorksheetForm, NotaryAndBondsWorksheetForm, 
    WorksheetEntryEditForm, ResourceRepairForm
)


@require_employee
def worksheet_view(request, employee):
    department = employee.department
    if not department:
        messages.error(request, "You are not assigned to a department. Cannot access worksheet.")
        return redirect('employee_dashboard')

    # --- Logic for the primary Worksheet Form ---
    form_map = {
        'Mee Seva': MeesevaWorksheetForm,
        'Online Hub': MeesevaWorksheetForm,
        'Aadhaar': AadharWorksheetForm,
        'Bhu Bharathi': BhuBharathiWorksheetForm,
        'Forms': FormsWorksheetForm,       # RENAMED from 'xerox'
        'Xerox': XeroxWorksheetForm,       # NEW 'Xerox' department
        'Notary and Bonds': NotaryAndBondsWorksheetForm, # NEW 'Notary and Bonds' department
    }
    WorksheetForm = form_map.get(department.name)
    worksheet_form = WorksheetForm() # Initialize for GET request

    # --- Logic for the new Resource Repair Form ---
    today = timezone.now().date()
    repair_form = None
    # Check if a report for the current employee and date already exists
    todays_repair_report = ResourceRepairReport.objects.filter(employee=employee, date=today).first()
    
    # Only create a form instance if a report for today doesn't exist yet
    if not todays_repair_report:
        repair_form = ResourceRepairForm()

    # --- Combined Form Handling on POST request ---
    if request.method == 'POST':
        # Use a hidden input to determine which form was submitted
        form_type = request.POST.get('form_type')

        # Handle the Worksheet Entry submission
        if form_type == 'worksheet_entry' and WorksheetForm:
            worksheet_form = WorksheetForm(request.POST)
            if worksheet_form.is_valid():
                entry = worksheet_form.save(commit=False)
                entry.employee = employee
                entry.department_name = department.name
                entry.save()
                messages.success(request, "Worksheet entry added successfully.")
                return redirect('worksheet')
            else:
                messages.error(request, "Please correct the errors in the worksheet entry.")

        # Handle the Resource Repair Report submission
        elif form_type == 'repair_report':
            # Double-check to prevent submitting again if the page was reloaded
            if todays_repair_report:
                 messages.error(request, "You have already submitted the repair report for today.")
            else:
                repair_form = ResourceRepairForm(request.POST)
                if repair_form.is_valid():
                    report = repair_form.save(commit=False)
                    report.employee = employee
                    report.date = today
                    report.save()
                    messages.success(request, "Resource repair report submitted successfully.")
                    return redirect('worksheet')
                else:
                    # If form is invalid, it will be re-rendered with errors below
                    messages.error(request, "Please correct the errors in the repair report.")
    
    # --- Data Fetching for Template Context ---
    # Today's worksheet entries and totals
    todays_entries = Worksheet.objects.filter(employee=employee, date=today)
    todays_total_amount = todays_entries.aggregate(total=Sum('amount'))['total'] or 0
    todays_total_payment = todays_entries.aggregate(total=Sum('payment'))['total'] or 0
    
    # Historical worksheet entries with filtering
    all_entries = Worksheet.objects.filter(employee=employee)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    mobile_filter = request.GET.get('mobile_number')

    if start_date_str and end_date_str:
        all_entries = all_entries.filter(date__range=[start_date_str, end_date_str])
    
    if mobile_filter:
        all_entries = all_entries.filter(
            Q(customer_mobile__icontains=mobile_filter) | 
            Q(login_mobile_no__icontains=mobile_filter)
        )
    
    context = {
        'employee': employee,
        'form': worksheet_form, # The main worksheet entry form
        'repair_form': repair_form, # The repair form (is None if already submitted)
        'department': department,
        'todays_entries': todays_entries,
        'todays_total_amount': todays_total_amount,
        'todays_total_payment': todays_total_payment,
        'todays_repair_report': todays_repair_report, # The submitted report object (is None if not submitted)
        'all_entries': all_entries.order_by('-date'),
        'today': today,
    }
    return render(request, 'worksheet.html', context)


@require_employee
def worksheet_entry_edit_view(request, employee, entry_id):
    entry = get_object_or_404(Worksheet, pk=entry_id, employee=employee)

    if entry.approved:
        messages.error(request, "This entry is approved and cannot be edited.")
        return redirect('worksheet')

    if request.method == 'POST':
        form = WorksheetEntryEditForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Certificate number updated successfully.")
            return redirect('worksheet')
        else:
            context = {'form': form, 'entry_id': entry_id}
            return render(request, 'partials/worksheet_edit_form.html', context)
    else:
        form = WorksheetEntryEditForm(instance=entry)

    context = {
        'form': form,
        'entry_id': entry_id
    }
    return render(request, 'partials/worksheet_edit_form.html', context)




@require_employee
def notification_list_view(request, employee):
    """
    Displays all notifications for the logged-in employee.
    """
    notifications = UserNotificationStatus.objects.filter(employee=employee).select_related('notification').order_by('-notification__created_at')
    
    context = {
        'notifications': notifications
    }
    return render(request, 'notifications.html', context)


@require_employee
def mark_notification_as_read(request, employee, pk):
    """
    Marks a specific notification as read for the logged-in employee.
    """
    notification_status = get_object_or_404(UserNotificationStatus, pk=pk, employee=employee)
    
    if not notification_status.is_read:
        notification_status.is_read = True
        notification_status.save()
    
    # Redirect back to the notification list
    return redirect('notification_list')


@receiver(post_save, sender=Notification)
def create_user_notification_statuses(sender, instance, created, **kwargs):
    """
    When a new Notification is created, this function creates a
    UserNotificationStatus object for every single employee in the system.
    """
    if created:
        # Get all employees
        all_employees = Employee.objects.all()
        # Create a UserNotificationStatus for each employee for the new notification
        for employee in all_employees:
            UserNotificationStatus.objects.create(
                employee=employee,
                notification=instance,
                is_read=False  # Default to unread
            )
        print(f"Created notification statuses for {all_employees.count()} employees for notification ID {instance.id}")

from .forms import EmployeeUploadForm

def upload_file_view(request):
    # Get employee_id from session, just like in your dashboard
    employee_id = request.session.get('employee_id')
    if not employee_id:
        messages.error(request, "Your session has expired. Please log in to upload files.")
        return redirect('login')

    if request.method == 'POST':
        form = EmployeeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Get the current employee instance
                current_employee = Employee.objects.get(employee_id=employee_id)
                
                # Save the form but don't commit to DB yet
                upload = form.save(commit=False)
                # Assign the employee from the session
                upload.employee = current_employee
                upload.save()
                
                messages.success(request, 'File uploaded successfully!')
            except Employee.DoesNotExist:
                messages.error(request, "Could not identify the employee. Please log in again.")
        else:
            # You can loop through form.errors for more specific messages if needed
            messages.error(request, 'There was an error with your upload. Please check the form and try again.')
            
    # Redirect back to the dashboard whether the upload was successful or not
    return redirect('employee_dashboard')



from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_datetime
from .models import TodoTask
import json

def todo_page_view(request):
    """Renders the main page for managing to-do tasks."""
    if not request.session.get("employee_id"):
        return redirect('login') # Or your login URL
    return render(request, 'todo_page.html')

def get_employee_todos(request):
    """API endpoint to fetch all upcoming tasks for the logged-in employee."""
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
    tasks = TodoTask.objects.filter(employee_id=employee_id).order_by('due_time')
    data = {
        "todos": [
            {"id": task.id, "description": task.description, "due_time": task.due_time.isoformat()}
            for task in tasks
        ]
    }
    return JsonResponse(data)

@require_POST
def add_employee_todo(request):
    """API endpoint to add a new to-do task."""
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)
        
    try:
        data = json.loads(request.body)
        description = data.get('description')
        due_time_str = data.get('due_time')

        if not description or not due_time_str:
            return JsonResponse({"error": "Description and due time are required."}, status=400)
        
        due_time = parse_datetime(due_time_str)
        if not due_time:
            return JsonResponse({"error": "Invalid date format."}, status=400)

        TodoTask.objects.create(employee_id=employee_id, description=description, due_time=due_time)
        return JsonResponse({"status": "success"}, status=201)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

@require_POST
def delete_employee_todo(request, task_id):
    """API endpoint to delete a to-do task."""
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
    task = get_object_or_404(TodoTask, id=task_id, employee_id=employee_id)
    task.delete()
    return JsonResponse({"status": "success"})
