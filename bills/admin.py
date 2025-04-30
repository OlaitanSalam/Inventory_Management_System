from django.contrib import admin
from .models import InternalUsage, UsageDetail

class UsageDetailInline(admin.TabularInline):
    model = UsageDetail
    extra = 0
    fields = ('usage', 'item', 'quantity', 'price_per_item', 'total_price')

@admin.register(InternalUsage)
class InternalUsageAdmin(admin.ModelAdmin):
    fields = ('user', 'store', 'description',)
    readonly_fields = ('date',)
    list_display = ('user', 'date', 'store', 'description',)
    list_per_page = 15
    inlines = [UsageDetailInline]

@admin.register(UsageDetail)
class UsageDetailAdmin(admin.ModelAdmin):
    fields = ('usage', 'item', 'quantity',)
    list_display = ('usage', 'item', 'quantity',)
    list_per_page = 15