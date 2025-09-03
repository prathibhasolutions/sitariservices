from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as django_login
from datetime import datetime
from django.utils import timezone
from calendar import month_name
from django.contrib.auth.hashers import check_password
from django.shortcuts import render, get_object_or_404
from .models import Invoice
from .forms import InvoiceForm, ParticularFormSet
from .utils import generate_otp, send_otp_whatsapp
from .models import Employee,Attendance,Order


def home(request):
    return render(request, "home.html")

def calender(request):
    return render(request, "calender.html")


def login_view(request):
    if request.method == 'POST':
        user_type = request.POST.get('user_type')
        username = request.POST.get('username')
        password = request.POST.get('password')

        if user_type == 'employee':
            try:
                employee = Employee.objects.get(mobile_number=username)
                if employee.password == password:  # For production, use hashing!
                    request.session['employee_id'] = employee.employee_id
                    return redirect('employee_dashboard')
                else:
                    messages.error(request, 'Invalid password.')
            except Employee.DoesNotExist:
                messages.error(request, 'Employee not found.')

        elif user_type == 'admin':
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_superuser:
                django_login(request, user)
                return redirect('/admin/')  # Django admin panel
            else:
                messages.error(request, 'Invalid admin credentials.')
        else:
            messages.error(request, 'Only employee or admin login is implemented here.')

    return render(request, 'login.html')


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

    if request.method == 'POST' and 'unlock_sensitive' in request.POST:
        password = request.POST.get('password')
        if password == employee.password:
            show_sensitive = True
        else:
            messages.error(request, "Invalid password.")

    context = {
        'employee': employee,
        'show_sensitive': show_sensitive,
        'messages': messages.get_messages(request)
    }
    return render(request, 'employee_dashboard.html', context)


def attendance_view(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    # Get current month/year, or filter if selected
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

    # Fetch employee's attendance records for this month
    attendance_records = Attendance.objects.filter(
        employee__employee_id=employee_id,
        date__year=year,
        date__month=month
    ).order_by('date')

    # Build months list for filter dropdown (Jan-Dec)
    months = [{'value': i, 'display': month_name[i]} for i in range(1, 13)]

    # Build years list for dropdown (e.g., last 5 years)
    current_year = today.year
    years = [current_year - i for i in range(5)][::-1]  # [2021, 2022, 2023, 2024, 2025]

    context = {
        'attendance_records': attendance_records,
        'months': months,
        'years': years,
        'selected_month': month,
        'selected_year': year,
    }
    return render(request, 'attendance.html', context)

def logout_view(request):
    # Destroys the session and logs out the user
    request.session.flush()
    return redirect('login_view')  


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


def change_password_view(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        try:
            employee = Employee.objects.get(employee_id=employee_id)
        except Employee.DoesNotExist:
            messages.error(request, "Employee not found.")
            return redirect('login')

        if employee.password != old_password:
            messages.error(request, "Old password is incorrect.")
        elif not new_password:
            messages.error(request, "New password cannot be empty.")
        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
        else:
            employee.password = new_password  # In production, hash the password!
            employee.save()
            messages.success(request, "Password changed successfully.")
            return redirect('change_password')

    return render(request, 'change_password.html')


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
    

def forgot_password(request):
    # Get the employee from session or user relation
    employee_id = request.session.get('employee_id')
    if not employee_id:
        # Not logged in or session expired
        return redirect('login')
    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        messages.error(request, "Invalid session.")
        return redirect('login')
    mobile = employee.mobile_number

    if request.method == "POST":
        otp = generate_otp()
        request.session['otp'] = otp
        request.session['mobile_number'] = mobile
        send_otp_whatsapp(mobile, otp)
        messages.success(request, "OTP sent to your WhatsApp number.")
        return redirect('verify_otp')
    # Pass the mobile to the template
    return render(request, "forgot_password.html", {"mobile": mobile})


def verify_otp(request):
    step = request.POST.get("step", "otp") if request.method == "POST" else "otp"
    if request.method == "POST":
        mobile = request.session.get('mobile_number')
        if not mobile:
            messages.error(request, "Session expired. Please start again.")
            return redirect('forgot_password')

        if step == "otp":
            entered_otp = request.POST.get("otp")
            otp = request.session.get("otp")
            if entered_otp == otp:
                request.session["otp_verified"] = True
            else:
                messages.error(request, "Invalid OTP.")
                return render(request, "verify_otp.html", {"step": "otp"})
        elif step == "password" or request.session.get("otp_verified", False):
            new_password = request.POST.get("new_password")
            confirm = request.POST.get("confirm_password")
            if new_password != confirm:
                messages.error(request, "Passwords do not match.")
                return render(request, "verify_otp.html", {"step": "password"})
            employee = Employee.objects.get(mobile_number=mobile)
            employee.password = new_password
            employee.save()
            # Clean up session
            request.session.flush()
            messages.success(request, "Password changed successfully.")
            return redirect('login_view')
    step = "password" if request.session.get("otp_verified", False) else "otp"
    return render(request, "verify_otp.html", {"step": step})