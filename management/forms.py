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

class XeroxWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['particulars', 'amount']


# In your forms.py file

from django import forms
from .models import Worksheet

# ... (your other forms like MeesevaWorksheetForm are here) ...

# NEW: Create a form specifically for editing the certificate number
class WorksheetEntryEditForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        # This is the key: only include the fields you want to be editable
        fields = ['certificate_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional: Add Bootstrap class for styling
        self.fields['certificate_number'].widget.attrs.update({'class': 'form-control'})



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
