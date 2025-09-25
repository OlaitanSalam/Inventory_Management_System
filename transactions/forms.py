# forms.py
from django import forms
from .models import PurchaseOrder, PurchaseDetail

class BootstrapMixin:
    """
    Adds 'form-control' (and preserves existing classes) to all widgets
    so Django forms look like Bootstrap inputs.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            existing = field.widget.attrs.get("class", "")
            # ensure we don't duplicate class
            classes = existing.split()
            if "form-control" not in classes:
                classes.append("form-control")
            field.widget.attrs["class"] = " ".join(classes).strip()


class PurchaseOrderForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["vendor", "delivery_date", "delivery_status"]
        widgets = {
            "vendor": forms.Select(),
            "delivery_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "delivery_status": forms.Select(),
        }


class PurchaseDetailForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PurchaseDetail
        fields = ["item", "quantity", "total_value"]
        widgets = {
            "item": forms.Select(),
            "quantity": forms.NumberInput(),
            "total_value": forms.NumberInput(attrs={"step": "0.01"}),
        }
