from django import forms

from .models import PurchaseOrder, PurchaseDetail

class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['vendor', 'delivery_date', 'delivery_status']
        widgets = {
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'delivery_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'delivery_status': forms.Select(attrs={'class': 'form-control'}),
        }

class PurchaseDetailForm(forms.ModelForm):
    class Meta:
        model = PurchaseDetail
        fields = ['item', 'quantity', 'total_value']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class BootstrapMixin(forms.ModelForm):
    """
    A mixin to add Bootstrap classes to form fields.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


