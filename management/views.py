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
from datetime import datetime
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


def employee_dashboard(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        request.session.flush()
        return redirect('login')

    # --- Your existing OTP state management ---
    show_sensitive = False
    otp_sent = request.session.get('otp_sent_flag', False) # Preserve state across GET requests
    otp_verified = request.session.get('otp_verified', False)

    if otp_verified:
        show_sensitive = True

    if request.method == 'POST':
        if 'send_otp' in request.POST:
            from .utils import generate_otp, send_otp_whatsapp

            otp = generate_otp()
            request.session['emp_otp'] = otp
            send_otp_whatsapp(employee.mobile_number, otp)

            # Set flags in session to remember state after redirect
            request.session['otp_sent_flag'] = True
            otp_sent = True
            messages.success(request, f"OTP sent to {employee.mobile_number}")
            return redirect('employee_dashboard')

        elif 'verify_otp' in request.POST:
            entered_otp = request.POST.get('otp')
            expected_otp = request.session.get('emp_otp')

            if entered_otp and entered_otp == expected_otp:
                request.session['otp_verified'] = True
                show_sensitive = True
                otp_verified = True
                messages.success(request, "OTP verified. Sensitive data unlocked.")
                if 'emp_otp' in request.session:
                    del request.session['emp_otp']
                if 'otp_sent_flag' in request.session:
                    del request.session['otp_sent_flag']
            else:
                messages.error(request, "Invalid OTP. Please try again.")
                request.session['otp_sent_flag'] = True

            return redirect('employee_dashboard')

    if request.method == 'GET' and not request.session.get('otp_sent_flag'):
        otp_sent = False
    elif request.session.get('otp_sent_flag'):
        otp_sent = True

    # --- THE ONLY CHANGE IS HERE ---
    current_month_earnings_data = employee.get_current_month_earnings()
    # --- END OF CHANGE ---

    context = {
        'employee': employee,
        'show_sensitive': show_sensitive,
        'otp_sent': otp_sent,
        'otp_verified': otp_verified,
        'current_month_earnings': current_month_earnings_data,
    }

    # --- ADD THIS BLOCK: RESET OTP VERIFIED FLAG AFTER RENDERING THE PAGE ---
    if 'otp_verified' in request.session and request.method == 'GET':
        del request.session['otp_verified']
    # --- END OF CHANGE ---

    # Reset the one-time flag after rendering
    if 'otp_sent_flag' in request.session and request.method == 'GET':
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

    # Get total days in the selected month
    days_in_month = monthrange(year, month)[1]

    # Calculate employee's daily working hours
    if employee.working_start_time and employee.working_end_time:
        # Convert time objects to datetime for calculation
        start_dt = datetime.combine(datetime.today().date(), employee.working_start_time)
        end_dt = datetime.combine(datetime.today().date(), employee.working_end_time)
        
        # Handle overnight shifts (if end time is before start time)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        
        daily_working_seconds = (end_dt - start_dt).total_seconds()
        daily_working_hours = daily_working_seconds / 3600
    else:
        # Default to 8 hours if working times not set
        daily_working_seconds = 8 * 3600
        daily_working_hours = 8.0

    qs = AttendanceSession.objects.filter(
        employee=employee,
        login_time__year=year,
        login_time__month=month
    ).order_by('login_time')

    # Apply working hours filter if present
    if employee.working_start_time and employee.working_end_time:
        qs = qs.filter(
            login_time__time__gte=employee.working_start_time,
            login_time__time__lte=employee.working_end_time
        )

    sessions_by_date = defaultdict(list)
    for session in qs:
        login_local = timezone.localtime(session.login_time)
        logout_local = timezone.localtime(session.logout_time) if session.logout_time else None
        duration = session.duration()
        total_seconds = duration.total_seconds() if duration else 0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        duration_str = f"{hours}h {minutes}m"
        sessions_by_date[login_local.date()].append({
            'id': session.uuid.hex[:6],
            'login_time': login_local,
            'logout_time': logout_local,
            'duration_str': duration_str,
            'logout_reason': session.logout_reason,
        })

    # Build a list of breaks with precomputed duration string
    break_sessions_qs = BreakSession.objects.filter(
        employee=employee,
        start_time__year=year,
        start_time__month=month
    ).order_by('start_time')
    
    # Apply working hours filter to break sessions too
    if employee.working_start_time and employee.working_end_time:
        break_sessions_qs = break_sessions_qs.filter(
            start_time__time__gte=employee.working_start_time,
            start_time__time__lte=employee.working_end_time
        )

    break_list = []
    for bs in break_sessions_qs:
        if bs.end_time:
            td = bs.end_time - bs.start_time
            total_seconds = int(td.total_seconds())
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            duration_str = f"{h}h {m}m"
        else:
            duration_str = "Ongoing"
        break_list.append({
            'id': bs.uuid.hex[:6],
            'start_time': bs.start_time,
            'end_time': bs.end_time,
            'logout_reason': bs.logout_reason,
            'approved': bs.approved,
            'duration_str': duration_str,
        })

    # Salary calculation based on employee's actual working hours
    attended_seconds = sum([s.duration().total_seconds() for s in qs])
    
    # Only count approved breaks within working hours
    approved_break_seconds = sum([
        (bs.end_time - bs.start_time).total_seconds()
        for bs in break_sessions_qs.filter(approved=True, end_time__isnull=False)
    ])
    
    total_work_seconds = attended_seconds + approved_break_seconds
    
    # Use employee's actual daily working hours × days in month
    expected_seconds = days_in_month * daily_working_seconds
    salary = float(employee.salary) * (total_work_seconds / expected_seconds) if expected_seconds else 0

    months = [{'value': i, 'display': month_name[i]} for i in range(1, 13)]
    current_year = today.year
    years = [current_year - i for i in range(5)][::-1]
    selected_month_name = month_name[month]

    # Today's sessions - also apply working hours filter
    todays_sessions_qs = AttendanceSession.objects.filter(
        employee=employee, 
        login_time__date=today.date()
    ).order_by('login_time')
    
    # Apply working hours filter to today's sessions
    if employee.working_start_time and employee.working_end_time:
        todays_sessions_qs = todays_sessions_qs.filter(
            login_time__time__gte=employee.working_start_time,
            login_time__time__lte=employee.working_end_time
        )

    todays_sessions = []
    for session in todays_sessions_qs:
        login_local = timezone.localtime(session.login_time)
        logout_local = timezone.localtime(session.logout_time) if session.logout_time else None
        duration = session.duration()
        total_seconds = duration.total_seconds() if duration else 0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        duration_str = f"{hours}h {minutes}m"
        todays_sessions.append({
            'id': session.uuid.hex[:6],
            'login_time': login_local,
            'logout_time': logout_local,
            'duration_str': duration_str,
            'logout_reason': session.logout_reason,
        })

    context = {
        'employee': employee,
        'sessions_by_date': dict(sessions_by_date),
        'break_sessions': break_list,
        'months': months,
        'years': years,
        'selected_month': month,
        'selected_year': year,
        'selected_month_name': selected_month_name,
        'today': today,
        'todays_sessions': todays_sessions,
        'calculated_salary': salary,
        'days_in_month': days_in_month,
        'daily_working_hours': daily_working_hours,  # Now properly calculated
        'expected_hours': days_in_month * daily_working_hours,  # Uses employee's actual hours
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

@require_employee
def application_list_create_view(request, employee):
    """
    Handles viewing and creating work applications.
    Requires a password verification once per session to access the page.
    """
    
    # --- STEP 1: PASSWORD VERIFICATION GATE ---
    # Check if the user has already verified their password in this session.
    if not request.session.get('application_password_verified', False):
        
        # If the user is submitting the password form...
        if request.method == 'POST' and 'verify_password' in request.POST:
            entered_password = request.POST.get('password')
            
            # Check if the entered password is correct.
            if entered_password == employee.password:
                # If correct, set a flag in the session to "remember" the verification.
                request.session['application_password_verified'] = True
                # Redirect back to this same page to clear the POST data and load the main content.
                return redirect('applications')
            else:
                # If incorrect, show an error message.
                messages.error(request, "Incorrect password. Please try again.")
        
        # If the password is not verified yet (either a GET request or a failed attempt),
        # render the password prompt template.
        return render(request, 'application_password_prompt.html', {'employee': employee})

    # --- FROM THIS POINT ON, THE PASSWORD IS VERIFIED FOR THE CURRENT SESSION ---

    # --- STEP 2: HANDLE APPLICATION CREATION (POST REQUEST) ---
    # This block only runs if the request is a POST and is NOT from the password form.
    if request.method == 'POST':
        try:
            # Retrieve data from the application creation form.
            assign_type = request.POST.get('assign_type')
            total_commission = Decimal(request.POST.get('total_commission'))

            # Create the main application object.
            app = Application.objects.create(
                application_name=request.POST.get('application_name'),
                customer_name=request.POST.get('customer_name'),
                customer_mobile_number=request.POST.get('customer_mobile_number'),
                description=request.POST.get('description'),
                expected_days_to_complete=int(request.POST.get('expected_days', 1)),
                total_commission=total_commission,
                approved=False  # New applications are not approved by default.
            )

            # Handle the assignment based on whether it's for self or shared.
            if assign_type == 'own':
                # Assign 100% of the commission to the creator.
                ApplicationAssignment.objects.create(application=app, employee=employee, commission_percentage=100)
            
            elif assign_type == 'sharing':
                # Retrieve details for sharing.
                other_employee_id = request.POST.get('other_employee')
                creator_share = Decimal(request.POST.get('creator_share'))
                partner_share = Decimal(request.POST.get('partner_share'))

                # Validate the sharing inputs.
                if not other_employee_id:
                    app.delete()  # Clean up the created application if validation fails.
                    raise ValueError("Please select an employee to share with.")

                if creator_share + partner_share != 100:
                    app.delete()
                    raise ValueError("Commission shares must add up to 100%.")

                # Create assignments for both employees.
                other_emp = Employee.objects.get(employee_id=other_employee_id)
                ApplicationAssignment.objects.create(application=app, employee=employee, commission_percentage=creator_share)
                ApplicationAssignment.objects.create(application=app, employee=other_emp, commission_percentage=partner_share)

            # If everything succeeds, show a success message and redirect.
            messages.success(request, f"Application '{app.application_name}' created successfully!")
            return redirect('applications')

        except (ValueError, TypeError, Employee.DoesNotExist) as e:
            # If any error occurs during creation, show an error message and redirect.
            messages.error(request, f"Error creating application: {e}")
            return redirect('applications')

    # --- STEP 3: PREPARE DATA FOR PAGE DISPLAY (GET REQUEST) ---
    # This block runs for GET requests or after a form submission redirects.
    today = timezone.localtime(timezone.now())

    # Get month and year from URL parameters for filtering, or use current month/year.
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))

    # Fetch all applications assigned to the current employee.
    your_applications = Application.objects.filter(assigned_employees=employee).order_by('-date_created').distinct()

    # Fetch approved assignments for the selected month/year to calculate commission.
    approved_assignments = ApplicationAssignment.objects.filter(
        employee=employee,
        application__approved=True,
        application__date_created__year=selected_year,
        application__date_created__month=selected_month
    ).select_related('application')

    # Calculate the total commission for the month.
    total_monthly_commission = 0
    for assignment in approved_assignments:
        commission_share = (assignment.commission_percentage / 100) * assignment.application.total_commission
        assignment.commission_share = commission_share # Attach the calculated share to the object for the template.
        total_monthly_commission += commission_share

    # Prepare context data for the template.
    other_employees = Employee.objects.exclude(employee_id=employee.employee_id)
    months = [{'value': i, 'display': timezone.datetime(2000, i, 1).strftime('%B')} for i in range(1, 13)]
    selected_month_display = months[selected_month - 1]['display']
    current_year = timezone.now().year
    years = list(range(current_year - 5, current_year + 2))

    # Bundle all data into the context dictionary.
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
    
    # Render the main applications page with the prepared context.
    return render(request, 'applications.html', context)


@require_employee
def application_detail_view(request, employee, pk):
    """
    Displays the details of a single application and handles the chat functionality.
    """
    # Ensure the logged-in employee is actually assigned to this application
    application = get_object_or_404(Application, pk=pk, assigned_employees=employee)
    
    # Check if the application is shared and not yet approved to enable chat
    is_shared = application.assigned_employees.count() > 1
    is_chat_active = is_shared and not application.approved

    # Handle chat message submission
    if request.method == 'POST' and is_chat_active:
        message_text = request.POST.get('message')
        message_file = request.FILES.get('file')
        
        if message_text or message_file:
            ChatMessage.objects.create(
                application=application,
                employee=employee,
                message=message_text,
                file=message_file
            )
            # Redirect to the same page to show the new message and clear the form
            return redirect('application-detail', pk=application.pk)

    # Fetch data for display
    assignments = application.applicationassignment_set.all().select_related('employee')
    chat_messages = []
    if is_chat_active:
        chat_messages = application.chat_messages.all().order_by('timestamp').select_related('employee')

    context = {
        'application': application,
        'assignments': assignments,
        'is_chat_active': is_chat_active,
        'chat_messages': chat_messages
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


def links_view(request):
    employee_id = request.session.get('employee_id')
    if employee_id:
        return render(request, 'links.html')
    else:
        return render(request, 'login.html')
    
# In your views.py file

from django.db.models import Q # Make sure to import Q for complex lookups

@require_employee
def worksheet_view(request, employee):
    department = employee.department
    if not department:
        messages.error(request, "You are not assigned to a department. Cannot access worksheet.")
        return redirect('employee_dashboard')

    form_map = {
        'Mee Seva': MeesevaWorksheetForm,
        'Online Hub': MeesevaWorksheetForm,
        'Aadhaar': AadharWorksheetForm,
        'Bhu Bharathi': BhuBharathiWorksheetForm,
        'xerox': XeroxWorksheetForm,
    }
    WorksheetForm = form_map.get(department.name)

    if not WorksheetForm:
        messages.error(request, f"No worksheet available for the '{department.name}' department.")
        return redirect('employee_dashboard')

    if request.method == 'POST':
        form = WorksheetForm(request.POST)
        if form.is_valid():
            worksheet_entry = form.save(commit=False)
            worksheet_entry.employee = employee
            worksheet_entry.department_name = department.name
            worksheet_entry.save()
            messages.success(request, "Worksheet entry added successfully.")
            return redirect('worksheet')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = WorksheetForm()

    today = timezone.now().date()
    
    # --- Today's Entries with DUAL totals ---
    todays_entries = Worksheet.objects.filter(employee=employee, date=today)
    todays_total_amount = todays_entries.aggregate(total=Sum('amount'))['total'] or 0
    # NEW: Calculate total for the 'payment' column
    todays_total_payment = todays_entries.aggregate(total=Sum('payment'))['total'] or 0

    # --- Historical Entries with NEW mobile filter ---
    all_entries = Worksheet.objects.filter(employee=employee)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    mobile_filter = request.GET.get('mobile_number') # Get the mobile number from the URL

    if start_date_str and end_date_str:
        all_entries = all_entries.filter(date__range=[start_date_str, end_date_str])
    
    # NEW: Apply the mobile number filter
    if mobile_filter:
        # Use Q objects to search in either customer_mobile OR login_mobile_no
        all_entries = all_entries.filter(
            Q(customer_mobile__icontains=mobile_filter) | 
            Q(login_mobile_no__icontains=mobile_filter)
        )
    
    context = {
        'employee': employee,
        'form': form,
        'department': department,
        'todays_entries': todays_entries,
        'todays_total_amount': todays_total_amount, # Changed name for clarity
        'todays_total_payment': todays_total_payment, # Pass new total to template
        'all_entries': all_entries.order_by('-date'), # Ensure consistent ordering
        'today': today,
    }
    return render(request, 'worksheet.html', context)


@require_employee
def worksheet_entry_edit_view(request, employee, entry_id):
    entry = get_object_or_404(Worksheet, pk=entry_id, employee=employee)

    if entry.approved:
        messages.error(request, "This entry is approved and cannot be edited.")
        return redirect('worksheet')

    # NEW: Use a separate, restricted form for editing
    if request.method == 'POST':
        # Pass the instance to the restricted form
        form = WorksheetEntryEditForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Certificate number updated successfully.")
            return redirect('worksheet')
        else:
            context = {'form': form, 'entry_id': entry_id}
            return render(request, 'partials/worksheet_edit_form.html', context)
    else:
        # Show the restricted form on GET request
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