# internal_usage/admin.py
from django.contrib import admin
from .models import InternalUsage, UsageDetail

@admin.register(InternalUsage)
class InternalUsageAdmin(admin.ModelAdmin):
    """Admin interface for managing InternalUsage instances."""
    fields = (
        'user',
        'store',
        'description',
    )
    readonly_fields = ('date',)
    list_display = (
        'id',
        'user',
        'date',
        'store',
        'description',
    )

@admin.register(UsageDetail)
class UsageDetailAdmin(admin.ModelAdmin):
    """Admin interface for managing UsageDetail instances."""
    fields = (
        'usage',
        'item',
        'quantity',
    )
    list_display = (
        'usage',
        'item',
        'quantity',
    )