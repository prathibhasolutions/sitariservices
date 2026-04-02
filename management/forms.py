


from django import forms
from .models import Invoice, Particular
from django.forms import inlineformset_factory, formset_factory
from .models import Token, Department, ServiceType, Employee



class InvoiceForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=forms.fields.datetime.date.today)
    class Meta:
        model = Invoice
        fields = ['date', 'customer_name']


ParticularFormSet = inlineformset_factory(
    Invoice, Particular, fields=('description', 'amount'), extra=1, can_delete=True
)


class TokenNamingForm(forms.ModelForm):
    class Meta:
        model = Token
        fields = ['customer_name', 'cell_no', 'department', 'service_type', 'operator_name']
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter customer name'}),
            'cell_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter cell number'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'service_type': forms.Select(attrs={'class': 'form-control'}),
            'operator_name': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.all().order_by('name')
        self.fields['department'].empty_label = '-- Select Department --'
        self.fields['service_type'].queryset = ServiceType.objects.none()
        self.fields['service_type'].empty_label = '-- Select Service Type --'
        self.fields['operator_name'].queryset = (
            Employee.objects.filter(
                locked=False,
                attendance_sessions__logout_time__isnull=True,
                attendance_sessions__session_closed=False,
            )
            .distinct()
            .order_by('name')
        )
        self.fields['operator_name'].empty_label = '-- Select Active Operator --'

        department_id = None
        if self.data.get('department'):
            department_id = self.data.get('department')
        elif self.instance and self.instance.pk and self.instance.department_id:
            department_id = self.instance.department_id

        if department_id:
            self.fields['service_type'].queryset = ServiceType.objects.filter(
                departments__id=department_id
            ).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        service_type = cleaned_data.get('service_type')
        if department and service_type and not service_type.departments.filter(pk=department.pk).exists():
            self.add_error('service_type', 'Selected service type does not belong to the selected department.')
        return cleaned_data



from .models import Worksheet

from .models import Worksheet, ServiceType


class TokenRequiredWorksheetMixin:
    token_required_message = "Token number is required for this department."

    def clean_token_no(self):
        token_no = (self.cleaned_data.get('token_no') or '').strip()
        if not token_no:
            raise forms.ValidationError(self.token_required_message)
        return token_no

class MeesevaWorksheetForm(TokenRequiredWorksheetMixin, forms.ModelForm):
    service = forms.ModelChoiceField(
        queryset=ServiceType.objects.none(),
        empty_label="-- Select a Service --",
        required=False,
        label="Service (with Amount)",
        widget=forms.Select(attrs={'class': 'form-control service-dropdown'})
    )
    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        import logging
        logger = logging.getLogger("worksheet_form")
        logger.warning(f"Employee: {employee}")
        logger.warning(f"Department: {getattr(employee, 'department', None)}")
        if employee and employee.department:
            qs = ServiceType.objects.filter(departments=employee.department)
            logger.warning(f"ServiceType queryset: {list(qs)}")
            self.fields['service'].queryset = qs
        else:
            logger.warning("No department or employee provided, empty queryset.")
            self.fields['service'].queryset = ServiceType.objects.none()
    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name', 'customer_mobile', 'service', 'particulars', 'transaction_num', 'certificate_number','payment', 'amount']

class AadharWorksheetForm(TokenRequiredWorksheetMixin, forms.ModelForm):
    service = forms.ModelChoiceField(
        queryset=ServiceType.objects.none(),
        empty_label="-- Select a Service --",
        required=False,
        label="Service (with Amount)",
        widget=forms.Select(attrs={'class': 'form-control service-dropdown'})
    )
    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee and employee.department:
            self.fields['service'].queryset = ServiceType.objects.filter(departments=employee.department)
        else:
            self.fields['service'].queryset = ServiceType.objects.none()
    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name', 'customer_mobile', 'service', 'particulars', 'enrollment_no', 'certificate_number', 'payment', 'amount']

class BhuBharathiWorksheetForm(TokenRequiredWorksheetMixin, forms.ModelForm):
    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        # employee is ignored, just for compatibility

    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name',  'login_mobile_no', 'application_no', 'status','payment',  'amount', 'particulars']

# RENAMED from XeroxWorksheetForm
class FormsWorksheetForm(TokenRequiredWorksheetMixin, forms.ModelForm):
    service = forms.ModelChoiceField(
        queryset=ServiceType.objects.none(),
        empty_label="-- Select a Service --",
        required=False,
        label="Service (with Amount)",
        widget=forms.Select(attrs={'class': 'form-control service-dropdown'})
    )
    stocks_used = forms.IntegerField(
        required=False,
        min_value=1,
        initial=1,
        label="Stocks Used",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1'}),
    )

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee and employee.department:
            self.fields['service'].queryset = ServiceType.objects.filter(departments=employee.department)
        else:
            self.fields['service'].queryset = ServiceType.objects.none()

    def clean_stocks_used(self):
        val = self.cleaned_data.get('stocks_used')
        if val is None:
            return 1
        return val

    class Meta:
        model = Worksheet
        fields = ['token_no', 'service', 'particulars', 'stocks_used', 'amount']

# NEW form for the new 'Xerox' department (without 'particulars')
class XeroxWorksheetForm(forms.ModelForm):
    service = forms.ModelChoiceField(
        queryset=ServiceType.objects.none(),
        empty_label="-- Select a Service --",
        required=False,
        label="Service (with Amount)",
        widget=forms.Select(attrs={'class': 'form-control service-dropdown'})
    )

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee and employee.department:
            self.fields['service'].queryset = ServiceType.objects.filter(departments=employee.department)
        else:
            self.fields['service'].queryset = ServiceType.objects.none()

    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name', 'customer_mobile', 'service', 'particulars', 'payment', 'amount']

# NEW form for 'Notary and Bonds' department
class NotaryAndBondsWorksheetForm(TokenRequiredWorksheetMixin, forms.ModelForm):
    service = forms.ModelChoiceField(
        queryset=ServiceType.objects.none(),
        empty_label="-- Select a Service --",
        required=False,
        label="Service (with Amount)",
        widget=forms.Select(attrs={'class': 'form-control service-dropdown'})
    )
    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee and employee.department:
            self.fields['service'].queryset = ServiceType.objects.filter(departments=employee.department)
        else:
            self.fields['service'].queryset = ServiceType.objects.none()
    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name', 'service', 'particulars', 'bonds_sno', 'payment', 'amount']

# Form for employee worksheet edits while protecting key identifiers
class WorksheetEntryEditForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = [
            'particulars',
            'transaction_num',
            'enrollment_no',
            'login_mobile_no',
            'application_no',
            'status',
            'certificate_number',
            'bonds_sno',
            'payment',
            'amount',
        ]
        widgets = {
            'particulars': forms.TextInput(attrs={'class': 'form-control'}),
            'transaction_num': forms.TextInput(attrs={'class': 'form-control'}),
            'enrollment_no': forms.TextInput(attrs={'class': 'form-control'}),
            'login_mobile_no': forms.TextInput(attrs={'class': 'form-control'}),
            'application_no': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.TextInput(attrs={'class': 'form-control'}),
            'certificate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bonds_sno': forms.TextInput(attrs={'class': 'form-control'}),
            'payment': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep optional fields easy to submit when not applicable to a department
        for name, field in self.fields.items():
            field.required = False



from .models import Worksheet, ResourceRepairReport


# --- NEW FORM FOR RESOURCE REPAIR CHECKLIST ---
class ResourceRepairForm(forms.ModelForm):
    class Meta:
        model = ResourceRepairReport
        fields = [
            'monitor_status', 'cpu_status', 'keyboard_status', 'mouse_status',
            'cables_status', 'printer_status', 'bike_status', 'remarks'
        ]
        widgets = {
            'monitor_status': forms.RadioSelect(attrs={'class': 'form-check-inline'}),
            'cpu_status': forms.RadioSelect(attrs={'class': 'form-check-inline'}),
            'keyboard_status': forms.RadioSelect(attrs={'class': 'form-check-inline'}),
            'mouse_status': forms.RadioSelect(attrs={'class': 'form-check-inline'}),
            'cables_status': forms.RadioSelect(attrs={'class': 'form-check-inline'}),
            'printer_status': forms.RadioSelect(attrs={'class': 'form-check-inline'}),
            'bike_status': forms.RadioSelect(attrs={'class': 'form-check-inline'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Any additional details...'}),
        }




from .models import EmployeeUpload, UploadService

class EmployeeUploadForm(forms.ModelForm):
    # Explicitly define the service field to add a placeholder
    service = forms.ModelChoiceField(
        queryset=UploadService.objects.all(),
        empty_label="-- Select a Service --",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Add renewal_date field with date picker
    renewal_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Date when this upload needs to be renewed"
    )
    
    # Add mobile_number field
    mobile_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter mobile number'
        }),
        help_text="Mobile number related to this upload"
    )

    class Meta:
        model = EmployeeUpload
        # Define the order of fields in the form
        fields = ['service', 'description', 'file', 'renewal_date', 'mobile_number']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }




from .models import Employee, ManagedLink

class EmployeeLinksForm(forms.ModelForm):
    """
    A form for an Employee that displays the assigned_links
    field as a list of checkboxes.
    """
    class Meta:
        model = Employee
        fields = ['assigned_links']
        widgets = {
            'assigned_links': forms.CheckboxSelectMultiple
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We make the queryset ordered by description for a consistent layout
        self.fields['assigned_links'].queryset = ManagedLink.objects.all().order_by('description')



from .models import Employee

class EmployeeProfilePictureForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['profile_picture']
        widgets = {
            # Use the simple FileInput and add the Bootstrap 'form-control' class
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }
        # We can hide the default label since we'll add our own in the template
        labels = {
            'profile_picture': '',
        }


# --- TTD Forms ---

from .models import TTDGroupSeva, TTDGroupMember, TTDIndividualDarshan

class TTDGroupSevaStep1Form(forms.ModelForm):
    """Step 1: Capture group size and planned date for TTD Group Seva."""
    class Meta:
        model = TTDGroupSeva
        fields = ['planned_date', 'num_members']
        widgets = {
            'planned_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'num_members': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 1, 'max': 100,
                'placeholder': 'e.g. 5'
            }),
        }
        labels = {
            'planned_date': 'Planned Date',
            'num_members': 'Number of Members',
        }


class TTDGroupMemberForm(forms.ModelForm):
    """Form for a single TTD group member."""
    class Meta:
        model = TTDGroupMember
        fields = ['name', 'mobile_number', 'aadhar_number']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'mobile_number': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '10-digit mobile',
                'maxlength': '15',
            }),
            'aadhar_number': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '12-digit Aadhaar',
                'maxlength': '12',
            }),
        }


TTDGroupMemberFormSet = forms.modelformset_factory(
    TTDGroupMember,
    form=TTDGroupMemberForm,
    extra=0,
    can_delete=False,
)


class TTDIndividualDarshanForm(forms.ModelForm):
    """Form for booking an individual TTD darshan."""
    class Meta:
        model = TTDIndividualDarshan
        fields = ['name', 'mobile_number', 'aadhar_number', 'planned_date', 'slot_time']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'mobile_number': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '10-digit mobile',
                'maxlength': '15',
            }),
            'aadhar_number': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '12-digit Aadhaar',
                'maxlength': '12',
            }),
            'planned_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'slot_time': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Full Name',
            'mobile_number': 'Mobile Number',
            'aadhar_number': 'Aadhaar Number',
            'planned_date': 'Planned Date',
            'slot_time': 'Slot Time',
        }



from .models import Employee

class EmployeeAdminForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = '__all__'  # Include all fields
        widgets = {
            # THIS IS THE KEY: Replace the default widget with a simple one
            'profile_picture': forms.FileInput,
        }



from .models import Employee, Department 
    
class WorksheetFilterForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    approved = forms.ChoiceField(
        choices=[('', '---------'), ('yes', 'Yes'), ('no', 'No')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


