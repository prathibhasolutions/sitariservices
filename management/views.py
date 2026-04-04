from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Sum
from .models import Department, DepartmentTopUp, DepartmentStock, Employee, ServiceType, Worksheet, Token
# --- Department Head: Top Up Page ---
@login_required
def department_topup_view(request):
    # Get logged-in employee
    try:
        employee = Employee.objects.get(pk=request.session.get('employee_id'))
    except Employee.DoesNotExist:
        from django.contrib import messages
        messages.error(request, "You are not recognized as an employee.")
        return redirect('employee_dashboard')

    # Get department where this employee is the current head
    department = Department.objects.filter(department_head=employee).first()
    if not department:
        from django.contrib import messages
        messages.error(request, "You are not the current head of any department.")
        return redirect('employee_dashboard')

    # Top-up history (all time)
    topups = DepartmentTopUp.objects.filter(department=department).order_by('-created_at')

    # Date filter for per-employee table
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()

    # Main table: selected-date transactions for this department
    all_transactions = Worksheet.objects.filter(
        department_name=department.name,
        date=selected_date,
    ).order_by('-created_at')

    # Employees in this department
    employees = Employee.objects.filter(department=department).order_by('name')

    # Forms department stock
    from datetime import date as date_cls
    is_forms_dept = department.name == 'Forms'
    stock_rows = []
    stock_date_str = request.GET.get('stock_date', '')
    try:
        stock_date = date_cls.fromisoformat(stock_date_str) if stock_date_str else timezone.localdate()
    except ValueError:
        stock_date = timezone.localdate()
    if is_forms_dept:
        dept_service_types = ServiceType.objects.filter(departments=department).order_by('name')
        for st in dept_service_types:
            stock_obj, _ = DepartmentStock.objects.get_or_create(
                department=department,
                service_type=st,
                defaults={'quantity': 0},
            )
            day_qs = Worksheet.objects.filter(
                department_name='Forms',
                service=st.name,
                date=stock_date,
            )
            used_count = day_qs.aggregate(total=Sum('stocks_used'))['total'] or 0
            total_amount = day_qs.aggregate(total=Sum('amount'))['total'] or 0
            remaining = max(0, stock_obj.quantity - used_count)
            price = stock_obj.price
            from decimal import Decimal
            total_cost = Decimal(str(stock_obj.quantity)) * price
            stock_rows.append({
                'name': st.name,
                'quantity': stock_obj.quantity,
                'price': price,
                'total_cost': total_cost,
                'used': used_count,
                'total_amount': total_amount,
                'remaining': remaining,
            })

    stock_totals = {
        'quantity': sum(r['quantity'] for r in stock_rows),
        'total_cost': sum(r['total_cost'] for r in stock_rows),
        'total_amount': sum(r['total_amount'] for r in stock_rows),
        'used': sum(r['used'] for r in stock_rows),
        'remaining': sum(r['remaining'] for r in stock_rows),
    } if stock_rows else None

    context = {
        'department': department,
        'topups': topups,
        'all_transactions': all_transactions,
        'employees': employees,
        'selected_date': selected_date,
        'is_forms_dept': is_forms_dept,
        'stock_rows': stock_rows,
        'stock_totals': stock_totals,
        'stock_date': stock_date.isoformat(),
    }
    return render(request, 'management/department_topup.html', context)
from django.contrib.auth.decorators import user_passes_test
from .models import Employee, EmployeeNextDayAvailability, Holiday
def admin_only(user):
    return user.is_active and user.is_superuser

# --- Admin: Leave Management Report ---
@user_passes_test(admin_only)
def admin_leave_management(request):
    from django.contrib import messages
    tomorrow = next_working_day(timezone.localdate())

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Holiday actions ────────────────────────────────────────
        if action == 'add_holiday':
            date_str = request.POST.get('holiday_date', '').strip()
            reason = request.POST.get('holiday_reason', '').strip()
            if date_str:
                try:
                    from datetime import date as _date
                    holiday_date = _date.fromisoformat(date_str)
                    Holiday.objects.get_or_create(date=holiday_date, defaults={'reason': reason})
                    messages.success(request, f"Holiday marked for {holiday_date}.")
                except ValueError:
                    messages.error(request, "Invalid date.")
            else:
                messages.error(request, "Please select a date.")
            return redirect('admin_leave_management')

        if action == 'delete_holiday':
            holiday_id = request.POST.get('holiday_id')
            Holiday.objects.filter(pk=holiday_id).delete()
            messages.success(request, "Holiday removed.")
            return redirect('admin_leave_management')

        # ── Employee availability action ───────────────────────────
        employee_id = request.POST.get('employee_id')
        will_come_value = request.POST.get('will_come')

        if employee_id and will_come_value in ('yes', 'no'):
            try:
                employee = Employee.objects.get(pk=employee_id)
                EmployeeNextDayAvailability.objects.update_or_create(
                    employee=employee,
                    target_date=tomorrow,
                    defaults={
                        'will_come': (will_come_value == 'yes'),
                        'response_source': EmployeeNextDayAvailability.RESPONSE_SOURCE_MANUAL,
                        'responded_at': timezone.now(),
                    }
                )
                messages.success(request, f"Updated response for {employee.name}.")
            except Employee.DoesNotExist:
                messages.error(request, "Employee not found.")
        else:
            messages.error(request, "Please choose Yes or No.")

        return redirect('admin_leave_management')

    employees = Employee.objects.all().order_by('name')
    records = []
    for emp in employees:
        record = EmployeeNextDayAvailability.objects.filter(employee=emp, target_date=tomorrow).order_by('-responded_at').first()
        records.append({
            'employee': emp,
            'availability': record,
        })

    from datetime import date as _date
    today = timezone.localdate()
    upcoming_holidays = Holiday.objects.filter(date__gte=today).order_by('date')

    ctx = admin.site.each_context(request)
    ctx.update({
        'records': records,
        'tomorrow': tomorrow,
        'upcoming_holidays': upcoming_holidays,
        'today_iso': today.isoformat(),
    })
    return render(request, 'admin_leave_management.html', ctx)


# --- Admin Dashboard ---
def _build_admin_dashboard_context():
    employees = Employee.objects.select_related('department').order_by('name')
    employee_data = [
        {
            'employee': emp,
            'is_active': emp.is_active(),
        }
        for emp in employees
    ]
    active_count = sum(1 for item in employee_data if item['is_active'])
    inactive_count = len(employee_data) - active_count

    departments_overview = []
    departments = Department.objects.select_related('department_head').order_by('name')
    for dept in departments:
        total_topup = dept.topups.aggregate(total=Sum('amount'))['total'] or 0
        departments_overview.append({
            'name': dept.name,
            'head_name': dept.department_head.name if dept.department_head else '-',
            'topup_balance': total_topup,
        })

    return {
        'employee_data': employee_data,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'total_count': len(employee_data),
        'departments_overview': departments_overview,
        'employees': employees,
        'departments': departments,
    }


def admin_dashboard(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return redirect('/admin/login/?next=/admin-dashboard/')
    from django.contrib import messages
    from django.urls import reverse
    from .models import Token, TokenChatMessage

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'send_admin_message':
            token_id = request.POST.get('chat_token_id')
            message_text = (request.POST.get('admin_message') or '').strip()
            chat_token = Token.objects.filter(pk=token_id).first()

            if not chat_token:
                messages.error(request, 'Selected token not found.')
                return redirect('admin_dashboard')

            if not message_text:
                messages.error(request, 'Message cannot be empty.')
            else:
                TokenChatMessage.objects.create(
                    token=chat_token,
                    sender=TokenChatMessage.SENDER_ADMIN,
                    message=message_text,
                )

            return redirect(f"{reverse('admin_dashboard')}?token={chat_token.token_no}")

    query = (request.GET.get('q') or '').strip()
    selected_token_no = (request.GET.get('token') or '').strip()

    tokens_qs = Token.objects.all().order_by('-created_at')
    if query:
        tokens_qs = tokens_qs.filter(
            Q(token_no__icontains=query)
            | Q(customer_name__icontains=query)
            | Q(cell_no__icontains=query)
        )

    selected_chat_token = None
    if selected_token_no:
        selected_chat_token = Token.objects.filter(token_no=selected_token_no).first()
    if not selected_chat_token:
        selected_chat_token = tokens_qs.first()

    selected_chat_messages = TokenChatMessage.objects.none()
    if selected_chat_token:
        selected_chat_messages = TokenChatMessage.objects.filter(token=selected_chat_token).order_by('created_at')

    base_context = _build_admin_dashboard_context()
    base_context.update({
        'sitari_chat_tokens': tokens_qs[:200],
        'sitari_chat_query': query,
        'selected_chat_token': selected_chat_token,
        'selected_chat_messages': selected_chat_messages,
    })
    return render(request, 'admin_dashboard.html', base_context)


WORKSHEET_FIELDS_BY_DEPARTMENT = {
    'mee seva': ['service', 'particulars', 'transaction_num', 'certificate_number', 'payment', 'amount'],
    'online hub': ['service', 'particulars', 'transaction_num', 'certificate_number', 'payment', 'amount'],
    'aadhaar': ['service', 'particulars', 'enrollment_no', 'certificate_number', 'payment', 'amount'],
    'bhu bharathi': ['login_mobile_no', 'application_no', 'status', 'payment', 'amount'],
    'forms': ['service', 'particulars', 'stocks_used', 'amount'],
    'xerox': ['service', 'particulars', 'payment', 'amount'],
    'notary and bonds': ['service', 'particulars', 'bonds_sno', 'payment', 'amount'],
}


def _normalize_department_name(name):
    return (name or '').strip().lower()


def _worksheet_fields_for_department(department_name):
    return WORKSHEET_FIELDS_BY_DEPARTMENT.get(_normalize_department_name(department_name), ['service', 'particulars', 'payment', 'amount'])


def _build_token_search_payload(token_obj, datetime_format):
    worksheet_obj = Worksheet.objects.filter(token_no=token_obj.token_no).order_by('-created_at').first()
    department_name = token_obj.department.name if token_obj.department else ''
    worksheet_fields = _worksheet_fields_for_department(department_name)

    worksheet_payload = {
        'exists': bool(worksheet_obj),
        'entry_id': worksheet_obj.id if worksheet_obj else None,
        'particulars_image_url': worksheet_obj.particulars_image.url if worksheet_obj and worksheet_obj.particulars_image else '',
        'field_names': worksheet_fields,
        'values': {},
    }
    if worksheet_obj:
        for field_name in worksheet_fields:
            raw_value = getattr(worksheet_obj, field_name, '')
            worksheet_payload['values'][field_name] = '' if raw_value is None else str(raw_value)

    return {
        'token_id': token_obj.id,
        'token_no': token_obj.token_no,
        'created_at': timezone.localtime(token_obj.created_at).strftime(datetime_format) if token_obj.created_at else '-',
        'customer_name': token_obj.customer_name or '-',
        'cell_no': token_obj.cell_no or '-',
        'department': token_obj.department.name if token_obj.department else '-',
        'department_id': token_obj.department_id,
        'service_type': token_obj.service_type.name if token_obj.service_type else '-',
        'service_type_id': token_obj.service_type_id,
        'operator_name': token_obj.operator_name.name if token_obj.operator_name else '-',
        'operator_id': token_obj.operator_name_id,
        'worksheet_saved': bool(worksheet_obj),
        'worksheet': worksheet_payload,
    }


def _update_linked_worksheet_from_payload(token_obj, worksheet_fields_payload):
    from decimal import Decimal

    worksheet_obj = Worksheet.objects.filter(token_no=token_obj.token_no).order_by('-created_at').first()
    if not worksheet_obj or not isinstance(worksheet_fields_payload, dict):
        return

    department_name = token_obj.department.name if token_obj.department else worksheet_obj.department_name
    editable_fields = _worksheet_fields_for_department(department_name)

    changed_fields = []
    for field_name in editable_fields:
        if field_name not in worksheet_fields_payload:
            continue

        incoming = worksheet_fields_payload.get(field_name)
        if field_name in ('payment', 'amount'):
            text_value = str(incoming or '').strip()
            incoming_value = Decimal(text_value or '0')
        elif field_name == 'stocks_used':
            text_value = str(incoming or '').strip()
            incoming_value = int(text_value or '1')
            if incoming_value < 1:
                incoming_value = 1
        else:
            incoming_value = str(incoming or '').strip()

        if getattr(worksheet_obj, field_name) != incoming_value:
            setattr(worksheet_obj, field_name, incoming_value)
            changed_fields.append(field_name)

    # Keep core customer details aligned with token edits.
    if worksheet_obj.customer_name != token_obj.customer_name:
        worksheet_obj.customer_name = token_obj.customer_name
        changed_fields.append('customer_name')
    if worksheet_obj.customer_mobile != token_obj.cell_no:
        worksheet_obj.customer_mobile = token_obj.cell_no
        changed_fields.append('customer_mobile')
    if token_obj.service_type and worksheet_obj.service != token_obj.service_type.name:
        worksheet_obj.service = token_obj.service_type.name
        changed_fields.append('service')
    if token_obj.department and worksheet_obj.department_name != token_obj.department.name:
        worksheet_obj.department_name = token_obj.department.name
        changed_fields.append('department_name')

    if changed_fields:
        worksheet_obj.save(update_fields=changed_fields)


def admin_token_search(request):
    from django.http import JsonResponse

    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    token_no = (request.GET.get('token_no') or '').strip()
    if not token_no:
        return JsonResponse({'error': 'Token number is required.'}, status=400)

    token = Token.objects.select_related('department', 'service_type', 'operator_name').filter(token_no=token_no).first()
    if not token:
        return JsonResponse({'error': 'Token not found.'}, status=404)

    return JsonResponse(_build_token_search_payload(token, '%d-%m-%Y %H:%M'))


def admin_token_update(request):
    import json
    from django.http import JsonResponse

    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    token_no = str(payload.get('token_no') or '').strip()
    customer_name = str(payload.get('customer_name') or '').strip()
    cell_no = str(payload.get('cell_no') or '').strip()
    department_id = payload.get('department_id')
    service_type_id = payload.get('service_type_id')
    operator_id = payload.get('operator_id')
    worksheet_fields_payload = payload.get('worksheet_fields')

    if not token_no:
        return JsonResponse({'error': 'Token number is required.'}, status=400)
    if not customer_name:
        return JsonResponse({'error': 'Customer name is required.'}, status=400)
    if not cell_no:
        return JsonResponse({'error': 'Cell number is required.'}, status=400)

    token = Token.objects.select_related('department', 'service_type', 'operator_name').filter(token_no=token_no).first()
    if not token:
        return JsonResponse({'error': 'Token not found.'}, status=404)

    department_obj = None
    if department_id not in (None, '', 'null'):
        department_obj = Department.objects.filter(pk=department_id).first()
        if not department_obj:
            return JsonResponse({'error': 'Invalid department.'}, status=400)

    service_type_obj = None
    if service_type_id not in (None, '', 'null'):
        service_type_obj = ServiceType.objects.filter(pk=service_type_id).first()
        if not service_type_obj:
            return JsonResponse({'error': 'Invalid service type.'}, status=400)
        if department_obj and not service_type_obj.departments.filter(pk=department_obj.pk).exists():
            return JsonResponse({'error': 'Selected service type does not belong to selected department.'}, status=400)

    operator_obj = None
    if operator_id not in (None, '', 'null'):
        operator_obj = Employee.objects.filter(employee_id=operator_id).first()
        if not operator_obj:
            return JsonResponse({'error': 'Invalid operator.'}, status=400)

    token.customer_name = customer_name
    token.cell_no = cell_no
    token.department = department_obj
    token.service_type = service_type_obj
    token.operator_name = operator_obj
    token.save(update_fields=['customer_name', 'cell_no', 'department', 'service_type', 'operator_name'])

    try:
        _update_linked_worksheet_from_payload(token, worksheet_fields_payload)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid worksheet field values.'}, status=400)

    return JsonResponse({
        'status': 'ok',
        'token': _build_token_search_payload(token, '%d-%m-%Y %H:%M'),
    })


def employee_token_search(request):
    from django.http import JsonResponse

    employee_id = request.session.get('employee_id')
    if not employee_id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    employee = Employee.objects.select_related('department').filter(employee_id=employee_id).first()
    if not employee:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    token_no = (request.GET.get('token_no') or '').strip()
    if not token_no:
        return JsonResponse({'error': 'Token number is required.'}, status=400)

    token = Token.objects.select_related('department', 'service_type', 'operator_name').filter(token_no=token_no).first()
    if not token:
        return JsonResponse({'error': 'Token not found.'}, status=404)

    is_service_linked_to_employee_department = False
    if employee.department_id and token.service_type_id:
        is_service_linked_to_employee_department = token.service_type.departments.filter(
            id=employee.department_id
        ).exists()

    if not is_service_linked_to_employee_department:
        return JsonResponse({'error': 'Access restricted'}, status=403)

    payload = _build_token_search_payload(token, '%d-%m-%Y %I:%M %p')
    payload['department_scope'] = 'Matched'
    return JsonResponse(payload)


def employee_token_update(request):
    import json
    from django.http import JsonResponse

    employee_id = request.session.get('employee_id')
    if not employee_id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    employee = Employee.objects.select_related('department').filter(employee_id=employee_id).first()
    if not employee:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    token_no = str(payload.get('token_no') or '').strip()
    customer_name = str(payload.get('customer_name') or '').strip()
    cell_no = str(payload.get('cell_no') or '').strip()
    worksheet_fields_payload = payload.get('worksheet_fields')

    if not token_no:
        return JsonResponse({'error': 'Token number is required.'}, status=400)
    if not customer_name:
        return JsonResponse({'error': 'Customer name is required.'}, status=400)
    if not cell_no:
        return JsonResponse({'error': 'Cell number is required.'}, status=400)

    token = Token.objects.select_related('department', 'service_type', 'operator_name').filter(token_no=token_no).first()
    if not token:
        return JsonResponse({'error': 'Token not found.'}, status=404)

    is_service_linked_to_employee_department = False
    if employee.department_id and token.service_type_id:
        is_service_linked_to_employee_department = token.service_type.departments.filter(
            id=employee.department_id
        ).exists()

    if not is_service_linked_to_employee_department:
        return JsonResponse({'error': 'Access restricted'}, status=403)

    token.customer_name = customer_name
    token.cell_no = cell_no
    token.save(update_fields=['customer_name', 'cell_no'])

    try:
        _update_linked_worksheet_from_payload(token, worksheet_fields_payload)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid worksheet field values.'}, status=400)

    token_payload = _build_token_search_payload(token, '%d-%m-%Y %I:%M %p')
    token_payload['department_scope'] = 'Matched'
    return JsonResponse({
        'status': 'ok',
        'token': token_payload,
    })


def employee_token_search_upload_image(request):
    import os
    import uuid
    from django.conf import settings as _settings

    employee_id = request.session.get('employee_id')
    if not employee_id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    employee = Employee.objects.filter(employee_id=employee_id).first()
    if not employee:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    worksheet_entry_id = (request.POST.get('worksheet_entry_id') or '').strip()
    particulars_image = request.FILES.get('particulars_image')

    if not worksheet_entry_id:
        return JsonResponse({'error': 'Worksheet entry is required.'}, status=400)
    if not particulars_image:
        return JsonResponse({'error': 'Please choose an image to upload.'}, status=400)

    worksheet_entry = Worksheet.objects.filter(pk=worksheet_entry_id, employee=employee).first()
    if not worksheet_entry:
        return JsonResponse({'error': 'Worksheet entry not found.'}, status=404)

    ext = os.path.splitext(particulars_image.name)[1].lower()
    uid = uuid.uuid4().hex[:8]
    entry_date = worksheet_entry.date or timezone.localdate()
    rel_path = f"worksheet_data/{entry_date}/{employee.employee_id}/particulars_{uid}{ext}"
    abs_dir = os.path.join(_settings.MEDIA_ROOT, 'worksheet_data', str(entry_date), str(employee.employee_id))
    os.makedirs(abs_dir, exist_ok=True)
    abs_path = os.path.join(_settings.MEDIA_ROOT, rel_path)
    particulars_image.seek(0)
    with open(abs_path, 'wb+') as dest:
        for chunk in particulars_image.chunks():
            dest.write(chunk)

    worksheet_entry.particulars_image = rel_path
    worksheet_entry.save(update_fields=['particulars_image'])

    token = Token.objects.select_related('department', 'service_type', 'operator_name').filter(token_no=worksheet_entry.token_no).first()
    if not token:
        return JsonResponse({'status': 'ok', 'message': 'Image uploaded successfully.'})

    payload = _build_token_search_payload(token, '%d-%m-%Y %I:%M %p')
    payload['department_scope'] = 'Matched'
    return JsonResponse({'status': 'ok', 'message': 'Image uploaded successfully.', 'token': payload})


@staff_member_required
def admin_token_search_upload_image(request):
    import os
    import uuid
    from django.conf import settings as _settings

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    worksheet_entry_id = (request.POST.get('worksheet_entry_id') or '').strip()
    particulars_image = request.FILES.get('particulars_image')

    if not worksheet_entry_id:
        return JsonResponse({'error': 'Worksheet entry is required.'}, status=400)
    if not particulars_image:
        return JsonResponse({'error': 'Please choose an image to upload.'}, status=400)

    worksheet_entry = Worksheet.objects.select_related('employee').filter(pk=worksheet_entry_id).first()
    if not worksheet_entry:
        return JsonResponse({'error': 'Worksheet entry not found.'}, status=404)

    ext = os.path.splitext(particulars_image.name)[1].lower()
    uid = uuid.uuid4().hex[:8]
    employee_id = worksheet_entry.employee_id or 'admin'
    entry_date = worksheet_entry.date or timezone.localdate()
    rel_path = f"worksheet_data/{entry_date}/{employee_id}/particulars_{uid}{ext}"
    abs_dir = os.path.join(_settings.MEDIA_ROOT, 'worksheet_data', str(entry_date), str(employee_id))
    os.makedirs(abs_dir, exist_ok=True)
    abs_path = os.path.join(_settings.MEDIA_ROOT, rel_path)
    particulars_image.seek(0)
    with open(abs_path, 'wb+') as dest:
        for chunk in particulars_image.chunks():
            dest.write(chunk)

    worksheet_entry.particulars_image = rel_path
    worksheet_entry.save(update_fields=['particulars_image'])

    token = Token.objects.select_related('department', 'service_type', 'operator_name').filter(token_no=worksheet_entry.token_no).first()
    if not token:
        return JsonResponse({'status': 'ok', 'message': 'Image uploaded successfully.'})

    payload = _build_token_search_payload(token, '%d-%m-%Y %H:%M')
    return JsonResponse({'status': 'ok', 'message': 'Image uploaded successfully.', 'token': payload})


@staff_member_required
def admin_upi_qr_single_view(request, entry_id):
    entry = get_object_or_404(Worksheet.objects.select_related('employee', 'employee__department'), pk=entry_id)
    employee = entry.employee

    total_amount_val = (entry.amount or 0) + (entry.payment or 0)
    remarks = entry.service or entry.particulars or 'Payment'
    upi_id = _resolve_upi_id_for_department(employee)
    upi_payee_name = 'Sainadha Associates'
    upi_url = _build_upi_payment_url(upi_id, upi_payee_name, total_amount_val, employee.name, remarks)
    qr_image_src = _build_qr_image_src(upi_url)

    context = {
        'employee': employee,
        'entry': entry,
        'upi_id': upi_id,
        'upi_payee_name': upi_payee_name,
        'total_amount': total_amount_val,
        'remarks': remarks,
        'upi_url': upi_url,
        'qr_image_src': qr_image_src,
        'is_single_entry': True,
    }
    return render(request, 'upi_qr.html', context)


def token_naming_form(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return redirect('/admin/login/?next=/admin/token-naming/')

    from django.contrib import messages
    from .forms import TokenNamingForm

    if request.method == 'POST':
        form = TokenNamingForm(request.POST)
        if form.is_valid():
            token = form.save()
            if request.POST.get('print_token') == '1':
                _save_token_to_worksheet(token)
                return redirect('token_print_view', token_id=token.id)
            messages.success(request, 'Token created successfully.')
            return redirect('token_naming_form')
        messages.error(request, 'Please fix the form errors and try again.')
    else:
        form = TokenNamingForm()

    recent_tokens = Token.objects.select_related(
        'department',
        'service_type',
        'operator_name',
    ).order_by('-created_at')[:100]

    return render(request, 'token_naming_form.html', {
        'form': form,
        'recent_tokens': recent_tokens,
    })


def employee_token_naming(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        request.session.flush()
        return redirect('login')

    if employee.locked or not employee.token_naming_access:
        return redirect('employee_dashboard')

    from .forms import TokenNamingForm

    def _build_employee_token_form(data=None):
        token_data = data.copy() if data is not None else None
        initial_data = {}

        if employee.department_id:
            initial_data['department'] = employee.department_id
            if token_data is not None:
                token_data['department'] = str(employee.department_id)

        form = TokenNamingForm(data=token_data, initial=initial_data)

        if employee.department_id and not (token_data and token_data.get('department')):
            form.fields['department'].initial = employee.department_id

        if (
            not (token_data and token_data.get('operator_name'))
            and form.fields['operator_name'].queryset.filter(employee_id=employee.employee_id).exists()
        ):
            form.fields['operator_name'].initial = employee.employee_id
        return form

    if request.method == 'POST':
        form = _build_employee_token_form(data=request.POST)
        if form.is_valid():
            token = form.save()
            if request.POST.get('print_token') == '1':
                _save_token_to_worksheet(token)
                return redirect('token_print_view', token_id=token.id)
            messages.success(request, 'Token created successfully.')
            return redirect('employee_token_naming')
        messages.error(request, 'Please fix token form errors and try again.')
    else:
        form = _build_employee_token_form()

    recent_tokens = Token.objects.select_related('department', 'service_type', 'operator_name').filter(
        operator_name=employee
    ).order_by('-created_at')[:100]

    from .models import Announcement
    active_announcements = Announcement.objects.filter(active=True).order_by('-created_at')
    is_department_head = bool(employee.department and employee.department.department_head_id == employee.employee_id)

    context = {
        'employee': employee,
        'active_announcements': active_announcements,
        'is_department_head': is_department_head,
        'token_form': form,
        'recent_tokens': recent_tokens,
        'has_token_naming_access': True,
    }
    return render(request, 'employee_token_naming.html', context)


def token_print_view(request, token_id):
    from django.core import signing
    from django.urls import reverse
    from urllib.parse import quote

    employee_id = request.session.get('employee_id')
    session_employee = Employee.objects.filter(employee_id=employee_id).first() if employee_id else None
    is_staff_user = request.user.is_authenticated and request.user.is_staff
    if not is_staff_user and not (session_employee and session_employee.token_naming_access):
        return redirect('/admin/login/?next=/admin/token-naming/')

    token = get_object_or_404(
        Token.objects.select_related('department', 'service_type', 'operator_name'),
        pk=token_id,
    )

    if not is_staff_user and token.operator_name_id != session_employee.employee_id:
        messages.error(request, 'You can only view tokens created by you.')
        return redirect('employee_dashboard')

    assistant_access_token = signing.dumps(
        {'token_id': token.id},
        salt='assistant-customer-link',
    )
    assistant_url = (
        request.build_absolute_uri(reverse('assistant'))
        + '?access='
        + quote(assistant_access_token, safe='')
    )
    assistant_qr_url = 'https://quickchart.io/qr?size=600&text=' + quote(assistant_url, safe='')

    worksheet_exists = _save_token_to_worksheet(token)
    return render(request, 'token_print.html', {
        'token': token,
        'worksheet_exists': worksheet_exists,
        'assistant_qr_url': assistant_qr_url,
    })


def _save_token_to_worksheet(token):
    """Create worksheet entry from token once; return True if it exists/was created."""
    if Worksheet.objects.filter(token_no=token.token_no).exists():
        return True

    if not token.operator_name:
        return False

    department_name = ''
    if token.operator_name.department:
        department_name = token.operator_name.department.name
    elif token.department:
        department_name = token.department.name

    if not department_name:
        return False

    # Keep particulars empty by default; user can fill department-specific notes explicitly.
    particulars = ''

    Worksheet.objects.create(
        employee=token.operator_name,
        department_name=department_name,
        token_no=token.token_no,
        customer_name=token.customer_name,
        customer_mobile=token.cell_no,
        service=(token.service_type.name if token.service_type else None),
        particulars=particulars,
    )
    return True


def get_department_services(request):
    is_staff_user = request.user.is_authenticated and request.user.is_staff
    employee_id = request.session.get('employee_id')
    session_employee = Employee.objects.filter(employee_id=employee_id).first() if employee_id else None
    has_employee_token_access = bool(session_employee and session_employee.token_naming_access)

    if not is_staff_user and not has_employee_token_access:
        return JsonResponse({'services': []}, status=403)

    department_id = request.GET.get('department_id')
    if not department_id:
        return JsonResponse({'services': []})

    services = ServiceType.objects.filter(departments__id=department_id).order_by('name')
    operators = (
        Employee.objects.filter(
            department_id=department_id,
            locked=False,
            attendance_sessions__logout_time__isnull=True,
            attendance_sessions__session_closed=False,
        )
        .distinct()
        .order_by('name')
    )
    return JsonResponse({
        'services': [{'id': item.id, 'name': item.name} for item in services],
        'operators': [{'id': item.employee_id, 'name': item.name} for item in operators],
    })


# --- Admin TTD Views ---
def admin_ttd_view(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return redirect('/admin/login/?next=/admin-dashboard/ttd/')
    groups = TTDGroupSeva.objects.prefetch_related('members').order_by('-created_at')
    individual_darshans = TTDIndividualDarshan.objects.order_by('-created_at')
    return render(request, 'admin_ttd.html', {
        'groups': groups,
        'individual_darshans': individual_darshans,
    })

def admin_ttd_group_print(request, group_id):
    if not (request.user.is_authenticated and request.user.is_staff):
        return redirect('/admin/login/')
    group_seva = get_object_or_404(TTDGroupSeva.objects.prefetch_related('members'), pk=group_id)
    return render(request, 'ttd_group_seva_print.html', {'group_seva': group_seva})

def admin_ttd_individual_print(request, darshan_id):
    if not (request.user.is_authenticated and request.user.is_staff):
        return redirect('/admin/login/')
    darshan = get_object_or_404(TTDIndividualDarshan, pk=darshan_id)
    return render(request, 'ttd_individual_darshan_print.html', {'darshan': darshan})

def admin_ttd_print_all(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return redirect('/admin/login/')
    group_sevas = TTDGroupSeva.objects.prefetch_related('members').order_by('planned_date', 'created_at')
    individual_darshans = TTDIndividualDarshan.objects.order_by('planned_date', 'slot_time')
    return render(request, 'ttd_print_all.html', {
        'group_sevas': group_sevas,
        'individual_darshans': individual_darshans,
    })


# --- Admin: Departments Section ---
@staff_member_required
def admin_departments(request):
    base_context = _build_admin_dashboard_context()
    base_context['departments'] = Department.objects.select_related('department_head').prefetch_related('employees').order_by('name')

    selected_department = None
    filtered_employee = None
    department_employees = Employee.objects.none()
    worksheet_entries = Worksheet.objects.none()
    report_headers = []
    report_rows = []
    total_amount = 0
    total_payment = 0
    department_report_headers = []
    department_report_rows = []
    department_total_amount = 0
    department_total_payment = 0

    department_id = request.GET.get('department_id')
    employee_id = request.GET.get('employee_id')
    from_date = (request.GET.get('from_date') or '').strip()
    to_date = (request.GET.get('to_date') or '').strip()
    department_from_date = (request.GET.get('department_from_date') or '').strip()
    department_to_date = (request.GET.get('department_to_date') or '').strip()
    print_today = request.GET.get('print_today') == '1'
    auto_print_department = request.GET.get('auto_print') == '1'

    if print_today and not (department_from_date or department_to_date):
        today = timezone.localdate().isoformat()
        department_from_date = today
        department_to_date = today

    if department_id:
        selected_department = Department.objects.filter(pk=department_id).select_related('department_head').first()
        if selected_department:
            department_employees = Employee.objects.filter(
                department=selected_department,
                locked=False,
            ).order_by('name')

    if selected_department and employee_id:
        filtered_employee = department_employees.filter(employee_id=employee_id).first()

    def _display(value):
        return '-' if value in (None, '') else str(value)

    def _money(value):
        return f"{value:.2f}" if value is not None else '0.00'

    def _get_department_columns(department_name):
        if department_name in ('Mee Seva', 'Online Hub'):
            return [
                ('Token No', lambda entry: _display(entry.token_no)),
                ('Customer Name', lambda entry: _display(entry.customer_name)),
                ('Customer Mobile', lambda entry: _display(entry.customer_mobile)),
                ('Service', lambda entry: _display(entry.service)),
                ('Particulars', lambda entry: _display(entry.particulars)),
                ('Transaction Num', lambda entry: _display(entry.transaction_num)),
                ('Certificate Num', lambda entry: _display(entry.certificate_number)),
                ('Payment', lambda entry: _money(entry.payment)),
                ('Amount', lambda entry: _money(entry.amount)),
            ]
        if department_name == 'Aadhaar':
            return [
                ('Token No', lambda entry: _display(entry.token_no)),
                ('Customer Name', lambda entry: _display(entry.customer_name)),
                ('Customer Mobile', lambda entry: _display(entry.customer_mobile)),
                ('Service', lambda entry: _display(entry.service)),
                ('Particulars', lambda entry: _display(entry.particulars)),
                ('Enrollment No', lambda entry: _display(entry.enrollment_no)),
                ('Certificate Num', lambda entry: _display(entry.certificate_number)),
                ('Payment', lambda entry: _money(entry.payment)),
                ('Amount', lambda entry: _money(entry.amount)),
            ]
        if department_name == 'Bhu Bharathi':
            return [
                ('Token No', lambda entry: _display(entry.token_no)),
                ('Customer Name', lambda entry: _display(entry.customer_name)),
                ('Login Mobile', lambda entry: _display(entry.login_mobile_no)),
                ('Application No', lambda entry: _display(entry.application_no)),
                ('Status', lambda entry: _display(entry.status)),
                ('Payment', lambda entry: _money(entry.payment)),
                ('Amount', lambda entry: _money(entry.amount)),
                ('Particulars', lambda entry: _display(entry.particulars)),
            ]
        if department_name == 'Forms':
            return [
                ('Token No', lambda entry: _display(entry.token_no)),
                ('Service', lambda entry: _display(entry.service)),
                ('Particulars', lambda entry: _display(entry.particulars)),
                ('Stocks Used', lambda entry: _display(entry.stocks_used)),
                ('Amount', lambda entry: _money(entry.amount)),
            ]
        if department_name == 'Xerox':
            return [
                ('Token No', lambda entry: _display(entry.token_no)),
                ('Customer Name', lambda entry: _display(entry.customer_name)),
                ('Mobile No.', lambda entry: _display(entry.customer_mobile)),
                ('Service', lambda entry: _display(entry.service)),
                ('Particulars', lambda entry: _display(entry.particulars)),
                ('Payment', lambda entry: _money(entry.payment)),
                ('Amount', lambda entry: _money(entry.amount)),
            ]
        if department_name == 'Notary and Bonds':
            return [
                ('Token No', lambda entry: _display(entry.token_no)),
                ('Customer Name', lambda entry: _display(entry.customer_name)),
                ('Service', lambda entry: _display(entry.service)),
                ('Particulars', lambda entry: _display(entry.particulars)),
                ('Bonds Sl. No', lambda entry: _display(entry.bonds_sno)),
                ('Payment', lambda entry: _money(entry.payment)),
                ('Amount', lambda entry: _money(entry.amount)),
            ]
        return [
            ('Service', lambda entry: _display(entry.service)),
            ('Particulars', lambda entry: _display(entry.particulars)),
            ('Payment', lambda entry: _money(entry.payment)),
            ('Amount', lambda entry: _money(entry.amount)),
        ]

    if selected_department and (department_from_date or department_to_date):
        department_entries = Worksheet.objects.filter(
            department_name=selected_department.name,
        ).select_related('employee').order_by('-date', '-created_at')

        if department_from_date and department_to_date:
            department_entries = department_entries.filter(date__range=[department_from_date, department_to_date])
        elif department_from_date:
            department_entries = department_entries.filter(date__gte=department_from_date)
        elif department_to_date:
            department_entries = department_entries.filter(date__lte=department_to_date)

        department_columns = _get_department_columns(selected_department.name)
        department_report_headers = ['Date', 'Employee'] + [header for header, _ in department_columns]
        department_report_rows = [
            [
                entry.date.strftime('%d-%m-%Y') if entry.date else '-',
                _display(entry.employee.name if entry.employee_id else '-'),
                *[extractor(entry) for _, extractor in department_columns],
            ]
            for entry in department_entries
        ]

        department_totals = department_entries.aggregate(total_amount=Sum('amount'), total_payment=Sum('payment'))
        department_total_amount = department_totals['total_amount'] or 0
        department_total_payment = department_totals['total_payment'] or 0

    if selected_department and filtered_employee and (from_date or to_date):
        worksheet_entries = Worksheet.objects.filter(
            employee=filtered_employee,
            department_name=selected_department.name,
        ).order_by('-date', '-created_at')

        if from_date and to_date:
            worksheet_entries = worksheet_entries.filter(date__range=[from_date, to_date])
        elif from_date:
            worksheet_entries = worksheet_entries.filter(date__gte=from_date)
        elif to_date:
            worksheet_entries = worksheet_entries.filter(date__lte=to_date)

        dynamic_columns = _get_department_columns(selected_department.name)

        report_headers = [header for header, _ in dynamic_columns]
        report_rows = [
            [
                *[extractor(entry) for _, extractor in dynamic_columns],
            ]
            for entry in worksheet_entries
        ]

        totals = worksheet_entries.aggregate(total_amount=Sum('amount'), total_payment=Sum('payment'))
        total_amount = totals['total_amount'] or 0
        total_payment = totals['total_payment'] or 0

    base_context.update({
        'selected_department': selected_department,
        'selected_employee': filtered_employee,
        'department_employees': department_employees,
        'department_report_headers': department_report_headers,
        'department_report_rows': department_report_rows,
        'department_total_amount': department_total_amount,
        'department_total_payment': department_total_payment,
        'department_filter_from_date': department_from_date,
        'department_filter_to_date': department_to_date,
        'auto_print_department': auto_print_department,
        'worksheet_report_headers': report_headers,
        'worksheet_report_rows': report_rows,
        'worksheet_total_amount': total_amount,
        'worksheet_total_payment': total_payment,
        'filter_from_date': from_date,
        'filter_to_date': to_date,
    })
    return render(request, 'admin_dashboard.html', base_context)


# --- Admin: Employees Section ---
@staff_member_required
def admin_employees(request):
    base_context = _build_admin_dashboard_context()
    employees = Employee.objects.select_related('department').order_by('name')
    active_employee_ids = set(
        AttendanceSession.objects.filter(logout_time__isnull=True, session_closed=False)
        .values_list('employee_id', flat=True)
    )
    selected_employee = None
    selected_employee_id = (request.GET.get('employee_id') or '').strip()
    if selected_employee_id.isdigit():
        selected_employee = employees.filter(employee_id=int(selected_employee_id)).first()
    if not selected_employee:
        selected_employee = employees.first()

    admin_change_url = None
    if selected_employee:
        admin_change_url = f"/admin/management/employee/{selected_employee.employee_id}/change/"

    base_context.update({
        'employees': employees,
        'active_employee_ids': active_employee_ids,
        'selected_employee': selected_employee,
        'admin_employee_change_url': admin_change_url,
    })
    return render(request, 'admin_dashboard.html', base_context)


@staff_member_required
def admin_employee_edit(request, employee_id):
    employee = get_object_or_404(Employee, employee_id=employee_id)
    return redirect(f"/admin/management/employee/{employee.employee_id}/change/")


from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from auditlog.models import LogEntry
from django.utils import timezone

# --- Admin Print Event Logging Endpoint ---
from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
@staff_member_required
def admin_print_event(request):
    """
    Log a print event in the audit log for the current admin user.
    """
    if request.method == 'POST' and request.user.is_authenticated:
        from django.contrib.auth import get_user_model
        from django.contrib.contenttypes.models import ContentType
        User = get_user_model()
        LogEntry.objects.create(
            actor=request.user,
            action=4,  # Custom action code for print event
            content_type=ContentType.objects.get_for_model(User),
            object_id=request.user.pk,
            object_repr='Admin Print Event',
            remote_addr=getattr(request, 'auditlog_ip', None),
            changes={'message': 'Admin triggered print (Ctrl+P or afterprint) in admin interface.'},
            timestamp=timezone.now(),
        )
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'forbidden'}, status=403)
from .models import TodoTask

from django.views.decorators.http import require_POST

def assign_task_to_self(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        messages.error(request, "Your session has expired. Please log in again.")
        return redirect('login')
    if request.method == 'POST':
        description = request.POST.get('description')
        due_time = request.POST.get('due_time')
        if not description or not due_time:
            messages.error(request, "Please provide both description and due time.")
            return redirect('assigned_tasks')
        try:
            employee = Employee.objects.get(employee_id=employee_id)
            TodoTask.objects.create(employee=employee, description=description, due_time=due_time)
            messages.success(request, "Task assigned to yourself successfully.")
        except Exception as e:
            messages.error(request, f"Could not assign task: {e}")
        return redirect('assigned_tasks')
    else:
        return redirect('assigned_tasks')

from django.views.decorators.csrf import csrf_exempt
from .models import AccessArea
from django.views.decorators.http import require_POST
import math
from django.conf import settings
from django.apps import apps

# Haversine formula to calculate distance between two lat/lng points in meters
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lon2 - lon1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

@csrf_exempt
@require_POST
def geofence_check(request):

    import logging
    logger = logging.getLogger(__name__)
    try:
        data = request.POST or request.json or {}
        lat = float(data.get('latitude'))
        lng = float(data.get('longitude'))
        logger.info(f"Geofence check received coordinates: lat={lat}, lng={lng}")
    except Exception as e:
        logger.error(f"Geofence check error parsing coordinates: {e}")
        return JsonResponse({'allowed': False, 'reason': 'Invalid coordinates'}, status=400)

    # Check if geofencing is enabled
    GeofenceSettings = apps.get_model('management', 'GeofenceSettings')
    enabled = True
    try:
        enabled = GeofenceSettings.objects.first().enabled
    except Exception:
        pass
    if not enabled:
        return JsonResponse({'allowed': True, 'reason': 'Geofencing disabled'})

    # Check if inside any active area
    for area in AccessArea.objects.filter(active=True):
        dist = haversine(lat, lng, area.latitude, area.longitude)
        logger.info(f"Comparing to area '{area.name}': center=({area.latitude},{area.longitude}), radius={area.radius_meters}, distance={dist}")
        if dist <= area.radius_meters:
            logger.info(f"User is within area: {area.name}")
            return JsonResponse({'allowed': True, 'reason': f'Within area: {area.name}'})
    logger.warning("User is out of all access areas.")
    return JsonResponse({'allowed': False, 'reason': 'You are out of the access area.'})
from django.views.decorators.csrf import csrf_exempt
# --- Session Refresh Endpoint ---
@csrf_exempt
def refresh_session(request):
    if request.method == "POST":
        employee_id = request.session.get('employee_id')
        if not employee_id:
            return JsonResponse({'status': 'not-logged-in'}, status=401)
        now = timezone.now()
        session = AttendanceSession.objects.filter(
            employee_id=employee_id,
            logout_time__isnull=True,
            session_closed=False
        ).order_by('-login_time').first()
        if session:
            session.session_expires_at = now + timedelta(minutes=60)
            session.refreshed_at = now
            session.session_status = "refreshed"
            session.save(update_fields=["session_expires_at", "refreshed_at", "session_status"])
            return JsonResponse({'status': 'refreshed', 'expires_at': session.session_expires_at})
        return JsonResponse({'status': 'no-active-session'}, status=404)
    return JsonResponse({'status': 'invalid-method'}, status=405)
from django.shortcuts import render, redirect
from django.contrib import messages
from collections import defaultdict
from datetime import datetime, timedelta, time
from django.utils import timezone
from calendar import month_name,monthrange
from django.shortcuts import render, get_object_or_404
from django.db import models
from .models import Invoice
from django.http import JsonResponse
from .forms import InvoiceForm, ParticularFormSet,WorksheetEntryEditForm
from .utils import generate_otp, send_otp_whatsapp, get_employee_next_day_alert_state, next_working_day
from .models import Employee,AttendanceSession, BreakSession, Application, ApplicationAssignment, ChatMessage, Commission,Worksheet
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from django.db.models import Sum
from .forms import MeesevaWorksheetForm, AadharWorksheetForm, BhuBharathiWorksheetForm, XeroxWorksheetForm
from .models import UserNotificationStatus,Notification
from django.db.models.signals import post_save
from django.dispatch import receiver


# Password-based employee login (replaces OTP login)
def home_view(request):
    from .models import ChatbotServiceTemplate

    template_options = list(
        ChatbotServiceTemplate.objects.filter(is_active=True)
        .exclude(service_name='')
        .order_by('sort_order', 'service_name')
        .values_list('service_name', flat=True)
    )
    return render(request, 'home.html', {'assistant_template_options': template_options})


def assistant_view(request):
    from django.core import signing
    from django.http import Http404
    from .models import ChatbotServiceTemplate, TokenChatMessage

    access_token = (request.GET.get('access') or '').strip()
    if not access_token:
        raise Http404('Assistant page is not public.')

    try:
        payload = signing.loads(
            access_token,
            salt='assistant-customer-link',
            max_age=60 * 60 * 24 * 30,
        )
    except signing.BadSignature:
        raise Http404('Invalid assistant link.')
    except signing.SignatureExpired:
        raise Http404('Assistant link expired.')

    token_id = payload.get('token_id')
    token = Token.objects.filter(pk=token_id).only('customer_name').first()
    if not token:
        raise Http404('Invalid customer token.')

    template_options = list(
        ChatbotServiceTemplate.objects.filter(is_active=True)
        .exclude(service_name='')
        .order_by('sort_order', 'service_name')
        .values_list('service_name', flat=True)
    )
    chat_messages = TokenChatMessage.objects.filter(token=token).order_by('created_at')
    last_chat_message = chat_messages.last()
    last_chat_date_label = ''
    if last_chat_message:
        last_chat_date_label = timezone.localtime(last_chat_message.created_at).strftime('%d/%m/%Y')

    return render(request, 'assistant.html', {
        'assistant_template_options': template_options,
        'assistant_customer_name': token.customer_name,
        'assistant_access_token': access_token,
        'assistant_chat_messages': chat_messages,
        'assistant_last_chat_date_label': last_chat_date_label,
    })


def contact_view(request):
    return render(request, 'contact.html')


def employee_login(request):
    from auditlog.models import LogEntry
    from django.contrib.contenttypes.models import ContentType
    if request.method == 'POST':
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        try:
            employee = Employee.objects.get(mobile_number=mobile)
        except Employee.DoesNotExist:
            messages.error(request, "Employee with this mobile number not found.")
            return render(request, 'login.html')

        if employee.locked:
            messages.error(request, "Your account is locked. Please contact the admin.")
            return render(request, 'login.html', {'mobile': mobile})

        if password == employee.password:
            request.session['employee_id'] = employee.employee_id
            now = timezone.now()

            # 1. Find and close any still-open AttendanceSession for this employee (single device enforcement)
            open_attendance_sessions = AttendanceSession.objects.filter(
                employee=employee,
                logout_time__isnull=True,
                session_closed=False
            )
            for old_session in open_attendance_sessions:
                old_session.logout_time = now
                old_session.logout_reason = "New Login Override (Logged in from another device)"
                old_session.session_closed = True
                old_session.session_status = "ended"
                old_session.save(update_fields=["logout_time", "logout_reason", "session_closed", "session_status"])

            # --- Audit log: login event (changes as dict for admin compatibility) ---
            LogEntry.objects.create(
                actor=request.user if request.user.is_authenticated else None,
                action=4,  # Custom action code for login event
                content_type=ContentType.objects.get_for_model(Employee),
                object_id=employee.pk,
                object_repr=str(employee),
                remote_addr=getattr(request, 'auditlog_ip', None),
                changes={'message': 'User login via password'},
            )

            # If a break session is still open (from idle/tab close/previous logout), end it NOW
            last_break = BreakSession.objects.filter(
                employee=employee,
                end_time__isnull=True
            ).order_by('-start_time').first()
            if last_break:
                last_break.end_time = now
                last_break.ended_by_login = True  # optional for tracking
                last_break.save()

            # Create a new attendance session for this login (60-min session)
            new_session = AttendanceSession.objects.create(
                employee=employee,
                login_time=now,
                logout_time=None,
                logout_reason="",
                session_closed=False,
                session_expires_at=now + timedelta(minutes=60),
                refreshed_at=now,
                session_status="active"
            )
            request.session['attendance_session_id'] = new_session.id

            return redirect('employee_dashboard')
        else:
            messages.error(request, "Incorrect password. Please try again.")
            return render(request, 'login.html', {'mobile': mobile})

    return render(request, 'login.html')




def change_password_request(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if old_password != employee.password:
            messages.error(request, "Old password is incorrect.")
            return render(request, 'change_password_request.html', {'employee': employee})

        if not new_password:
            messages.error(request, "New password cannot be empty.")
            return render(request, 'change_password_request.html', {'employee': employee})

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return render(request, 'change_password_request.html', {'employee': employee})

        employee.password = new_password
        employee.save()
        messages.success(request, "Password changed successfully! You can now use the new password.")
        return redirect('employee_dashboard')

    return render(request, 'change_password_request.html', {'employee': employee})


def change_password_verify(request):
    # This view is deprecated; redirect to change_password_request
    return redirect('change_password_request')



@csrf_exempt
def logout_view(request):
    from auditlog.models import LogEntry
    from django.contrib.contenttypes.models import ContentType
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

                # --- Audit log: logout event (changes as dict for admin compatibility) ---
                LogEntry.objects.create(
                    actor=request.user if request.user.is_authenticated else None,
                    action=4,  # Custom action code for logout event
                    content_type=ContentType.objects.get_for_model(Employee),
                    object_id=employee.pk,
                    object_repr=str(employee),
                    remote_addr=getattr(request, 'auditlog_ip', None),
                    changes={'message': f'User logout: {reason}'},
                )
                
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
from .forms import EmployeeProfilePictureForm
from .models import Employee, MeetingAttendance, TrainingBonus, PerformanceBonus, ExtraDaysBonus

def employee_dashboard(request):
    # 1. Authenticate Employee (Unchanged)
    employee_id = request.session.get('employee_id')
    if not employee_id:
        return redirect('login')

    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        request.session.flush()
        return redirect('login')

    has_token_naming_access = bool(employee.token_naming_access and not employee.locked)
    
    # 2. Handle Profile Picture Upload (Unchanged)
    if request.method == 'POST' and 'upload_profile_pic' in request.POST:
        form = EmployeeProfilePictureForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile picture updated successfully')
            return redirect('employee_dashboard')
    else:
        # This is for the GET request, initializes the form
        form = EmployeeProfilePictureForm(instance=employee)

    # 2.1. Initialize upload form
    upload_form = EmployeeUploadForm()
    
    # Handle Document Upload (NEW)
    if request.method == 'POST' and 'upload_document' in request.POST:
        upload_form = EmployeeUploadForm(request.POST, request.FILES)
        if upload_form.is_valid():
            document = upload_form.save(commit=False)
            document.employee = employee
            document.save()
            messages.success(request, 'Document uploaded successfully')
            return redirect('employee_dashboard')
        else:
            messages.error(request, 'Error uploading document. Please check the form.')

    # 3. Handle Password Unlock for Sensitive Data
    password_verified = request.session.get('password_verified', False)
    show_sensitive = password_verified

    if request.method == 'POST':
        if 'unlock_sensitive' in request.POST:
            entered_password = request.POST.get('unlock_password')
            if entered_password == employee.password:
                request.session['password_verified'] = True
                messages.success(request, "Password verified. Sensitive data unlocked.")
            else:
                messages.error(request, "Incorrect password. Please try again.")
            return redirect('employee_dashboard')

    # 4. Fetch Data for the Template
    # Fetches earnings totals using the updated get_current_month_earnings method
    earnings_data = {}
    if show_sensitive:
        earnings_data = employee.get_current_month_earnings()

    # --- UPDATED DATA FETCHING FOR BONUS LISTS ---
    now = timezone.now()
    # Fetch meetings attended (Unchanged)
    attended_meetings = MeetingAttendance.objects.filter(
        employee=employee,
        attended=True,
        meeting__date__year=now.year,
        meeting__date__month=now.month
    ).select_related('meeting').order_by('-meeting__date')

    # Fetch individual training bonuses for the month (NEW)
    attended_trainings = TrainingBonus.objects.filter(
        employee=employee, date__year=now.year, date__month=now.month
    ).order_by('-date')
    
    # Fetch individual performance bonuses for the month (NEW)
    performance_bonuses = PerformanceBonus.objects.filter(
        employee=employee, date__year=now.year, date__month=now.month
    ).order_by('-date')
    
    # Fetch individual extra days bonuses for the month (NEW)
    extra_days_bonuses = ExtraDaysBonus.objects.filter(
        employee=employee, date__year=now.year, date__month=now.month
    ).order_by('-date')

    # 5. Fetch all active announcements (if any)
    from .models import Announcement
    active_announcements = Announcement.objects.filter(active=True).order_by('-created_at')

    # 5. Build the Context Dictionary (Now includes new bonus lists and all announcements)
    is_department_head = False
    if employee.department and employee.department.department_head_id == employee.employee_id:
        is_department_head = True
    context = {
        'employee': employee,
        'show_sensitive': show_sensitive,
        'current_month_earnings': earnings_data,
        'upload_profile_form': form,
        'attended_meetings': attended_meetings,
        'attended_trainings': attended_trainings,
        'performance_bonuses': performance_bonuses,
        'extra_days_bonuses': extra_days_bonuses,
        'upload_form': upload_form,
        'active_announcements': active_announcements,
        'is_department_head': is_department_head,
        'has_token_naming_access': has_token_naming_access,
    }

    # 6. Perform Session Cleanup (Unchanged)
    if 'password_verified' in request.session:
        del request.session['password_verified']

    # 7. Render the Template
    return render(request, 'employee_dashboard.html', context)


# In views.py

# In views.py

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
    
    # ### START OF THE CRITICAL FIX ###

    # 1. Initialize variables to hold the values, preventing errors
    daily_summary, total_wage, max_daily_wage = [], Decimal('0.00'), Decimal('0.00')

    try:
        # 2. Correctly unpack the THREE values returned from the model method
        daily_summary, total_wage, max_daily_wage = employee.get_daily_attendance_summary(year, month)
    except Exception as e:
        messages.error(request, f"Could not calculate attendance summary: {e}")

    # 3. Find today's calculated wage from the summary
    todays_calculated_wage = Decimal('0.00')
    if month == today.month and year == today.year:
        for record in daily_summary:
            if record['date'].day == today.day:
                todays_calculated_wage = record['daily_wage']
                break
    
    # ### END OF THE CRITICAL FIX ###
    
    # --- The rest of the view remains the same ---
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
        'calculated_salary': total_wage, # This context variable might be legacy, but we'll keep it
        'days_in_month': monthrange(year, month)[1],
        'daily_working_hours': daily_working_hours,
        'expected_hours': monthrange(year, month)[1] * daily_working_hours,
        # The context now uses the correct values passed directly from the model
        'max_daily_wage': max_daily_wage,
        'todays_calculated_wage': todays_calculated_wage,
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


@require_employee
def submit_next_day_availability(request, employee):
    if request.method != 'POST':
        return redirect('employee_dashboard')

    state = get_employee_next_day_alert_state(employee)
    if not state['pending']:
        messages.error(request, 'Tomorrow availability confirmation is not pending right now.')
        return redirect(request.META.get('HTTP_REFERER') or 'employee_dashboard')

    decision = (request.POST.get('will_come') or '').strip().lower()
    if decision not in ('yes', 'no'):
        messages.error(request, 'Please choose Yes or No.')
        return redirect(request.META.get('HTTP_REFERER') or 'employee_dashboard')

    EmployeeNextDayAvailability.objects.update_or_create(
        employee=employee,
        target_date=state['target_date'],
        defaults={
            'will_come': decision == 'yes',
            'response_source': EmployeeNextDayAvailability.RESPONSE_SOURCE_MANUAL,
            'responded_at': timezone.now(),
        },
    )
    messages.success(request, 'Tomorrow availability saved successfully.')
    return redirect(request.META.get('HTTP_REFERER') or 'employee_dashboard')


@require_employee
def todays_absentees_view(request, employee):
    today = timezone.localdate()
    # On Saturday show Monday's absentees; any other day shows tomorrow's
    absentee_date = next_working_day(today)
    absentees = EmployeeNextDayAvailability.objects.filter(
        target_date=absentee_date,
        will_come=False,
    ).select_related('employee').order_by('employee__name')

    is_department_head = False
    if employee.department and employee.department.department_head_id == employee.employee_id:
        is_department_head = True

    context = {
        'employee': employee,
        'today': today,
        'absentee_date': absentee_date,
        'absentees': absentees,
        'is_department_head': is_department_head,
    }
    return render(request, 'todays_absentees.html', context)


def _resolve_upi_id_for_department(employee):
    dept_name = (employee.department.name if employee.department else '') or ''
    dept_name = dept_name.strip().lower()

    if dept_name == 'bhu bharathi':
        return 'sainadhassociates@sbi'
    if dept_name == 'online hub':
        return 'srimahallaxmicommunication@sbi'
    if dept_name == 'mee seva':
        return 'sitarirajuxeroxandonline@sbi'
    if dept_name == 'xerox':
        return '8179811603@sbi'
    return 'sainadhassociates@sbi'


def _build_upi_payment_url(upi_id, payee_name, amount, employee_name, remarks):
    from decimal import Decimal
    from urllib.parse import quote

    amount_text = f"{Decimal(str(amount)).quantize(Decimal('0.01'))}"
    # Keep note compact so QR generation remains fast and robust.
    raw_note = f"{employee_name} - {remarks} - {amount_text}"
    note = raw_note[:80]
    return (
        "upi://pay"
        f"?pa={quote(upi_id)}"
        f"&pn={quote(payee_name)}"
        f"&am={quote(amount_text)}"
        "&cu=INR"
        f"&tn={quote(note)}"
    )


def _build_qr_image_src(upi_url):
    from urllib.parse import quote
    try:
        import base64
        import importlib
        import io
        qrcode = importlib.import_module('qrcode')
        svg_module = importlib.import_module('qrcode.image.svg')
        SvgImage = getattr(svg_module, 'SvgImage')

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(upi_url)
        qr.make(fit=True)

        image = qr.make_image(image_factory=SvgImage)
        buffer = io.BytesIO()
        image.save(buffer)
        encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
        return f"data:image/svg+xml;base64,{encoded}"
    except Exception:
        return f"https://quickchart.io/qr?size=350&ecLevel=M&text={quote(upi_url)}"


@require_employee
def employee_upi_qr_view(request, employee):
    from django.utils import timezone
    from django.db.models import Sum
    
    today = timezone.now().date()
    
    # Get today's worksheet entries
    todays_entries = Worksheet.objects.filter(employee=employee, date=today)
    
    # Calculate total amount (amount + payment)
    total_stats = todays_entries.aggregate(
        total_amount=Sum('amount'),
        total_payment=Sum('payment')
    )
    
    total_amount_val = (total_stats['total_amount'] or 0) + (total_stats['total_payment'] or 0)
    
    # Get service types from today's entries
    services = list(set(todays_entries.values_list('service', flat=True).exclude(service__isnull=True).exclude(service__exact='')))
    remarks = ', '.join(filter(None, services[:3]))  # Limit to top 3 services
    upi_id = _resolve_upi_id_for_department(employee)
    remarks_text = remarks if remarks else 'Payment'
    upi_payee_name = 'Sainadha Associates'
    upi_url = _build_upi_payment_url(upi_id, upi_payee_name, total_amount_val, employee.name, remarks_text)
    qr_image_src = _build_qr_image_src(upi_url)
    
    context = {
        'employee': employee,
        'upi_id': upi_id,
        'upi_payee_name': upi_payee_name,
        'total_amount': total_amount_val,
        'remarks': remarks_text,
        'upi_url': upi_url,
        'qr_image_src': qr_image_src,
    }
    return render(request, 'upi_qr.html', context)

@require_employee
def employee_upi_qr_single_view(request, employee, entry_id):
    from django.utils import timezone
    entry = get_object_or_404(Worksheet, pk=entry_id, employee=employee)
    
    # Calculate amount for this entry (amount + payment)
    total_amount_val = (entry.amount or 0) + (entry.payment or 0)
    
    # Use service and remarks from this entry
    remarks = entry.service or entry.particulars or 'Payment'
    upi_id = _resolve_upi_id_for_department(employee)
    upi_payee_name = 'Sainadha Associates'
    upi_url = _build_upi_payment_url(upi_id, upi_payee_name, total_amount_val, employee.name, remarks)
    qr_image_src = _build_qr_image_src(upi_url)
    
    context = {
        'employee': employee,
        'entry': entry,
        'upi_id': upi_id,
        'upi_payee_name': upi_payee_name,
        'total_amount': total_amount_val,
        'remarks': remarks,
        'upi_url': upi_url,
        'qr_image_src': qr_image_src,
        'is_single_entry': True,
    }
    return render(request, 'upi_qr.html', context)

# --- Main Views ---

# management/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from .models import Application, ApplicationAssignment, Employee, ChatMessage,ServiceType

@require_employee
def application_list_create_view(request, employee):
    """
    Handles viewing and creating applications with UPDATED commission logic for 'Own' assignments.
    """
    if request.method == 'POST':
        # Password verification logic remains the same
        if 'verify_password' in request.POST:
            entered_password = request.POST.get('password')
            if entered_password == employee.password:
                pass # Fall through to the GET logic
            else:
                messages.error(request, "Incorrect password. Please try again.")
                return render(request, 'application_password_prompt.html', {'employee': employee})
        
        # Application creation logic
        else:
            try:
                service_type_id = request.POST.get('service_type')
                if not service_type_id:
                    raise ValueError("You must select a service type.")
                
                service_type = ServiceType.objects.get(id=service_type_id)
                total_commission = Decimal(request.POST.get('total_commission'))
                assign_type = request.POST.get('assign_type')
                expected_date = request.POST.get('expected_date_of_completion') or None

                # Create the Application instance first
                app = Application.objects.create(
                    service_type=service_type,
                    customer_name=request.POST.get('customer_name'),
                    customer_mobile_number=request.POST.get('customer_mobile_number'),
                    expected_date_of_completion=expected_date,
                    total_commission=total_commission,
                    approved=False
                )

                # --- COMMISSION ASSIGNMENT LOGIC ---
                if assign_type == 'own':
                    # --- NEW LOGIC FOR 'OWN' ASSIGNMENT ---
                    # The employee gets a commission based on the sum of the referee and partner percentages.
                    own_commission_percentage = service_type.referee_commission_percentage + service_type.partner_commission_percentage
                    own_commission_amount = (total_commission * (own_commission_percentage / Decimal('100.00'))).quantize(Decimal('0.01'))
                    
                    ApplicationAssignment.objects.create(
                        application=app, 
                        employee=employee, 
                        commission_amount=own_commission_amount
                    )

                elif assign_type == 'sharing':
                    # This logic remains the same, splitting commission based on the predefined percentages
                    other_employee_id = request.POST.get('other_employee')
                    if not other_employee_id:
                        app.delete() # Clean up created application if no partner is selected
                        raise ValueError("Please select an employee to share with.")
                    
                    other_emp = Employee.objects.get(employee_id=other_employee_id)
                    
                    referee_amount = (total_commission * (service_type.referee_commission_percentage / Decimal('100.00'))).quantize(Decimal('0.01'))
                    partner_amount = (total_commission * (service_type.partner_commission_percentage / Decimal('100.00'))).quantize(Decimal('0.01'))

                    ApplicationAssignment.objects.create(application=app, employee=employee, commission_amount=referee_amount)
                    ApplicationAssignment.objects.create(application=app, employee=other_emp, commission_amount=partner_amount)

                messages.success(request, f"Application for '{app.service_type.name}' created successfully!")
                return redirect('applications')

            except (ValueError, TypeError, Employee.DoesNotExist, ServiceType.DoesNotExist) as e:
                messages.error(request, f"Error creating application: {e}")
                return redirect('applications')

    # GET request or successful password verification
    if request.method == 'GET':
        return render(request, 'application_password_prompt.html', {'employee': employee})
    
    # This part runs after a successful password POST
    today = timezone.localtime(timezone.now())
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))

    your_applications = Application.objects.filter(assigned_employees=employee).select_related('service_type').order_by('-date_created').distinct()
    approved_assignments = ApplicationAssignment.objects.filter(
        employee=employee,
        application__approved=True,
        application__date_created__year=selected_year,
        application__date_created__month=selected_month
    ).select_related('application', 'application__service_type')
    
    total_monthly_commission = approved_assignments.aggregate(total=Sum('commission_amount'))['total'] or 0

    other_employees = Employee.objects.exclude(employee_id=employee.employee_id)
    service_types = ServiceType.objects.all()
    
    months = [{'value': i, 'display': timezone.datetime(2000, i, 1).strftime('%B')} for i in range(1, 13)]
    selected_month_display = months[selected_month - 1]['display']
    current_year = timezone.now().year
    years = list(range(current_year - 5, current_year + 2))

    context = {
        'applications': your_applications,
        'approved_assignments': approved_assignments,
        'total_commission': total_monthly_commission,
        'other_employees': other_employees,
        'service_types': service_types,
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
from .models import Employee, Worksheet, Department, ResourceRepairReport, DepartmentTopUp, DepartmentInventoryEntry, EmployeeNextDayAvailability
from .forms import (
    MeesevaWorksheetForm, AadharWorksheetForm, BhuBharathiWorksheetForm, 
    FormsWorksheetForm, XeroxWorksheetForm, NotaryAndBondsWorksheetForm, 
    WorksheetEntryEditForm, ResourceRepairForm
)




# In views.py

from django.db.models import Sum, Q
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from .forms import (
    MeesevaWorksheetForm, AadharWorksheetForm, BhuBharathiWorksheetForm, 
    FormsWorksheetForm, XeroxWorksheetForm, NotaryAndBondsWorksheetForm,
    ResourceRepairForm
)
from .models import Worksheet, ResourceRepairReport, Employee

from decimal import Decimal


def is_worksheet_entry_locked_now(employee=None, now_local=None, cutoff_hour=None, secondary_cutoff_hour=None):
    if now_local is None:
        now_local = timezone.localtime(timezone.now())
    if cutoff_hour is None:
        cutoff_hour = getattr(settings, 'WORKSHEET_ENTRY_CUTOFF_HOUR', 17)
    if secondary_cutoff_hour is None:
        secondary_cutoff_hour = getattr(settings, 'WORKSHEET_ENTRY_SECONDARY_CUTOFF_HOUR', 0)

    # Check if user has time-based permission override
    if employee and employee.worksheet_entry_force_unlock_until:
        # If current time is before the permission expiration, allow access
        if now_local < employee.worksheet_entry_force_unlock_until:
            return False
        # If permission has expired, clear it
        employee.worksheet_entry_force_unlock_until = None
        employee.save(update_fields=['worksheet_entry_force_unlock_until'])

    # Entries are locked at the evening cutoff and again at midnight hour.
    base_locked = now_local.hour >= cutoff_hour or now_local.hour == secondary_cutoff_hour
    return base_locked


def format_cutoff_time_label(cutoff_hour):
    hour_12 = ((cutoff_hour - 1) % 12) + 1
    am_pm = 'AM' if cutoff_hour < 12 else 'PM'
    return f"{hour_12}:00 {am_pm}"

def resolve_notary_bond_type(service_value):
    if not service_value:
        return None

    if hasattr(service_value, 'name'):
        service_text = service_value.name or ''
    else:
        service_text = str(service_value)

    normalized_text = ' '.join(service_text.split()).strip()
    return normalized_text or None


def _calc_commission(collection, target):
    """5% commission on amount up to target; 10% on any amount above target."""
    collection = Decimal(str(collection))
    target = Decimal(str(target)) if target else Decimal('0.00')
    if target <= 0:
        return (collection * Decimal('0.05')).quantize(Decimal('0.01'))
    below = min(collection, target)
    above = max(Decimal('0.00'), collection - target)
    return (below * Decimal('0.05') + above * Decimal('0.10')).quantize(Decimal('0.01'))

@require_employee
def worksheet_view(request, employee):
    department = employee.department
    if not department:
        messages.error(request, "You are not assigned to a department. Cannot access worksheet.")
        return redirect('employee_dashboard')

    now_local = timezone.localtime(timezone.now())
    worksheet_cutoff_hour = getattr(settings, 'WORKSHEET_ENTRY_CUTOFF_HOUR', 17)
    cutoff_time_label = format_cutoff_time_label(worksheet_cutoff_hour)
    worksheet_cutoff_at = now_local.replace(hour=worksheet_cutoff_hour, minute=0, second=0, microsecond=0)
    milliseconds_until_worksheet_cutoff = max(
        int((worksheet_cutoff_at - now_local).total_seconds() * 1000),
        0,
    )
    is_worksheet_entry_locked = is_worksheet_entry_locked_now(
        employee=employee,
        now_local=now_local,
        cutoff_hour=worksheet_cutoff_hour,
    )

    # --- Form Handling (No changes needed) ---
    form_map = {
        'Mee Seva': MeesevaWorksheetForm, 'Online Hub': MeesevaWorksheetForm, 'Aadhaar': AadharWorksheetForm, 
        'Bhu Bharathi': BhuBharathiWorksheetForm, 'Forms': FormsWorksheetForm, 
        'Xerox': XeroxWorksheetForm, 'Notary and Bonds': NotaryAndBondsWorksheetForm,
    }
    WorksheetForm = form_map.get(department.name)
    worksheet_form = WorksheetForm(employee=employee) if WorksheetForm else None
    today = timezone.localtime(timezone.now()).date()
    todays_repair_report = ResourceRepairReport.objects.filter(employee=employee, date=today).first()
    repair_form = None
    if not todays_repair_report:
        repair_form = ResourceRepairForm()

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        upload_image = request.POST.get('upload_image')
        if upload_image == '1':
            import uuid, os
            from django.conf import settings as _settings
            entry_id = request.POST.get('entry_id')
            try:
                entry = Worksheet.objects.get(pk=entry_id, employee=employee)
                if 'particulars_image' in request.FILES:
                    file_obj = request.FILES['particulars_image']
                    ext = os.path.splitext(file_obj.name)[1].lower()
                    uid = uuid.uuid4().hex[:8]
                    rel_path = f"worksheet_data/{today}/{employee.employee_id}/particulars_{uid}{ext}"
                    abs_dir = os.path.join(_settings.MEDIA_ROOT, 'worksheet_data', str(today), str(employee.employee_id))
                    os.makedirs(abs_dir, exist_ok=True)
                    abs_path = os.path.join(_settings.MEDIA_ROOT, rel_path)
                    file_obj.seek(0)
                    with open(abs_path, 'wb+') as dest:
                        for chunk in file_obj.chunks():
                            dest.write(chunk)
                    entry.particulars_image = rel_path
                    entry.save()
                    messages.success(request, 'Image uploaded successfully.')
            except Worksheet.DoesNotExist:
                messages.error(request, 'Entry not found.')
            return redirect('worksheet')
        if form_type == 'worksheet_entry' and WorksheetForm:
            if is_worksheet_entry_locked:
                messages.error(request, f"Daily worksheet entry is closed after {cutoff_time_label}.")
                return redirect('worksheet')
            worksheet_form = WorksheetForm(request.POST, request.FILES, employee=employee)
            if worksheet_form.is_valid():
                import uuid, os
                from django.conf import settings as _settings
                entry = worksheet_form.save(commit=False)
                entry.employee = employee
                entry.department_name = department.name

                def _save_worksheet_image(file_obj, field_label):
                    if not file_obj:
                        return None
                    ext = os.path.splitext(file_obj.name)[1].lower()
                    uid = uuid.uuid4().hex[:8]
                    rel_path = f"worksheet_data/{today}/{employee.employee_id}/{field_label}_{uid}{ext}"
                    abs_dir = os.path.join(_settings.MEDIA_ROOT, 'worksheet_data', str(today), str(employee.employee_id))
                    os.makedirs(abs_dir, exist_ok=True)
                    abs_path = os.path.join(_settings.MEDIA_ROOT, rel_path)
                    file_obj.seek(0)
                    with open(abs_path, 'wb+') as dest:
                        for chunk in file_obj.chunks():
                            dest.write(chunk)
                    return rel_path

                particulars_file = request.FILES.get('particulars_image')
                if particulars_file:
                    entry.particulars_image = _save_worksheet_image(particulars_file, 'particulars')

                entry.save()
                # Auto-deduct payment from department top-up (skip Notary and Bonds)
                if entry.payment and entry.payment > 0 and department.name != 'Notary and Bonds':
                    DepartmentTopUp.objects.create(
                        department=department,
                        amount=-entry.payment,
                        note=f"Auto-deducted: worksheet entry by {employee.name} on {entry.date}",
                    )
                # Auto-deduct bond inventory for Notary and Bonds
                if department.name == 'Notary and Bonds':
                    selected_service = worksheet_form.cleaned_data.get('service')
                    matched_bond = resolve_notary_bond_type(selected_service) or resolve_notary_bond_type(entry.service)
                    if matched_bond:
                        DepartmentInventoryEntry.objects.create(
                            department=department,
                            bond_type=matched_bond,
                            quantity=-1,
                            note=f"Auto-deducted: worksheet entry by {employee.name} on {entry.date} (service: {entry.service})",
                        )
                messages.success(request, "Worksheet entry added successfully.")
                return redirect('worksheet')
        elif form_type == 'repair_report':
            if not todays_repair_report:
                repair_form = ResourceRepairForm(request.POST)
                if repair_form.is_valid():
                    report = repair_form.save(commit=False); report.employee = employee; report.date = today; report.save()
                    messages.success(request, "Resource repair report submitted successfully.")
                    return redirect('worksheet')

    # --- Data Fetching (No changes needed) ---
    todays_entries = Worksheet.objects.filter(employee=employee, date=today)
    todays_total_amount = todays_entries.aggregate(total=Sum('amount'))['total'] or 0
    todays_total_payment = todays_entries.aggregate(total=Sum('payment'))['total'] or 0
    from .models import EmployeeTarget as _ET
    _today_target_obj = _ET.objects.filter(employee=employee, date=today).first()
    _today_target = (_today_target_obj.target_amount + _today_target_obj.carry_forward) if _today_target_obj else Decimal('0.00')
    todays_commission = _calc_commission(todays_total_amount, _today_target)
    
    all_entries = Worksheet.objects.none()
    start_date_str = (request.GET.get('start_date') or '').strip()
    end_date_str = (request.GET.get('end_date') or '').strip()
    mobile_filter = (request.GET.get('mobile_number') or '').strip()
    has_history_filters = bool(start_date_str or end_date_str or mobile_filter)
    if has_history_filters:
        all_entries = Worksheet.objects.filter(employee=employee)
        if start_date_str and end_date_str:
            all_entries = all_entries.filter(date__range=[start_date_str, end_date_str])
        elif start_date_str:
            all_entries = all_entries.filter(date__gte=start_date_str)
        elif end_date_str:
            all_entries = all_entries.filter(date__lte=end_date_str)
        if mobile_filter:
            all_entries = all_entries.filter(Q(customer_mobile__icontains=mobile_filter) | Q(login_mobile_no__icontains=mobile_filter))
    
    # ### START OF THE DEBUGGING FIX ###
    
    todays_attendance_wage = Decimal('0.00')
    max_daily_wage = Decimal('0.00')

    print("--- Starting Salary Calculation Debug ---")
    print(f"Employee: {employee.name}, Salary in DB: {employee.salary}")

    try:
        daily_summary, _, calculated_max_wage = employee.get_daily_attendance_summary(today.year, today.month)
        
        max_daily_wage = calculated_max_wage
        print(f"Calculated Max Daily Wage from model: {max_daily_wage}")

        for record in daily_summary:
            if record['date'] == today:
                todays_attendance_wage = record['daily_wage']
                break
        
        print(f"Found Today's Calculated Wage: {todays_attendance_wage}")

    except Exception as e:
        # THIS IS THE CRITICAL CHANGE: We now show the error on the screen.
        error_message = f"An error occurred during salary calculation: {e}"
        print(error_message) # Also print to console
        messages.error(request, error_message)
        
    print("--- Ending Salary Calculation Debug ---")
    
    # ### END OF THE DEBUGGING FIX ###

    # All attendance and break sessions for today (not just active), with duration_str for template
    raw_sessions = AttendanceSession.objects.filter(employee=employee, login_time__date=today).order_by('login_time')
    todays_sessions = []
    for session in raw_sessions:
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

    # For breaks, you can add similar logic if needed
    todays_breaks = BreakSession.objects.filter(employee=employee, start_time__date=today).order_by('start_time')

    context = {
        'employee': employee,
        'form': worksheet_form,
        'repair_form': repair_form,
        'department': department,
        'todays_entries': todays_entries,
        'todays_total_amount': todays_total_amount,
        'todays_total_payment': todays_total_payment,
        'todays_commission': todays_commission,
        'todays_repair_report': todays_repair_report,
        'all_entries': all_entries.order_by('-date'),
        'has_history_filters': has_history_filters,
        'today': today,
        'todays_attendance_wage': todays_attendance_wage,
        'max_daily_wage': max_daily_wage,
        'todays_sessions': todays_sessions,
        'todays_breaks': todays_breaks,
        'is_worksheet_entry_locked': is_worksheet_entry_locked,
        'milliseconds_until_worksheet_cutoff': milliseconds_until_worksheet_cutoff,
        'should_auto_lock_after_cutoff': not (employee.worksheet_entry_force_unlock_until and now_local < employee.worksheet_entry_force_unlock_until),
        'cutoff_time_label': cutoff_time_label,
    }
    return render(request, 'worksheet.html', context)


def _build_worksheet_management_context(now_local):
    today = now_local.date()
    cutoff_hour = getattr(settings, 'WORKSHEET_ENTRY_CUTOFF_HOUR', 17)
    cutoff_time_label = format_cutoff_time_label(cutoff_hour)

    employees = Employee.objects.select_related('department').filter(locked=False).order_by('name')

    todays_totals_map = {
        row['employee_id']: {
            'total_amount': row['total_amount'] or 0,
            'total_payment': row['total_payment'] or 0,
        }
        for row in Worksheet.objects.filter(date=today)
        .values('employee_id')
        .annotate(
            total_amount=models.Sum('amount'),
            total_payment=models.Sum('payment'),
        )
    }

    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    weekly_totals_map = {
        row['employee_id']: row['total_amount'] or Decimal('0.00')
        for row in Worksheet.objects.filter(date__gte=week_start, date__lte=today)
        .values('employee_id')
        .annotate(total_amount=models.Sum('amount'))
    }
    monthly_totals_map = {
        row['employee_id']: row['total_amount'] or Decimal('0.00')
        for row in Worksheet.objects.filter(date__gte=month_start, date__lte=today)
        .values('employee_id')
        .annotate(total_amount=models.Sum('amount'))
    }

    from .models import EmployeeTarget as _ET
    from django.db.models import F
    daily_targets_map = {
        t.employee_id: (t.target_amount + t.carry_forward).quantize(Decimal('0.01'))
        for t in _ET.objects.filter(date=today)
    }
    weekly_targets_map = {
        row['employee_id']: row['total_target'] or Decimal('0.00')
        for row in _ET.objects.filter(date__gte=week_start, date__lte=today)
        .values('employee_id')
        .annotate(total_target=models.Sum(F('target_amount') + F('carry_forward')))
    }
    monthly_targets_map = {
        row['employee_id']: row['total_target'] or Decimal('0.00')
        for row in _ET.objects.filter(date__gte=month_start, date__lte=today)
        .values('employee_id')
        .annotate(total_target=models.Sum(F('target_amount') + F('carry_forward')))
    }

    employee_rows = []
    for emp in employees:
        is_locked = is_worksheet_entry_locked_now(employee=emp, now_local=now_local, cutoff_hour=cutoff_hour)
        employee_totals = todays_totals_map.get(emp.employee_id, {})

        has_active_override = emp.worksheet_entry_force_unlock_until and now_local < emp.worksheet_entry_force_unlock_until

        weekly_amount = weekly_totals_map.get(emp.employee_id, Decimal('0.00'))
        monthly_amount = monthly_totals_map.get(emp.employee_id, Decimal('0.00'))
        weekly_target = weekly_targets_map.get(emp.employee_id, Decimal('0.00'))
        monthly_target = monthly_targets_map.get(emp.employee_id, Decimal('0.00'))

        employee_rows.append({
            'employee': emp,
            'worksheet_locked': is_locked,
            'has_active_override': has_active_override,
            'override_until': emp.worksheet_entry_force_unlock_until,
            'total_amount': employee_totals.get('total_amount', 0),
            'total_payment': employee_totals.get('total_payment', 0),
            'daily_target': daily_targets_map.get(emp.employee_id, Decimal('0.00')),
            'weekly_commission': _calc_commission(weekly_amount, weekly_target),
            'monthly_commission': _calc_commission(monthly_amount, monthly_target),
        })

    return {
        'employee_rows': employee_rows,
        'now_local': now_local,
        'today': today,
        'cutoff_hour': cutoff_hour,
        'cutoff_time_label': cutoff_time_label,
    }


@staff_member_required
def admin_worksheet_management(request):
    now_local = timezone.localtime(timezone.now())
    cutoff_hour = getattr(settings, 'WORKSHEET_ENTRY_CUTOFF_HOUR', 17)
    cutoff_time_label = format_cutoff_time_label(cutoff_hour)

    if request.method == 'POST' and request.POST.get('action') == 'toggle_entry_access':
        employee_id = request.POST.get('target_employee_id')
        target_employee = get_object_or_404(Employee, employee_id=employee_id)
        
        if target_employee.worksheet_entry_force_unlock_until is None:
            # Grant permission with expiration time based on current time
            if now_local.hour < cutoff_hour:
                # Before 5 PM: permission expires at 5 PM today
                expiration = now_local.replace(hour=cutoff_hour, minute=0, second=0, microsecond=0)
                msg = f"Worksheet entry override enabled for {target_employee.name} until {cutoff_time_label} today."
            else:
                # At/after 5 PM: permission expires at midnight tonight
                expiration = (now_local + timezone.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                msg = f"Worksheet entry override enabled for {target_employee.name} until midnight tonight."
            
            target_employee.worksheet_entry_force_unlock_until = expiration
            target_employee.save(update_fields=['worksheet_entry_force_unlock_until'])
            messages.success(request, msg)
        else:
            # Revoke permission
            target_employee.worksheet_entry_force_unlock_until = None
            target_employee.save(update_fields=['worksheet_entry_force_unlock_until'])
            messages.success(request, f'Worksheet entry override disabled for {target_employee.name}.')

        return redirect(request.path)

    context = _build_worksheet_management_context(now_local)
    admin_context = admin.site.each_context(request)
    admin_context.update(context)
    return render(request, 'admin/worksheet_management.html', admin_context)


@staff_member_required
def admin_dashboard_worksheet_management(request):
    now_local = timezone.localtime(timezone.now())
    cutoff_hour = getattr(settings, 'WORKSHEET_ENTRY_CUTOFF_HOUR', 17)
    cutoff_time_label = format_cutoff_time_label(cutoff_hour)
    selected_employee_id = (request.GET.get('employee_id') or '').strip()

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()

        if action == 'toggle_entry_access':
            employee_id = request.POST.get('target_employee_id')
            target_employee = get_object_or_404(Employee, employee_id=employee_id)

            if target_employee.worksheet_entry_force_unlock_until is None:
                if now_local.hour < cutoff_hour:
                    expiration = now_local.replace(hour=cutoff_hour, minute=0, second=0, microsecond=0)
                    msg = f"Worksheet entry override enabled for {target_employee.name} until {cutoff_time_label} today."
                else:
                    expiration = (now_local + timezone.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    msg = f"Worksheet entry override enabled for {target_employee.name} until midnight tonight."

                target_employee.worksheet_entry_force_unlock_until = expiration
                target_employee.save(update_fields=['worksheet_entry_force_unlock_until'])
                messages.success(request, msg)
            else:
                target_employee.worksheet_entry_force_unlock_until = None
                target_employee.save(update_fields=['worksheet_entry_force_unlock_until'])
                messages.success(request, f'Worksheet entry override disabled for {target_employee.name}.')

            if selected_employee_id.isdigit():
                return redirect(f"{request.path}?employee_id={selected_employee_id}")
            return redirect(request.path)

        if action == 'update_single_token_access':
            employee_id = request.POST.get('target_employee_id')
            target_employee = get_object_or_404(Employee, employee_id=employee_id)
            allow_token_generation = request.POST.get('token_naming_access') == '1'
            target_employee.token_naming_access = allow_token_generation
            target_employee.save(update_fields=['token_naming_access'])
            if allow_token_generation:
                messages.success(request, f"Token Generation access enabled for {target_employee.name}.")
            else:
                messages.success(request, f"Token Generation access disabled for {target_employee.name}.")

            if selected_employee_id.isdigit():
                return redirect(f"{request.path}?employee_id={selected_employee_id}")
            return redirect(request.path)

    base_context = _build_admin_dashboard_context()
    base_context.update(_build_worksheet_management_context(now_local))

    employees = Employee.objects.select_related('department').order_by('name')
    active_employee_ids = set(
        AttendanceSession.objects.filter(logout_time__isnull=True, session_closed=False)
        .values_list('employee_id', flat=True)
    )
    selected_employee = None
    if selected_employee_id.isdigit():
        selected_employee = employees.filter(employee_id=int(selected_employee_id)).first()

    base_context.update({
        'active_employee_ids': active_employee_ids,
        'selected_employee': selected_employee,
        'selected_employee_id': int(selected_employee_id) if selected_employee_id.isdigit() else None,
    })

    return render(request, 'admin_dashboard.html', base_context)


@staff_member_required
def admin_dashboard_leave_management(request):
    tomorrow = next_working_day(timezone.localdate())

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add_holiday':
            date_str = request.POST.get('holiday_date', '').strip()
            reason = request.POST.get('holiday_reason', '').strip()
            if date_str:
                try:
                    from datetime import date as _date
                    holiday_date = _date.fromisoformat(date_str)
                    Holiday.objects.get_or_create(date=holiday_date, defaults={'reason': reason})
                    messages.success(request, f"Holiday marked for {holiday_date}.")
                except ValueError:
                    messages.error(request, "Invalid date.")
            else:
                messages.error(request, "Please select a date.")
            return redirect('admin_dashboard_leave_management')

        if action == 'delete_holiday':
            holiday_id = request.POST.get('holiday_id')
            Holiday.objects.filter(pk=holiday_id).delete()
            messages.success(request, "Holiday removed.")
            return redirect('admin_dashboard_leave_management')

        employee_id = request.POST.get('employee_id')
        will_come_value = request.POST.get('will_come')

        if employee_id and will_come_value in ('yes', 'no'):
            try:
                employee = Employee.objects.get(pk=employee_id)
                EmployeeNextDayAvailability.objects.update_or_create(
                    employee=employee,
                    target_date=tomorrow,
                    defaults={
                        'will_come': (will_come_value == 'yes'),
                        'response_source': EmployeeNextDayAvailability.RESPONSE_SOURCE_MANUAL,
                        'responded_at': timezone.now(),
                    }
                )
                messages.success(request, f"Updated response for {employee.name}.")
            except Employee.DoesNotExist:
                messages.error(request, "Employee not found.")
        else:
            messages.error(request, "Please choose Yes or No.")

        return redirect('admin_dashboard_leave_management')

    employees = Employee.objects.all().order_by('name')
    records = []
    for emp in employees:
        record = EmployeeNextDayAvailability.objects.filter(employee=emp, target_date=tomorrow).order_by('-responded_at').first()
        records.append({
            'employee': emp,
            'availability': record,
        })

    today = timezone.localdate()
    upcoming_holidays = Holiday.objects.filter(date__gte=today).order_by('date')

    base_context = _build_admin_dashboard_context()
    base_context.update({
        'records': records,
        'tomorrow': tomorrow,
        'upcoming_holidays': upcoming_holidays,
        'today_iso': today.isoformat(),
    })
    return render(request, 'admin_dashboard.html', base_context)


@staff_member_required
def admin_dashboard_targets(request):
    from .models import EmployeeTarget
    now_local = timezone.localtime(timezone.now())
    today = now_local.date()
    yesterday = today - timedelta(days=1)

    employees = Employee.objects.select_related('department').order_by('department__name', 'name')

    if request.method == 'POST':
        for emp in employees:
            key = f'target_{emp.employee_id}'
            raw = request.POST.get(key, '').strip()
            if raw == '':
                continue
            try:
                amount = Decimal(raw).quantize(Decimal('0.01'))
            except Exception:
                continue
            EmployeeTarget.objects.update_or_create(
                employee=emp,
                date=today,
                defaults={'target_amount': amount},
            )
        messages.success(request, f"Targets saved for {today.strftime('%d %b %Y')}.")
        return redirect('admin_dashboard_targets')

    yesterday_targets = {
        t.employee_id: t
        for t in EmployeeTarget.objects.filter(date=yesterday)
    }
    yesterday_collections = {
        row['employee_id']: row['total_amount'] or Decimal('0.00')
        for row in Worksheet.objects.filter(date=yesterday)
        .values('employee_id')
        .annotate(total_amount=models.Sum('amount'))
    }

    for emp in employees:
        yest_entry = yesterday_targets.get(emp.employee_id)
        if yest_entry:
            yest_effective = yest_entry.target_amount + yest_entry.carry_forward
            yest_collection = yesterday_collections.get(emp.employee_id, Decimal('0.00'))
            shortfall = max(Decimal('0.00'), (yest_effective - yest_collection).quantize(Decimal('0.01')))
            prev_target = yest_entry.target_amount
        else:
            shortfall = Decimal('0.00')
            prev_target = Decimal('0.00')

        EmployeeTarget.objects.update_or_create(
            employee=emp,
            date=today,
            create_defaults={'target_amount': prev_target, 'carry_forward': shortfall},
            defaults={'carry_forward': shortfall},
        )

    today_target_objs = {
        t.employee_id: t
        for t in EmployeeTarget.objects.filter(date=today)
    }

    today_actuals_map = {
        row['employee_id']: row['total_amount'] or Decimal('0.00')
        for row in Worksheet.objects.filter(date=today)
        .values('employee_id')
        .annotate(total_amount=models.Sum('amount'))
    }

    rows = []
    for emp in employees:
        obj = today_target_objs.get(emp.employee_id)
        target = obj.target_amount if obj else Decimal('0.00')
        carry_forward = obj.carry_forward if obj else Decimal('0.00')
        effective_target = target + carry_forward
        collection = today_actuals_map.get(emp.employee_id, Decimal('0.00'))
        balance = (effective_target - collection).quantize(Decimal('0.01'))
        achieved = collection >= effective_target if effective_target > 0 else None
        rows.append({
            'employee': emp,
            'target': target,
            'carry_forward': carry_forward,
            'effective_target': effective_target,
            'collection': collection,
            'balance': balance,
            'achieved': achieved,
        })

    base_context = _build_admin_dashboard_context()
    base_context.update({
        'rows': rows,
        'today': today,
    })
    return render(request, 'admin_dashboard.html', base_context)


@staff_member_required
def admin_dashboard_worksheet_data(request):
    import os
    from django.conf import settings as _settings

    worksheet_data_root = os.path.join(_settings.MEDIA_ROOT, 'worksheet_data')
    media_url_base = _settings.MEDIA_URL.rstrip('/')
    tree = []

    if os.path.isdir(worksheet_data_root):
        date_folders = sorted(
            [d for d in os.listdir(worksheet_data_root)
             if os.path.isdir(os.path.join(worksheet_data_root, d))],
            reverse=True
        )

        emp_map = {str(e.employee_id): e.name for e in Employee.objects.all()}

        for date_str in date_folders:
            date_path = os.path.join(worksheet_data_root, date_str)
            emp_entries = []
            emp_folders = sorted(
                [e for e in os.listdir(date_path)
                 if os.path.isdir(os.path.join(date_path, e))]
            )
            for emp_id in emp_folders:
                emp_path = os.path.join(date_path, emp_id)
                files = []
                for fname in sorted(os.listdir(emp_path)):
                    fpath = os.path.join(emp_path, fname)
                    if os.path.isfile(fpath):
                        rel = f"worksheet_data/{date_str}/{emp_id}/{fname}"
                        url = f"{media_url_base}/{rel}"
                        size_kb = round(os.path.getsize(fpath) / 1024, 1)
                        ext = os.path.splitext(fname)[1].lower()
                        is_image = ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
                        files.append({'name': fname, 'url': url, 'size_kb': size_kb, 'is_image': is_image})
                emp_entries.append({
                    'emp_id': emp_id,
                    'emp_name': emp_map.get(emp_id, emp_id),
                    'files': files,
                    'file_count': len(files),
                })
            total_files = sum(e['file_count'] for e in emp_entries)
            tree.append({'date': date_str, 'emp_entries': emp_entries, 'total_files': total_files})

    base_context = _build_admin_dashboard_context()
    base_context.update({'tree': tree})
    return render(request, 'admin_dashboard.html', base_context)


@staff_member_required
def admin_dashboard_managed_links(request):
    from django.core.exceptions import ValidationError
    from django.core.validators import URLValidator
    from .models import ManagedLink

    validator = URLValidator()

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        description = (request.POST.get('description') or '').strip()
        url = (request.POST.get('url') or '').strip()

        if action == 'add':
            if not description or not url:
                messages.error(request, 'Description and URL are required.')
            else:
                try:
                    validator(url)
                    ManagedLink.objects.create(description=description, url=url)
                    messages.success(request, 'Managed link added successfully.')
                except ValidationError:
                    messages.error(request, 'Please enter a valid URL (example: https://example.com).')

        elif action == 'edit':
            link_id = request.POST.get('link_id')
            link = ManagedLink.objects.filter(pk=link_id).first()
            if not link:
                messages.error(request, 'Managed link not found.')
            elif not description or not url:
                messages.error(request, 'Description and URL are required.')
            else:
                try:
                    validator(url)
                    link.description = description
                    link.url = url
                    link.save(update_fields=['description', 'url'])
                    messages.success(request, 'Managed link updated successfully.')
                except ValidationError:
                    messages.error(request, 'Please enter a valid URL (example: https://example.com).')

        elif action == 'delete':
            link_id = request.POST.get('link_id')
            deleted_count, _ = ManagedLink.objects.filter(pk=link_id).delete()
            if deleted_count:
                messages.success(request, 'Managed link deleted successfully.')
            else:
                messages.error(request, 'Managed link not found.')

        return redirect('admin_dashboard_managed_links')

    query = (request.GET.get('q') or '').strip()
    managed_links = ManagedLink.objects.all().order_by('description')
    if query:
        managed_links = managed_links.filter(Q(description__icontains=query) | Q(url__icontains=query))

    base_context = _build_admin_dashboard_context()
    base_context.update({
        'managed_links': managed_links,
        'managed_links_query': query,
    })
    return render(request, 'admin_dashboard.html', base_context)


@staff_member_required
def admin_dashboard_stocks_management(request):
    from datetime import date as date_cls
    from decimal import Decimal
    from django.urls import reverse
    from .models import DepartmentInventoryEntry

    forms_department = Department.objects.filter(name='Forms').first()
    notary_bonds_department = Department.objects.filter(name='Notary and Bonds').first()

    stock_date_str = (request.GET.get('stock_date') or '').strip()
    try:
        stock_date = date_cls.fromisoformat(stock_date_str) if stock_date_str else timezone.localdate()
    except ValueError:
        stock_date = timezone.localdate()

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()

        if action == 'update_forms_stock':
            if not forms_department:
                messages.error(request, 'Forms department not found.')
                return redirect('admin_dashboard_stocks_management')

            forms_services = ServiceType.objects.filter(departments=forms_department).order_by('name')
            errors = []

            for service_type in forms_services:
                raw_qty = (request.POST.get(f'stock_qty_{service_type.pk}') or '').strip()
                raw_price = (request.POST.get(f'stock_price_{service_type.pk}') or '').strip()

                try:
                    quantity = int(raw_qty)
                    if quantity < 0:
                        raise ValueError
                except ValueError:
                    errors.append(f"Invalid quantity for '{service_type.name}'.")
                    continue

                try:
                    price = Decimal(raw_price) if raw_price else Decimal('0')
                    if price < 0:
                        raise ValueError
                except Exception:
                    errors.append(f"Invalid price for '{service_type.name}'.")
                    continue

                DepartmentStock.objects.update_or_create(
                    department=forms_department,
                    service_type=service_type,
                    defaults={'quantity': quantity, 'price': price},
                )

            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, 'Forms stock updated successfully.')

            selected_stock_date = (request.POST.get('stock_date') or '').strip()
            if selected_stock_date:
                return redirect(f"{reverse('admin_dashboard_stocks_management')}?stock_date={selected_stock_date}")
            return redirect('admin_dashboard_stocks_management')

        if action == 'add_notary_inventory':
            if not notary_bonds_department:
                messages.error(request, 'Notary and Bonds department not found.')
                return redirect('admin_dashboard_stocks_management')

            bond_type = (request.POST.get('bond_type') or '').strip()
            raw_qty = (request.POST.get('inventory_quantity') or '').strip()
            note = (request.POST.get('inventory_note') or '').strip()

            valid_types = list(
                ServiceType.objects.filter(departments=notary_bonds_department)
                .order_by('name')
                .values_list('name', flat=True)
            )

            if not valid_types:
                messages.error(request, 'Please add service types to Notary and Bonds before adding inventory.')
                return redirect('admin_dashboard_stocks_management')

            if bond_type not in set(valid_types):
                messages.error(request, 'Please select a valid bond type.')
                return redirect('admin_dashboard_stocks_management')

            try:
                quantity = int(raw_qty)
                if quantity <= 0:
                    raise ValueError
            except ValueError:
                messages.error(request, 'Please enter a valid inventory quantity greater than 0.')
                return redirect('admin_dashboard_stocks_management')

            DepartmentInventoryEntry.objects.create(
                department=notary_bonds_department,
                bond_type=bond_type,
                quantity=quantity,
                note=note or None,
            )
            messages.success(request, 'Notary inventory added successfully.')
            return redirect('admin_dashboard_stocks_management')

    forms_stock_rows = []
    forms_stock_totals = None
    if forms_department:
        forms_services = ServiceType.objects.filter(departments=forms_department).order_by('name')
        for service_type in forms_services:
            stock_obj, _ = DepartmentStock.objects.get_or_create(
                department=forms_department,
                service_type=service_type,
                defaults={'quantity': 0, 'price': service_type.amount},
            )
            day_qs = Worksheet.objects.filter(
                department_name='Forms',
                service=service_type.name,
                date=stock_date,
            )
            used_count = day_qs.aggregate(total=Sum('stocks_used'))['total'] or 0
            total_amount = day_qs.aggregate(total=Sum('amount'))['total'] or 0
            remaining = max(0, stock_obj.quantity - used_count)
            total_cost = Decimal(str(stock_obj.quantity)) * stock_obj.price

            forms_stock_rows.append({
                'service_type_id': service_type.pk,
                'name': service_type.name,
                'quantity': stock_obj.quantity,
                'price': stock_obj.price,
                'total_cost': total_cost,
                'used': used_count,
                'remaining': remaining,
                'total_amount': total_amount,
            })

        if forms_stock_rows:
            forms_stock_totals = {
                'quantity': sum(row['quantity'] for row in forms_stock_rows),
                'total_cost': sum(row['total_cost'] for row in forms_stock_rows),
                'used': sum(row['used'] for row in forms_stock_rows),
                'remaining': sum(row['remaining'] for row in forms_stock_rows),
                'total_amount': sum(row['total_amount'] for row in forms_stock_rows),
            }

    notary_inventory_balance_rows = []
    notary_bond_type_options = []
    notary_inventory_history = []
    if notary_bonds_department:
        notary_bond_type_options = list(
            ServiceType.objects.filter(departments=notary_bonds_department)
            .order_by('name')
            .values_list('name', flat=True)
        )
        totals_by_type = {
            row['bond_type']: (row['total'] or 0)
            for row in DepartmentInventoryEntry.objects.filter(department=notary_bonds_department)
            .values('bond_type')
            .annotate(total=Sum('quantity'))
        }

        seen_types = set()
        for bond_type_name in notary_bond_type_options:
            notary_inventory_balance_rows.append({
                'name': bond_type_name,
                'total': totals_by_type.get(bond_type_name, 0),
            })
            seen_types.add(bond_type_name)

        for legacy_type in sorted(totals_by_type.keys()):
            if legacy_type not in seen_types:
                notary_inventory_balance_rows.append({
                    'name': legacy_type,
                    'total': totals_by_type.get(legacy_type, 0),
                })

        notary_inventory_history = DepartmentInventoryEntry.objects.filter(
            department=notary_bonds_department
        ).order_by('-created_at')[:30]

    base_context = _build_admin_dashboard_context()
    base_context.update({
        'forms_department': forms_department,
        'forms_stock_date': stock_date.isoformat(),
        'forms_stock_rows': forms_stock_rows,
        'forms_stock_totals': forms_stock_totals,
        'notary_department': notary_bonds_department,
        'notary_inventory_balance_rows': notary_inventory_balance_rows,
        'notary_bond_type_options': notary_bond_type_options,
        'notary_inventory_history': notary_inventory_history,
    })
    return render(request, 'admin_dashboard.html', base_context)


@staff_member_required
def admin_dashboard_chatbot(request):
    from .models import ChatbotServiceTemplate, ChatbotNumericTrigger

    def _is_checked(value):
        return str(value).lower() in ('1', 'true', 'on', 'yes')

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()

        if action == 'load_trial_data':
            trial_templates = [
                {
                    'service_name': 'MeeSeva Services',
                    'keywords': 'meeseva,certificate,income certificate,caste certificate',
                    'template_text': 'We provide MeeSeva services including income, caste, nativity and other certificate applications with fast processing support.',
                    'sort_order': 10,
                },
                {
                    'service_name': 'Aadhaar Services',
                    'keywords': 'aadhaar,uid,update aadhaar,mobile update',
                    'template_text': 'For Aadhaar services, we assist with mobile update, demographic corrections, and new enrollment guidance as per availability.',
                    'sort_order': 20,
                },
                {
                    'service_name': 'PAN and Tax Services',
                    'keywords': 'pan,pan card,tax,itr',
                    'template_text': 'We support PAN card application, correction, and basic tax filing assistance. Please carry valid ID and address proof.',
                    'sort_order': 30,
                },
                {
                    'service_name': 'Bill Payments',
                    'keywords': 'bill,current bill,electricity,water bill,recharge',
                    'template_text': 'You can pay electricity, water, and other utility bills at our center. Please share your consumer number for quick service.',
                    'sort_order': 40,
                },
                {
                    'service_name': 'Travel and Booking',
                    'keywords': 'ticket,booking,travel,bus,train,flight',
                    'template_text': 'We help with bus, train, and flight booking support depending on slot and provider availability.',
                    'sort_order': 50,
                },
            ]

            created = 0
            skipped = 0
            for item in trial_templates:
                obj, was_created = ChatbotServiceTemplate.objects.get_or_create(
                    service_name=item['service_name'],
                    defaults={
                        'keywords': item['keywords'],
                        'template_text': item['template_text'],
                        'sort_order': item['sort_order'],
                        'is_active': True,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

            messages.success(
                request,
                f'Trial data loaded. Templates -> Created: {created}, Skipped: {skipped}.',
            )
            return redirect('admin_dashboard_chatbot')

        if action == 'add_trigger':
            trigger_number = (request.POST.get('trigger_number') or '').strip()
            response_text = (request.POST.get('trigger_response_text') or '').strip()
            trigger_sort_order_raw = (request.POST.get('trigger_sort_order') or '100').strip()
            trigger_pdf = request.FILES.get('trigger_response_pdf')

            try:
                trigger_sort_order = int(trigger_sort_order_raw)
            except ValueError:
                trigger_sort_order = 100

            trigger_is_active = _is_checked(request.POST.get('trigger_is_active', '1'))

            if not trigger_number.isdigit():
                messages.error(request, 'Trigger must be numeric only.')
            elif not response_text:
                messages.error(request, 'Trigger response text is required.')
            elif ChatbotNumericTrigger.objects.filter(trigger_number=trigger_number).exists():
                messages.error(request, 'This trigger number already exists.')
            else:
                ChatbotNumericTrigger.objects.create(
                    trigger_number=trigger_number,
                    response_text=response_text,
                    response_pdf=trigger_pdf,
                    sort_order=trigger_sort_order,
                    is_active=trigger_is_active,
                )
                messages.success(request, 'Numeric trigger added successfully.')
            return redirect('admin_dashboard_chatbot')

        if action == 'edit_trigger':
            trigger_id = request.POST.get('trigger_id')
            trigger_obj = ChatbotNumericTrigger.objects.filter(pk=trigger_id).first()
            trigger_number = (request.POST.get('trigger_number') or '').strip()
            response_text = (request.POST.get('trigger_response_text') or '').strip()
            trigger_sort_order_raw = (request.POST.get('trigger_sort_order') or '100').strip()
            trigger_pdf = request.FILES.get('trigger_response_pdf')

            try:
                trigger_sort_order = int(trigger_sort_order_raw)
            except ValueError:
                trigger_sort_order = 100

            trigger_is_active = _is_checked(request.POST.get('trigger_is_active', '1'))

            if not trigger_obj:
                messages.error(request, 'Numeric trigger not found.')
            elif not trigger_number.isdigit():
                messages.error(request, 'Trigger must be numeric only.')
            elif not response_text:
                messages.error(request, 'Trigger response text is required.')
            elif ChatbotNumericTrigger.objects.filter(trigger_number=trigger_number).exclude(pk=trigger_obj.pk).exists():
                messages.error(request, 'Another trigger already uses this number.')
            else:
                trigger_obj.trigger_number = trigger_number
                trigger_obj.response_text = response_text
                trigger_obj.sort_order = trigger_sort_order
                trigger_obj.is_active = trigger_is_active
                if trigger_pdf:
                    trigger_obj.response_pdf = trigger_pdf
                trigger_obj.save(
                    update_fields=['trigger_number', 'response_text', 'response_pdf', 'sort_order', 'is_active', 'updated_at']
                )
                messages.success(request, 'Numeric trigger updated successfully.')
            return redirect('admin_dashboard_chatbot')

        if action == 'delete_trigger':
            trigger_id = request.POST.get('trigger_id')
            deleted_count, _ = ChatbotNumericTrigger.objects.filter(pk=trigger_id).delete()
            if deleted_count:
                messages.success(request, 'Numeric trigger deleted successfully.')
            else:
                messages.error(request, 'Numeric trigger not found.')
            return redirect('admin_dashboard_chatbot')

        service_name = (request.POST.get('service_name') or '').strip()
        keywords = (request.POST.get('keywords') or '').strip()
        template_text = (request.POST.get('template_text') or '').strip()
        sort_order_raw = (request.POST.get('sort_order') or '100').strip()

        try:
            sort_order = int(sort_order_raw)
        except ValueError:
            sort_order = 100

        is_active = _is_checked(request.POST.get('is_active', '0'))

        if action == 'add':
            if not service_name or not template_text:
                messages.error(request, 'Service name and template text are required.')
            elif ChatbotServiceTemplate.objects.filter(service_name__iexact=service_name).exists():
                messages.error(request, 'A template with this service name already exists.')
            else:
                ChatbotServiceTemplate.objects.create(
                    service_name=service_name,
                    keywords=keywords,
                    template_text=template_text,
                    sort_order=sort_order,
                    is_active=is_active,
                )
                messages.success(request, 'Chatbot template added successfully.')
            return redirect('admin_dashboard_chatbot')

        if action == 'edit':
            template_id = request.POST.get('template_id')
            template_obj = ChatbotServiceTemplate.objects.filter(pk=template_id).first()
            if not template_obj:
                messages.error(request, 'Template not found.')
            elif not service_name or not template_text:
                messages.error(request, 'Service name and template text are required.')
            elif ChatbotServiceTemplate.objects.filter(service_name__iexact=service_name).exclude(pk=template_obj.pk).exists():
                messages.error(request, 'Another template already uses this service name.')
            else:
                template_obj.service_name = service_name
                template_obj.keywords = keywords
                template_obj.template_text = template_text
                template_obj.sort_order = sort_order
                template_obj.is_active = is_active
                template_obj.save(update_fields=['service_name', 'keywords', 'template_text', 'sort_order', 'is_active', 'updated_at'])
                messages.success(request, 'Chatbot template updated successfully.')
            return redirect('admin_dashboard_chatbot')

        if action == 'delete':
            template_id = request.POST.get('template_id')
            deleted_count, _ = ChatbotServiceTemplate.objects.filter(pk=template_id).delete()
            if deleted_count:
                messages.success(request, 'Chatbot template deleted successfully.')
            else:
                messages.error(request, 'Template not found.')
            return redirect('admin_dashboard_chatbot')

    query = (request.GET.get('q') or '').strip()
    templates_qs = ChatbotServiceTemplate.objects.all().order_by('sort_order', 'service_name')
    if query:
        templates_qs = templates_qs.filter(
            Q(service_name__icontains=query)
            | Q(keywords__icontains=query)
            | Q(template_text__icontains=query)
        )

    base_context = _build_admin_dashboard_context()
    base_context.update({
        'chatbot_templates': templates_qs,
        'chatbot_query': query,
        'chatbot_numeric_triggers': ChatbotNumericTrigger.objects.all().order_by('sort_order', 'trigger_number'),
    })
    return render(request, 'admin_dashboard.html', base_context)


@staff_member_required
def admin_dashboard_sitari_chat(request):
    from .models import Token, TokenChatMessage
    from django.urls import reverse

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'send_admin_message':
            token_id = request.POST.get('chat_token_id')
            message_text = (request.POST.get('admin_message') or '').strip()
            chat_token = Token.objects.filter(pk=token_id).first()

            if not chat_token:
                messages.error(request, 'Selected token not found.')
                return redirect('admin_dashboard_sitari_chat')

            if not message_text:
                messages.error(request, 'Message cannot be empty.')
            else:
                TokenChatMessage.objects.create(
                    token=chat_token,
                    sender=TokenChatMessage.SENDER_ADMIN,
                    message=message_text,
                )

            return redirect(f"{reverse('admin_dashboard_sitari_chat')}?token={chat_token.token_no}")

    query = (request.GET.get('q') or '').strip()
    selected_token_no = (request.GET.get('token') or '').strip()

    tokens_qs = Token.objects.all().order_by('-created_at')
    if query:
        tokens_qs = tokens_qs.filter(
            Q(token_no__icontains=query)
            | Q(customer_name__icontains=query)
            | Q(cell_no__icontains=query)
        )

    selected_chat_token = None
    if selected_token_no:
        selected_chat_token = Token.objects.filter(token_no=selected_token_no).first()
    if not selected_chat_token:
        selected_chat_token = tokens_qs.first()

    selected_chat_messages = TokenChatMessage.objects.none()
    if selected_chat_token:
        selected_chat_messages = TokenChatMessage.objects.filter(token=selected_chat_token).order_by('created_at')

    base_context = _build_admin_dashboard_context()
    base_context.update({
        'sitari_chat_tokens': tokens_qs[:200],
        'sitari_chat_query': query,
        'selected_chat_token': selected_chat_token,
        'selected_chat_messages': selected_chat_messages,
    })
    return render(request, 'admin_dashboard.html', base_context)


@require_employee
def employee_sitari_chat(request, employee):
    from .models import Token, TokenChatMessage, Announcement
    from django.urls import reverse

    assigned_tokens_qs = Token.objects.filter(operator_name_id=employee.employee_id).order_by('-created_at')

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'send_employee_message':
            token_id = request.POST.get('chat_token_id')
            message_text = (request.POST.get('employee_message') or '').strip()
            chat_token = assigned_tokens_qs.filter(pk=token_id).first()

            if not chat_token:
                messages.error(request, 'Selected token is not assigned to you.')
                return redirect('employee_sitari_chat')

            if not message_text:
                messages.error(request, 'Message cannot be empty.')
            else:
                TokenChatMessage.objects.create(
                    token=chat_token,
                    sender=TokenChatMessage.SENDER_ADMIN,
                    message=message_text,
                )

            return redirect(f"{reverse('employee_sitari_chat')}?token={chat_token.token_no}")

    query = (request.GET.get('q') or '').strip()
    selected_token_no = (request.GET.get('token') or '').strip()

    if query:
        assigned_tokens_qs = assigned_tokens_qs.filter(
            Q(token_no__icontains=query)
            | Q(customer_name__icontains=query)
            | Q(cell_no__icontains=query)
        )

    selected_chat_token = None
    if selected_token_no:
        selected_chat_token = assigned_tokens_qs.filter(token_no=selected_token_no).first()
    if not selected_chat_token:
        selected_chat_token = assigned_tokens_qs.first()

    selected_chat_messages = TokenChatMessage.objects.none()
    if selected_chat_token:
        selected_chat_messages = TokenChatMessage.objects.filter(token=selected_chat_token).order_by('created_at')

    active_announcements = Announcement.objects.filter(active=True).order_by('-created_at')
    is_department_head = bool(employee.department and employee.department.department_head_id == employee.employee_id)

    context = {
        'employee': employee,
        'active_announcements': active_announcements,
        'is_department_head': is_department_head,
        'has_token_naming_access': bool(employee.token_naming_access and not employee.locked),
        'sitari_chat_tokens': assigned_tokens_qs[:200],
        'sitari_chat_query': query,
        'selected_chat_token': selected_chat_token,
        'selected_chat_messages': selected_chat_messages,
    }
    return render(request, 'employee_sitari_chat.html', context)


@require_employee
def employee_chat_assignment_check(request, employee):
    from django.utils.dateparse import parse_datetime
    from .models import Token

    since_raw = (request.GET.get('since') or '').strip()
    since_dt = None
    if since_raw:
        parsed = parse_datetime(since_raw)
        if parsed is not None:
            if timezone.is_naive(parsed):
                since_dt = timezone.make_aware(parsed, timezone.get_current_timezone())
            else:
                since_dt = timezone.localtime(parsed)

    assigned_tokens_qs = Token.objects.filter(operator_name_id=employee.employee_id).order_by('-created_at')
    latest_assigned_token = assigned_tokens_qs.first()
    latest_assigned_at = latest_assigned_token.created_at.isoformat() if latest_assigned_token else None

    # First load establishes baseline and avoids replaying older assignments.
    if since_dt is None:
        return JsonResponse({
            'new_assignments': [],
            'latest_assigned_at': latest_assigned_at,
        })

    new_assignments_qs = (
        assigned_tokens_qs
        .filter(created_at__gt=since_dt)
        .order_by('created_at')[:20]
    )

    return JsonResponse({
        'new_assignments': [
            {
                'token_no': item.token_no,
                'customer_name': item.customer_name,
                'cell_no': item.cell_no,
                'created_at': timezone.localtime(item.created_at).strftime('%d-%m-%Y %H:%M'),
            }
            for item in new_assignments_qs
        ],
        'latest_assigned_at': latest_assigned_at,
    })


def public_chatbot_reply(request):
    from .models import ChatbotServiceTemplate, ChatbotNumericTrigger

    user_message = (request.GET.get('message') or request.POST.get('message') or '').strip()
    if not user_message:
        return JsonResponse({'error': 'Message is required.'}, status=400)

    # Exact-number trigger flow: message must be numeric only and exactly match a configured trigger.
    if user_message.isdigit():
        trigger = ChatbotNumericTrigger.objects.filter(
            is_active=True,
            trigger_number=user_message,
        ).first()
        if trigger:
            documents = []
            if trigger.response_pdf:
                documents.append({
                    'name': trigger.response_pdf.name.rsplit('/', 1)[-1],
                    'url': trigger.response_pdf.url,
                })
            return JsonResponse({
                'reply': trigger.response_text,
                'matched_service': None,
                'matched_trigger': trigger.trigger_number,
                'documents': documents,
            })

    normalized = user_message.lower()
    templates_qs = ChatbotServiceTemplate.objects.filter(is_active=True).order_by('sort_order', 'service_name')

    for item in templates_qs:
        if item.service_name and item.service_name.lower() in normalized:
            return JsonResponse({'reply': item.template_text, 'matched_service': item.service_name, 'documents': []})

        keywords = [k.strip().lower() for k in (item.keywords or '').split(',') if k.strip()]
        if any(keyword in normalized for keyword in keywords):
            return JsonResponse({'reply': item.template_text, 'matched_service': item.service_name, 'documents': []})

    return JsonResponse({
        'reply': 'I can help with services, timings, address, and contact details. For quick support, use the WhatsApp icon on the right.',
        'matched_service': None,
        'documents': [],
    })


@csrf_exempt
def assistant_chat_log(request):
    import json
    from django.core import signing
    from .models import Token, TokenChatMessage

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    access_token = str(payload.get('access') or '').strip()
    sender = str(payload.get('sender') or '').strip().lower()
    message = str(payload.get('message') or '').strip()

    if not access_token:
        return JsonResponse({'error': 'Missing access token.'}, status=400)
    if sender not in {
        TokenChatMessage.SENDER_CUSTOMER,
        TokenChatMessage.SENDER_BOT,
        TokenChatMessage.SENDER_ADMIN,
    }:
        return JsonResponse({'error': 'Invalid sender.'}, status=400)
    if not message:
        return JsonResponse({'error': 'Message is required.'}, status=400)

    try:
        signed_data = signing.loads(
            access_token,
            salt='assistant-customer-link',
            max_age=60 * 60 * 24 * 30,
        )
    except signing.BadSignature:
        return JsonResponse({'error': 'Invalid assistant access token.'}, status=403)
    except signing.SignatureExpired:
        return JsonResponse({'error': 'Assistant access token expired.'}, status=403)

    token_id = signed_data.get('token_id')
    token = Token.objects.filter(pk=token_id).first()
    if not token:
        return JsonResponse({'error': 'Invalid token context.'}, status=404)

    TokenChatMessage.objects.create(
        token=token,
        sender=sender,
        message=message,
    )
    return JsonResponse({'status': 'ok'})


@staff_member_required
def admin_employee_daily_worksheet_pdf(request, employee_id, time_range='full_day'):
    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    now_local = timezone.localtime(timezone.now())
    today = now_local.date()

    employee = get_object_or_404(Employee, employee_id=employee_id)
    department = employee.department
    department_name = department.name if department else ''

    start_date_raw = (request.GET.get('start_date') or '').strip()
    end_date_raw = (request.GET.get('end_date') or '').strip()
    custom_start_date = None
    custom_end_date = None
    try:
        if start_date_raw and end_date_raw:
            custom_start_date = datetime.strptime(start_date_raw, '%Y-%m-%d').date()
            custom_end_date = datetime.strptime(end_date_raw, '%Y-%m-%d').date()
    except ValueError:
        custom_start_date = None
        custom_end_date = None

    is_custom_range = bool(custom_start_date and custom_end_date and custom_start_date <= custom_end_date)

    # Filter entries based on time_range or custom date range
    if is_custom_range:
        todays_entries = Worksheet.objects.filter(
            employee=employee,
            date__gte=custom_start_date,
            date__lte=custom_end_date,
        ).order_by('date', 'created_at', 'id')
        time_range_label = f"{custom_start_date.strftime('%d %b %Y')} - {custom_end_date.strftime('%d %b %Y')}"
    elif time_range == '5pm':
        # 12:00 AM to 5:00 PM (00:00 to 17:00)
        start_of_day = timezone.make_aware(datetime.combine(today, time(0, 0, 0)))
        end_of_5pm = timezone.make_aware(datetime.combine(today, time(17, 0, 0)))
        todays_entries = Worksheet.objects.filter(
            employee=employee,
            date=today,
            created_at__gte=start_of_day,
            created_at__lt=end_of_5pm,
        ).order_by('created_at', 'id')
        time_range_label = "12:00 AM - 5:00 PM"
    elif time_range == '9pm':
        # 5:00 PM to 12:00 AM (17:00 to 23:59:59)
        end_of_5pm = timezone.make_aware(datetime.combine(today, time(17, 0, 0)))
        end_of_day = timezone.make_aware(datetime.combine(today, time(23, 59, 59)))
        todays_entries = Worksheet.objects.filter(
            employee=employee,
            date=today,
            created_at__gte=end_of_5pm,
            created_at__lte=end_of_day,
        ).order_by('created_at', 'id')
        time_range_label = "5:00 PM - 12:00 AM"
    else:
        # full_day: all entries for today
        todays_entries = Worksheet.objects.filter(employee=employee, date=today).order_by('created_at', 'id')
        time_range_label = "Full Day"
    
    totals = todays_entries.aggregate(total_payment=models.Sum('payment'), total_amount=models.Sum('amount'))
    total_payment = totals.get('total_payment') or Decimal('0.00')
    total_amount = totals.get('total_amount') or Decimal('0.00')
    from .models import EmployeeTarget as _ET
    _target_obj = _ET.objects.filter(employee=employee, date=today).first()
    _daily_target = (_target_obj.target_amount + _target_obj.carry_forward) if _target_obj else Decimal('0.00')
    todays_commission = _calc_commission(total_amount, _daily_target)

    def _display(value):
        return '-' if value in (None, '') else str(value)

    def _money(value):
        if value is None:
            value = Decimal('0.00')
        return f"{Decimal(value):.2f}"

    def _entry_timestamp(value):
        if not value:
            return '-'
        return timezone.localtime(value).strftime('%I:%M %p')

    dynamic_columns = []
    has_payment_column = False

    if department_name in ('Mee Seva', 'Online Hub'):
        dynamic_columns = [
            ('T.K No', lambda e: _display(e.token_no)),
            ('Customer Name', lambda e: _display(e.customer_name)),
            ('Customer Mobile', lambda e: _display(e.customer_mobile)),
            ('Service', lambda e: _display(e.service)),
            ('Particulars', lambda e: _display(e.particulars)),
            ('Transaction Num', lambda e: _display(e.transaction_num)),
            ('Certificate Num', lambda e: _display(e.certificate_number)),
            ('Payment', lambda e: _money(e.payment)),
        ]
        has_payment_column = True
    elif department_name == 'Aadhaar':
        dynamic_columns = [
            ('T.K No', lambda e: _display(e.token_no)),
            ('Customer Name', lambda e: _display(e.customer_name)),
            ('Customer Mobile', lambda e: _display(e.customer_mobile)),
            ('Service', lambda e: _display(e.service)),
            ('Particulars', lambda e: _display(e.particulars)),
            ('Enrollment No', lambda e: _display(e.enrollment_no)),
            ('Certificate Num', lambda e: _display(e.certificate_number)),
            ('Payment', lambda e: _money(e.payment)),
        ]
        has_payment_column = True
    elif department_name == 'Bhu Bharathi':
        dynamic_columns = [
            ('Token No', lambda e: _display(e.token_no)),
            ('Customer Name', lambda e: _display(e.customer_name)),
            ('Login Mobile', lambda e: _display(e.login_mobile_no)),
            ('Application No', lambda e: _display(e.application_no)),
            ('Status', lambda e: _display(e.status)),
            ('Payment', lambda e: _money(e.payment)),
        ]
        has_payment_column = True
    elif department_name == 'Forms':
        dynamic_columns = [
            ('Service', lambda e: _display(e.service)),
            ('Particulars', lambda e: _display(e.particulars)),
        ]
    elif department_name == 'Xerox':
        dynamic_columns = [
            ('Token No', lambda e: _display(e.token_no)),
            ('Customer Name', lambda e: _display(e.customer_name)),
            ('Mobile No.', lambda e: _display(e.customer_mobile)),
            ('Service', lambda e: _display(e.service)),
            ('Particulars', lambda e: _display(e.particulars)),
            ('Payment', lambda e: _money(e.payment)),
        ]
        has_payment_column = True
    elif department_name == 'Notary and Bonds':
        dynamic_columns = [
            ('Token No', lambda e: _display(e.token_no)),
            ('Customer Name', lambda e: _display(e.customer_name)),
            ('Service', lambda e: _display(e.service)),
            ('Particulars', lambda e: _display(e.particulars)),
            ('Bonds Sl. No', lambda e: _display(e.bonds_sno)),
            ('Payment', lambda e: _money(e.payment)),
        ]
        has_payment_column = True
    else:
        dynamic_columns = [
            ('Service', lambda e: _display(e.service)),
            ('Particulars', lambda e: _display(e.particulars)),
            ('Payment', lambda e: _money(e.payment)),
        ]
        has_payment_column = True

    headers = ['Sl.No', 'Timestamp'] + [col[0] for col in dynamic_columns] + ['Amount (Rs)', 'Commission (Rs)']
    table_data = [headers]

    for idx, entry in enumerate(todays_entries, start=1):
        row = [str(idx), _entry_timestamp(entry.created_at)]
        for _, extractor in dynamic_columns:
            row.append(extractor(entry))
        row.append(_money(entry.amount))
        row.append(_money((entry.amount or Decimal('0.00')) * Decimal('0.05')))
        table_data.append(row)

    if len(table_data) == 1:
        empty_row = ['No entries for today.'] + [''] * (len(headers) - 1)
        table_data.append(empty_row)

    summary_row = [''] * len(headers)
    if len(headers) >= 3:
        summary_row[-3] = 'Total' if has_payment_column else ''
        summary_row[-2] = _money(total_amount)
        summary_row[-1] = _money(todays_commission)
        if has_payment_column:
            summary_row[-3] = _money(total_payment)
            summary_row[-4] = 'Total'
    table_data.append(summary_row)

    commission_row = [''] * len(headers)
    commission_row[-2] = 'Commission (5%)'
    commission_row[-1] = _money(todays_commission)
    table_data.append(commission_row)

    response = HttpResponse(content_type='application/pdf')
    if is_custom_range:
        filename_date_part = f"{custom_start_date.isoformat()}_to_{custom_end_date.isoformat()}"
    else:
        filename_date_part = today.isoformat()
    response['Content-Disposition'] = f'inline; filename="worksheet_{employee.employee_id}_{filename_date_part}.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=20,
        bottomMargin=20,
    )

    styles = getSampleStyleSheet()
    elements = [
        Paragraph('Worksheet Report', styles['Title']),
        Spacer(1, 8),
        Paragraph(f'Employee: {employee.name} (ID: {employee.employee_id})', styles['Normal']),
        Paragraph(f'Department: {department_name or "-"}', styles['Normal']),
        Paragraph(
            f"Date Range: {custom_start_date.strftime('%d %b %Y')} to {custom_end_date.strftime('%d %b %Y')}"
            if is_custom_range else f"Date: {today.strftime('%d %b %Y')}",
            styles['Normal']
        ),
        Paragraph(f'Time Range: {time_range_label}', styles['Normal']),
        Spacer(1, 12),
    ]

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -3), [colors.white, colors.HexColor('#f8fafc')]),
        ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor('#eef2f7')),
        ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e5ebf3')),
    ]))

    elements.append(table)
    doc.build(elements)
    return response


@staff_member_required
def admin_employee_commission_print(request, employee_id, period):
    from django.utils.timezone import localtime, now as tz_now
    now_local = localtime(tz_now())
    today = now_local.date()

    employee = get_object_or_404(Employee, employee_id=employee_id)
    department_name = employee.department.name if employee.department else '-'

    if period == 'weekly':
        # Monday of the current week up to today
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        period_label = f"Weekly ({start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')})"
    elif period == 'monthly':
        start_date = today.replace(day=1)
        end_date = today
        period_label = f"Monthly ({start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')})"
    else:
        return HttpResponseBadRequest("Invalid period. Use 'weekly' or 'monthly'.")

    totals = Worksheet.objects.filter(
        employee=employee,
        date__gte=start_date,
        date__lte=end_date,
    ).aggregate(total_amount=models.Sum('amount'))
    total_amount = totals.get('total_amount') or Decimal('0.00')
    from .models import EmployeeTarget as _ET
    from django.db.models import F
    _period_target_agg = _ET.objects.filter(
        employee=employee, date__gte=start_date, date__lte=end_date
    ).aggregate(total=models.Sum(F('target_amount') + F('carry_forward')))
    period_target = _period_target_agg.get('total') or Decimal('0.00')
    commission = _calc_commission(total_amount, period_target)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Commission – {employee.name}</title>
<style>
  @page {{ margin: 20mm; }}
  body {{ font-family: Arial, sans-serif; color: #1f2937; }}
  h2 {{ text-align: center; margin-bottom: 4px; }}
  .subtitle {{ text-align: center; color: #6b7280; margin-bottom: 24px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
  th, td {{ border: 1px solid #d1d5db; padding: 10px 14px; text-align: left; }}
  th {{ background: #1f2937; color: #fff; font-size: 13px; }}
  td {{ font-size: 14px; }}
  .commission-row td {{ background: #eef7ee; font-weight: bold; font-size: 16px; color: #166534; }}
  @media print {{ .no-print {{ display: none; }} body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}
</style>
</head>
<body>
<h2>Commission Statement</h2>
<p class="subtitle">{period_label}</p>

<table>
  <tr><th>Employee</th><td>{employee.name} (ID: {employee.employee_id})</td></tr>
  <tr><th>Department</th><td>{department_name}</td></tr>
  <tr><th>Period</th><td>{period_label}</td></tr>
  <tr><th>Total Amount (₹)</th><td>₹ {total_amount:.2f}</td></tr>
  <tr><th>Period Target (₹)</th><td>₹ {period_target:.2f}</td></tr>
  <tr class="commission-row"><th>Commission (5% / 10% above target) (₹)</th><td>₹ {commission:.2f}</td></tr>
</table>

<p class="no-print" style="margin-top:24px; text-align:center;">
  <button onclick="window.print()" style="padding:8px 24px;font-size:14px;cursor:pointer;">Print</button>
</p>
<script>window.onload = function() {{ window.print(); }};</script>
</body>
</html>"""

    return HttpResponse(html)


@staff_member_required
def admin_employee_targets(request):
    from .models import EmployeeTarget
    now_local = timezone.localtime(timezone.now())
    today = now_local.date()
    yesterday = today - timedelta(days=1)

    employees = Employee.objects.select_related('department').order_by('department__name', 'name')

    if request.method == 'POST':
        for emp in employees:
            key = f'target_{emp.employee_id}'
            raw = request.POST.get(key, '').strip()
            if raw == '':
                continue
            try:
                amount = Decimal(raw).quantize(Decimal('0.01'))
            except Exception:
                continue
            EmployeeTarget.objects.update_or_create(
                employee=emp,
                date=today,
                defaults={'target_amount': amount},
            )
        messages.success(request, f"Targets saved for {today.strftime('%d %b %Y')}.")
        return redirect(request.path)

    # --- Carry-forward: calculate from yesterday ---
    # Yesterday's targets
    yesterday_targets = {
        t.employee_id: t
        for t in EmployeeTarget.objects.filter(date=yesterday)
    }
    # Yesterday's collections
    yesterday_collections = {
        row['employee_id']: row['total_amount'] or Decimal('0.00')
        for row in Worksheet.objects.filter(date=yesterday)
        .values('employee_id')
        .annotate(total_amount=models.Sum('amount'))
    }
    # Compute and persist carry_forward on today's record for each employee
    for emp in employees:
        yest_entry = yesterday_targets.get(emp.employee_id)
        if yest_entry:
            yest_effective = yest_entry.target_amount + yest_entry.carry_forward
            yest_collection = yesterday_collections.get(emp.employee_id, Decimal('0.00'))
            shortfall = max(Decimal('0.00'), (yest_effective - yest_collection).quantize(Decimal('0.01')))
            prev_target = yest_entry.target_amount
        else:
            shortfall = Decimal('0.00')
            prev_target = Decimal('0.00')
        # When creating today's record for the first time, pre-fill target_amount from yesterday.
        # When updating an existing record, only refresh carry_forward (preserve admin-entered target).
        EmployeeTarget.objects.update_or_create(
            employee=emp,
            date=today,
            create_defaults={'target_amount': prev_target, 'carry_forward': shortfall},
            defaults={'carry_forward': shortfall},
        )

    # Build today's target map (fresh after carry_forward update)
    today_target_objs = {
        t.employee_id: t
        for t in EmployeeTarget.objects.filter(date=today)
    }

    # Today's collections
    today_actuals_map = {
        row['employee_id']: row['total_amount'] or Decimal('0.00')
        for row in Worksheet.objects.filter(date=today)
        .values('employee_id')
        .annotate(total_amount=models.Sum('amount'))
    }

    rows = []
    for emp in employees:
        obj = today_target_objs.get(emp.employee_id)
        target = obj.target_amount if obj else Decimal('0.00')
        carry_forward = obj.carry_forward if obj else Decimal('0.00')
        effective_target = target + carry_forward
        collection = today_actuals_map.get(emp.employee_id, Decimal('0.00'))
        balance = (effective_target - collection).quantize(Decimal('0.01'))
        achieved = collection >= effective_target if effective_target > 0 else None
        rows.append({
            'employee': emp,
            'target': target,
            'carry_forward': carry_forward,
            'effective_target': effective_target,
            'collection': collection,
            'balance': balance,
            'achieved': achieved,
        })

    context = {
        'rows': rows,
        'today': today,
    }
    admin_context = admin.site.each_context(request)
    admin_context.update(context)
    return render(request, 'admin/employee_targets.html', admin_context)


@require_employee
def worksheet_entry_edit_view(request, employee, entry_id):
    entry = get_object_or_404(Worksheet, pk=entry_id, employee=employee)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if entry.approved:
        messages.error(request, "This entry is approved and cannot be edited.")
        return redirect('worksheet')

    if request.method == 'POST':
        form = WorksheetEntryEditForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Worksheet entry updated successfully.")
            return redirect('worksheet')
    else:
        form = WorksheetEntryEditForm(instance=entry)

    context = {
        'form': form,
        'entry_id': entry_id,
        'entry': entry,
        'employee': employee,
    }

    if is_ajax:
        return render(request, 'partials/worksheet_edit_form.html', context)
    return render(request, 'management/worksheet_entry_edit.html', context)




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
            
    # Redirect to the dedicated uploads page whether success or failure
    return redirect('employee_uploads')


@require_employee
def employee_uploads_view(request, employee):
    has_token_naming_access = bool(employee.token_naming_access and not employee.locked)
    is_department_head = bool(employee.department and employee.department.department_head_id == employee.employee_id)

    upload_form = EmployeeUploadForm()
    if request.method == 'POST':
        upload_form = EmployeeUploadForm(request.POST, request.FILES)
        if upload_form.is_valid():
            upload = upload_form.save(commit=False)
            upload.employee = employee
            upload.save()
            messages.success(request, 'File uploaded successfully.')
            return redirect('employee_uploads')
        messages.error(request, 'Please correct the upload form errors and try again.')

    uploads = employee.file_uploads.select_related('service').order_by('-uploaded_at')

    context = {
        'employee': employee,
        'uploads': uploads,
        'upload_form': upload_form,
        'is_department_head': is_department_head,
        'has_token_naming_access': has_token_naming_access,
    }
    return render(request, 'uploads.html', context)



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
    
    tasks = TodoTask.objects.filter(employee_id=employee_id, completed=False).order_by('due_time')
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
    task.completed = True
    task.save(update_fields=["completed"])
    return JsonResponse({"status": "success"})


# Assigned tasks page for employees
from django.contrib.auth.decorators import login_required

def assigned_tasks_view(request):
    if not request.session.get("employee_id"):
        return redirect('login')
    return render(request, 'assigned_tasks.html')


@staff_member_required
def admin_worksheet_data(request):
    import os
    from django.conf import settings as _settings

    worksheet_data_root = os.path.join(_settings.MEDIA_ROOT, 'worksheet_data')
    media_url_base = _settings.MEDIA_URL.rstrip('/')

    # Build tree: list of (date_str, list of (emp_id, emp_name, list of (filename, file_url, size_kb)))
    tree = []

    if os.path.isdir(worksheet_data_root):
        date_folders = sorted(
            [d for d in os.listdir(worksheet_data_root)
             if os.path.isdir(os.path.join(worksheet_data_root, d))],
            reverse=True  # newest date first
        )

        # Prefetch employees for name lookup
        emp_map = {str(e.employee_id): e.name for e in Employee.objects.all()}

        for date_str in date_folders:
            date_path = os.path.join(worksheet_data_root, date_str)
            emp_entries = []
            emp_folders = sorted(
                [e for e in os.listdir(date_path)
                 if os.path.isdir(os.path.join(date_path, e))]
            )
            for emp_id in emp_folders:
                emp_path = os.path.join(date_path, emp_id)
                files = []
                for fname in sorted(os.listdir(emp_path)):
                    fpath = os.path.join(emp_path, fname)
                    if os.path.isfile(fpath):
                        rel = f"worksheet_data/{date_str}/{emp_id}/{fname}"
                        url = f"{media_url_base}/{rel}"
                        size_kb = round(os.path.getsize(fpath) / 1024, 1)
                        ext = os.path.splitext(fname)[1].lower()
                        is_image = ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
                        files.append({'name': fname, 'url': url, 'size_kb': size_kb, 'is_image': is_image})
                emp_entries.append({
                    'emp_id': emp_id,
                    'emp_name': emp_map.get(emp_id, emp_id),
                    'files': files,
                    'file_count': len(files),
                })
            total_files = sum(e['file_count'] for e in emp_entries)
            tree.append({'date': date_str, 'emp_entries': emp_entries, 'total_files': total_files})

    return render(request, 'admin/worksheet_data.html', {'tree': tree})


# --- TTD Section Views ---

from .models import TTDGroupSeva, TTDGroupMember, TTDIndividualDarshan
from .forms import TTDGroupSevaStep1Form, TTDGroupMemberForm, TTDIndividualDarshanForm

@require_employee
def ttd_main_view(request, employee):
    """Main TTD page – lists recent group sevas and individual darshans."""
    group_sevas = TTDGroupSeva.objects.all().prefetch_related('members').order_by('-created_at')[:20]
    individual_darshans = TTDIndividualDarshan.objects.all().order_by('-created_at')[:20]
    return render(request, 'ttd_main.html', {
        'group_sevas': group_sevas,
        'individual_darshans': individual_darshans,
    })


@require_employee
def ttd_group_seva_step1(request, employee):
    """Step 1: Enter number of members and planned date for Group Seva."""
    if request.method == 'POST':
        form = TTDGroupSevaStep1Form(request.POST)
        if form.is_valid():
            group_seva = form.save(commit=False)
            group_seva.created_by = employee
            group_seva.save()
            return redirect('ttd_group_seva_step2', group_id=group_seva.pk)
    else:
        form = TTDGroupSevaStep1Form()
    return render(request, 'ttd_group_seva_step1.html', {'form': form})


@require_employee
def ttd_group_seva_step2(request, employee, group_id):
    """Step 2: Enter member details for the group seva."""
    from django.forms import modelformset_factory
    from .forms import TTDGroupMemberForm

    try:
        group_seva = TTDGroupSeva.objects.get(pk=group_id)
    except TTDGroupSeva.DoesNotExist:
        from django.contrib import messages as msg
        msg.error(request, "Group Seva not found.")
        return redirect('ttd_main')

    MemberFormSet = modelformset_factory(
        TTDGroupMember,
        form=TTDGroupMemberForm,
        extra=group_seva.num_members,
        can_delete=False,
        max_num=group_seva.num_members,
        validate_max=True,
    )

    if request.method == 'POST':
        formset = MemberFormSet(request.POST, queryset=TTDGroupMember.objects.none())
        if formset.is_valid():
            members = formset.save(commit=False)
            for idx, member in enumerate(members, start=1):
                member.group = group_seva
                member.order = idx
                member.save()
            from django.contrib import messages as msg
            msg.success(request, f"Group Seva saved with {len(members)} members.")
            return redirect('ttd_main')
    else:
        formset = MemberFormSet(queryset=TTDGroupMember.objects.none())

    return render(request, 'ttd_group_seva_step2.html', {
        'group_seva': group_seva,
        'formset': formset,
    })


@require_employee
def ttd_individual_darshan_create(request, employee):
    """Create an individual darshan booking."""
    if request.method == 'POST':
        form = TTDIndividualDarshanForm(request.POST)
        if form.is_valid():
            darshan = form.save(commit=False)
            darshan.created_by = employee
            darshan.save()
            from django.contrib import messages as msg
            msg.success(request, "Individual Darshan booking saved.")
            return redirect('ttd_main')
    else:
        form = TTDIndividualDarshanForm()
    return render(request, 'ttd_individual_darshan.html', {'form': form})


@require_employee
def ttd_group_seva_delete(request, employee, group_id):
    """Delete a group seva and its members."""
    try:
        group_seva = TTDGroupSeva.objects.get(pk=group_id)
        group_seva.delete()
        from django.contrib import messages as msg
        msg.success(request, "Group Seva deleted.")
    except TTDGroupSeva.DoesNotExist:
        pass
    return redirect('ttd_main')


@require_employee
def ttd_individual_darshan_delete(request, employee, darshan_id):
    """Delete an individual darshan booking."""
    try:
        darshan = TTDIndividualDarshan.objects.get(pk=darshan_id)
        darshan.delete()
        from django.contrib import messages as msg
        msg.success(request, "Individual Darshan booking deleted.")
    except TTDIndividualDarshan.DoesNotExist:
        pass
    return redirect('ttd_main')


@require_employee
def ttd_group_seva_print(request, employee, group_id):
    """Print view for a single group seva booking."""
    try:
        group_seva = TTDGroupSeva.objects.prefetch_related('members').get(pk=group_id)
    except TTDGroupSeva.DoesNotExist:
        from django.http import Http404
        raise Http404
    return render(request, 'ttd_group_seva_print.html', {'group_seva': group_seva})


@require_employee
def ttd_individual_darshan_print(request, employee, darshan_id):
    """Print view for a single individual darshan booking."""
    try:
        darshan = TTDIndividualDarshan.objects.get(pk=darshan_id)
    except TTDIndividualDarshan.DoesNotExist:
        from django.http import Http404
        raise Http404
    return render(request, 'ttd_individual_darshan_print.html', {'darshan': darshan})


@require_employee
def ttd_print_all(request, employee):
    """Print all TTD bookings — all group sevas and all individual darshans."""
    group_sevas = TTDGroupSeva.objects.all().prefetch_related('members').order_by('planned_date', '-created_at')
    individual_darshans = TTDIndividualDarshan.objects.all().order_by('planned_date', 'slot_time')
    return render(request, 'ttd_print_all.html', {
        'group_sevas': group_sevas,
        'individual_darshans': individual_darshans,
    })
