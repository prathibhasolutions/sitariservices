from django.shortcuts import render, redirect
from django.contrib import messages
from collections import defaultdict
from datetime import datetime,timedelta
from django.utils import timezone
from calendar import month_name,monthrange
from django.shortcuts import render, get_object_or_404
from .models import Invoice
from django.http import JsonResponse
from .forms import InvoiceForm, ParticularFormSet
from .utils import generate_otp, send_otp_whatsapp
from .models import Employee,AttendanceSession, WorkOrder, Commission,BreakSession
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from datetime import datetime
from django.db.models import Count


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
    # Fetch all approved work orders for employee in given month and year
    work_orders = WorkOrder.objects.filter(
        approved=True,
        assigned_employees=employee,
        date_created__year=year,
        date_created__month=month,
    ).prefetch_related('assigned_employees')

    total_commission = 0.0
    for wo in work_orders:
        assignees = list(wo.assigned_employees.all())
        assignee_count = len(assignees) if assignees else 1
        if employee in assignees:
            share = float(wo.commission) / assignee_count
            total_commission += share
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

    show_sensitive = False
    otp_sent = False
    otp_verified = False

    if request.method == 'POST':
        if 'send_otp' in request.POST:
            from .utils import generate_otp, send_otp_whatsapp

            otp = generate_otp()
            request.session['emp_otp'] = otp
            send_otp_whatsapp(employee.mobile_number, otp)
            otp_sent = True
            messages.success(request, f"OTP sent to {employee.mobile_number}")
        elif 'verify_otp' in request.POST:
            entered_otp = request.POST.get('otp')
            expected_otp = request.session.get('emp_otp')
            if entered_otp == expected_otp:
                show_sensitive = True
                otp_verified = True
                request.session['otp_verified'] = True
                messages.success(request, "OTP verified. Sensitive data unlocked.")
            else:
                messages.error(request, "Invalid OTP. Please try again.")
        else:
            # In case of other POST forms, preserve show_sensitive if previously verified
            if request.session.get('otp_verified'):
                show_sensitive = True
    else:
        if request.session.get('otp_verified'):
            show_sensitive = True

    today = timezone.localtime(timezone.now())
    current_year = today.year
    current_month = today.month

    current_month_commission = calculate_employee_monthly_commission(employee, current_year, current_month)

    context = {
        'employee': employee,
        'show_sensitive': show_sensitive,
        'otp_sent': otp_sent,
        'otp_verified': otp_verified,
        'messages': messages.get_messages(request),
        'current_month_commission': current_month_commission,
    }
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


def get_logged_in_employee(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return None
    try:
        return Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        return None

def require_employee(view_func):
    def wrapped_view(request, *args, **kwargs):
        employee = get_logged_in_employee(request)
        if not employee:
            messages.error(request, "Employee not logged in.")
            return redirect('login')
        return view_func(request, employee, *args, **kwargs)
    return wrapped_view

@require_employee
def work_order_list_create_view(request, employee):
    # Month/Year filter for commissions
    today = timezone.localtime(timezone.now())
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))

    if request.method == 'POST':
        work_name = request.POST.get('work_name')
        customer_name = request.POST.get('customer_name')
        customer_mobile = request.POST.get('customer_mobile_number')
        description = request.POST.get('description')
        expected_days = int(request.POST.get('expected_days', 0))
        commission = request.POST.get('commission')
        assigned_type = request.POST.get('assigned_type')
        other_employee_id = request.POST.get('other_employee')

        if not (work_name and customer_name and customer_mobile and description and commission):
            messages.error(request, "Please fill all required fields.")
            return redirect('workorders')

        work_order = WorkOrder.objects.create(
            work_name=work_name,
            customer_name=customer_name,
            customer_mobile_number=customer_mobile,
            description=description,
            expected_days_to_complete=expected_days,
            commission=commission,
            approved=False,
        )
        work_order.assigned_employees.add(employee)

        if assigned_type == 'sharing' and other_employee_id:
            try:
                other_emp = Employee.objects.get(employee_id=other_employee_id)
                work_order.assigned_employees.add(other_emp)
            except Employee.DoesNotExist:
                messages.error(request, "Selected employee to share with does not exist.")
                work_order.delete()
                return redirect('workorders')

        messages.success(request, "Work Order created successfully!")
        return redirect('workorders')

    # Your work orders
    work_orders = WorkOrder.objects.filter(assigned_employees=employee).order_by('-date_created')

    # Approved work orders filtered by selected month/year
    approved_work_orders = WorkOrder.objects.filter(
        approved=True,
        assigned_employees=employee,
        date_created__year=selected_year,
        date_created__month=selected_month,
    ).order_by('date_created')

    # Calculate commission share for each approved work order
    for wo in approved_work_orders:
        count = wo.assigned_employees.count() or 1
        wo.commission_share = float(wo.commission) / count

    # Total commission sum for the employee in selected month
    total_commission = sum([wo.commission_share for wo in approved_work_orders])

    other_employees = Employee.objects.exclude(employee_id=employee.employee_id)

    months = [{'value': i, 'display': timezone.datetime(2000, i, 1).strftime('%B')} for i in range(1, 13)]
    years = [selected_year - i for i in range(5)][::-1]

    context = {
        'work_orders': work_orders,
        'approved_work_orders': approved_work_orders,
        'total_commission': total_commission,
        'other_employees': other_employees,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'months': months,
        'years': years,
    }
    return render(request, 'workorders.html', context)


@require_employee
def work_order_detail_view(request, employee, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk, assigned_employees=employee)
    return render(request, 'workorder_detail.html', {'work_order': work_order})






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
    



