# internal_usage/tables.py
import django_tables2 as tables
from .models import InternalUsage

class InternalUsageTable(tables.Table):
    """Table view for displaying internal stock usage records."""
    class Meta:
        """Meta options for the InternalUsageTable."""
        model = InternalUsage
        template_name = "django_tables2/semantic.html"
        fields = (
            'id',
            'user',
            'date',
            'store',
            'description',
        )
        order_by_field = 'sort'