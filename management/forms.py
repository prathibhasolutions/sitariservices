from django import forms
from .models import Invoice, Particular
from django.forms import inlineformset_factory,formset_factory


class InvoiceForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=forms.fields.datetime.date.today)
    class Meta:
        model = Invoice
        fields = ['date', 'customer_name']

ParticularFormSet = inlineformset_factory(
    Invoice, Particular, fields=('description', 'amount'), extra=1, can_delete=True
)


from django import forms
from .models import Worksheet

class MeesevaWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name', 'customer_mobile', 'service', 'transaction_num', 'certificate_number','payment', 'amount']

class AadharWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name', 'customer_mobile', 'service', 'enrollment_no', 'certificate_number', 'payment', 'amount']

class BhuBharathiWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name',  'login_mobile_no', 'application_no', 'status','payment',  'amount']

# RENAMED from XeroxWorksheetForm
class FormsWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['particulars', 'amount']

# NEW form for the new 'Xerox' department (without 'particulars')
class XeroxWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['amount']

# NEW form for 'Notary and Bonds' department
class NotaryAndBondsWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name', 'service', 'bonds_sno', 'payment', 'amount']

# Form specifically for editing the certificate number
class WorksheetEntryEditForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['certificate_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['certificate_number'].widget.attrs.update({'class': 'form-control'})


from django import forms
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



# management/forms.py
from django import forms
from .models import EmployeeUpload, UploadService

class EmployeeUploadForm(forms.ModelForm):
    # Explicitly define the service field to add a placeholder
    service = forms.ModelChoiceField(
        queryset=UploadService.objects.all(),
        empty_label="-- Select a Service --",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = EmployeeUpload
        # Define the order of fields in the form
        fields = ['service', 'description', 'file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }



# your_app/forms.py

from django import forms
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


# your_app/forms.py

from django import forms
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


from django import forms
from .models import Employee

class EmployeeAdminForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = '__all__'  # Include all fields
        widgets = {
            # THIS IS THE KEY: Replace the default widget with a simple one
            'profile_picture': forms.FileInput,
        }


from django import forms
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

