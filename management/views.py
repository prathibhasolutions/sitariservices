from django.shortcuts import render, redirect
from django.contrib import messages
from collections import defaultdict
from datetime import datetime,timedelta
from django.utils import timezone
from calendar import month_name
from django.shortcuts import render, get_object_or_404
from .models import Invoice
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

                    AttendanceSession.objects.create(
                        employee=employee,
                        login_time=timezone.now(),
                        logout_time=None
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
            active_session = AttendanceSession.objects.filter(employee=employee, logout_time__isnull=True).last()
            if active_session:
                active_session.logout_time = timezone.now()
                active_session.logout_reason = logout_reason if logout_reason else "No reason provided"
                active_session.save()
                # Create BreakSession from previous logout to current login
                prev_logout = AttendanceSession.objects.filter(
                    employee=employee, logout_time__lt=active_session.login_time).order_by('-logout_time').first()
                if prev_logout and prev_logout.logout_time:
                    BreakSession.objects.create(
                        employee=employee,
                        start_time=prev_logout.logout_time,
                        end_time=active_session.login_time,
                        logout_reason=prev_logout.logout_reason,
                        approved=False
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

    filtered_sessions = AttendanceSession.objects.filter(
        employee=employee,
        login_time__year=year,
        login_time__month=month
    ).order_by('login_time')

    sessions_by_date = defaultdict(list)
    for session in filtered_sessions:
        login_local = timezone.localtime(session.login_time)
        logout_local = timezone.localtime(session.logout_time) if session.logout_time else None
        duration = session.duration()
        total_seconds = duration.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        duration_str = f"{hours}h {minutes}m"
        sessions_by_date[login_local.date()].append({
            'login_time': login_local,
            'logout_time': logout_local,
            'duration_str': duration_str,
            'logout_reason': session.logout_reason,
        })

    # Break Sessions for same period
    break_sessions = BreakSession.objects.filter(
        employee=employee,
        start_time__year=year,
        start_time__month=month
    ).order_by('start_time')

    # Salary calculation for 25 working days x 8 hours/day
    attended_seconds = sum([session.duration().total_seconds() for session in filtered_sessions])
    approved_break_seconds = sum([bs.duration().total_seconds() for bs in break_sessions if bs.approved])
    total_work_seconds = attended_seconds + approved_break_seconds
    expected_seconds = 25 * 8 * 3600
    salary = float(employee.salary) * (total_work_seconds / expected_seconds) if expected_seconds else 0

    months = [{'value': i, 'display': month_name[i]} for i in range(1, 13)]
    current_year = today.year
    years = [current_year - i for i in range(5)][::-1]
    selected_month_name = month_name[month]

    # Today's active sessions
    todays_sessions_qs = AttendanceSession.objects.filter(employee=employee, login_time__date=today.date()).order_by('login_time')
    todays_sessions = []
    for session in todays_sessions_qs:
        login_local = timezone.localtime(session.login_time)
        logout_local = timezone.localtime(session.logout_time) if session.logout_time else None
        duration = session.duration()
        total_seconds = duration.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        duration_str = f"{hours}h {minutes}m"
        todays_sessions.append({
            'login_time': login_local,
            'logout_time': logout_local,
            'duration_str': duration_str,
            'logout_reason': session.logout_reason,
        })

    context = {
        'employee': employee,
        'sessions_by_date': dict(sessions_by_date),
        'break_sessions': break_sessions,
        'months': months,
        'years': years,
        'selected_month': month,
        'selected_year': year,
        'selected_month_name': selected_month_name,
        'today': today,
        'todays_sessions': todays_sessions,
        'calculated_salary': salary,
    }
    return render(request, 'attendance.html', context)


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
    



