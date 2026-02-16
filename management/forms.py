


from django import forms
from .models import Invoice, Particular
from django.forms import inlineformset_factory, formset_factory



class InvoiceForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=forms.fields.datetime.date.today)
    class Meta:
        model = Invoice
        fields = ['date', 'customer_name']


ParticularFormSet = inlineformset_factory(
    Invoice, Particular, fields=('description', 'amount'), extra=1, can_delete=True
)



from .models import Worksheet

from .models import Worksheet, ServiceType

class MeesevaWorksheetForm(forms.ModelForm):
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
        fields = ['token_no', 'customer_name', 'customer_mobile', 'service', 'transaction_num', 'certificate_number','payment', 'amount', 'particulars']

class AadharWorksheetForm(forms.ModelForm):
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
        fields = ['token_no', 'customer_name', 'customer_mobile', 'service', 'enrollment_no', 'certificate_number', 'payment', 'amount', 'particulars']

class BhuBharathiWorksheetForm(forms.ModelForm):
    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        # employee is ignored, just for compatibility

    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name',  'login_mobile_no', 'application_no', 'status','payment',  'amount', 'particulars']

# RENAMED from XeroxWorksheetForm
class FormsWorksheetForm(forms.ModelForm):
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
        fields = ['service', 'amount', 'particulars']

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
        fields = ['token_no', 'customer_name', 'customer_mobile', 'service', 'payment', 'amount', 'particulars']

# NEW form for 'Notary and Bonds' department
class NotaryAndBondsWorksheetForm(forms.ModelForm):
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
        fields = ['token_no', 'customer_name', 'service', 'bonds_sno', 'payment', 'amount', 'particulars']

# Form specifically for editing the certificate number
class WorksheetEntryEditForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['certificate_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['certificate_number'].widget.attrs.update({'class': 'form-control'})



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


