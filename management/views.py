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
from .models import Employee,AttendanceSession,Order
from .forms import WorksheetParticularFormSet


def home(request):
    return render(request, "home.html")

def calender(request):
    return render(request, "calender.html")

def contact(request):
    return render(request, "contact.html")


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

def logout_view(request):
    employee_id = request.session.get('employee_id')
    if employee_id:
        try:
            employee = Employee.objects.get(employee_id=employee_id)
            active_session = AttendanceSession.objects.filter(employee=employee, logout_time__isnull=True).last()
            if active_session:
                active_session.logout_time = timezone.now()
                active_session.save()
        except Employee.DoesNotExist:
            pass

    request.session.flush()
    return redirect('login')


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
            # Send OTP to employee mobile
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
        elif request.session.get('otp_verified'):
            show_sensitive = True

    elif request.session.get('otp_verified'):
        show_sensitive = True

    context = {
        'employee': employee,
        'show_sensitive': show_sensitive,
        'otp_sent': otp_sent,
        'otp_verified': otp_verified,
        'messages': messages.get_messages(request)
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
    month = request.GET.get('month')
    year = request.GET.get('year')

    if not month:
        month = today.month
    else:
        month = int(month)
    if not year:
        year = today.year
    else:
        year = int(year)

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
        total_seconds = duration.total_seconds() if duration else 0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        duration_str = f"{hours}h {minutes}m"

        sessions_by_date[login_local.date()].append({
            'login_time': login_local,
            'logout_time': logout_local,
            'duration_str': duration_str,
        })

    todays_sessions_qs = AttendanceSession.objects.filter(
        employee=employee,
        login_time__date=today.date()
    ).order_by('login_time')

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
            'login_time': login_local,
            'logout_time': logout_local,
            'duration_str': duration_str,
        })

    months = [{'value': i, 'display': month_name[i]} for i in range(1, 13)]
    current_year = today.year
    years = [current_year - i for i in range(5)][::-1]

    selected_month_name = month_name[month]

    context = {
        'employee': employee,
        'sessions_by_date': dict(sessions_by_date),
        'todays_sessions': todays_sessions,
        'months': months,
        'years': years,
        'selected_month': month,
        'selected_year': year,
        'selected_month_name': selected_month_name,
        'today': today,
    }
    return render(request, 'attendance.html', context)
  


def employee_orders_view(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    month = request.GET.get('month')
    year = request.GET.get('year')
    today = datetime.today()
    if not month:
        month = today.month
    else:
        month = int(month)
    if not year:
        year = today.year
    else:
        year = int(year)

    orders = Order.objects.filter(
        assigned_employee__employee_id=employee_id,
        order_date__month=month,
        order_date__year=year
    ).order_by('-order_date')

    months = [{'value': i, 'display': month_name[i]} for i in range(1, 13)]
    years = [today.year - i for i in range(5)][::-1]  # Shows last 5 years

    context = {
        'orders': orders,
        'months': months,
        'years': years,
        'selected_month': month,
        'selected_year': year,
    }
    return render(request, 'orders.html', context)



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
    



def create_worksheet(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    employee = Employee.objects.get(employee_id=employee_id)

    if request.method == "POST":
        formset = WorksheetParticularFormSet(request.POST)
        if formset.is_valid():
            particulars = formset.cleaned_data
            total_amount = sum(item['amount'] for item in particulars if item and 'amount' in item)
            context = {
                'employee': employee,
                'date': timezone.now(),
                'particulars': particulars,
                'total_amount': total_amount,
            }
            return render(request, 'worksheet_print.html', context)
    else:
        formset = WorksheetParticularFormSet()

    return render(request, 'worksheet.html', {
        'employee': employee,
        'date': timezone.now(),
        'formset': formset,
    })
