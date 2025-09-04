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


class WorksheetParticularForm(forms.Form):
    ticket_no = forms.CharField(label='Tk.No', max_length=50)
    customer_name = forms.CharField(max_length=255)
    service = forms.CharField(max_length=255)
    transaction_no = forms.CharField(required=False, max_length=255)
    certificate_no = forms.CharField(required=False, max_length=255)
    amount = forms.DecimalField(max_digits=10, decimal_places=2)

WorksheetParticularFormSet = formset_factory(WorksheetParticularForm, extra=1)


