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
        fields = ['token_no', 'customer_name', 'service', 'transaction_num', 'certificate_number', 'amount']

class AadharWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name', 'service', 'enrollment_no', 'certificate_number', 'amount']

class BhuBharathiWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['token_no', 'customer_name', 'login_mobile_no', 'application_no', 'status', 'amount']

class XeroxWorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ['particulars', 'amount']



