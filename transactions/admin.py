from django.contrib import admin
from .models import Sale, SaleDetail, PurchaseOrder, PurchaseDetail, TaxRate

class SaleDetailInline(admin.TabularInline):
    model = SaleDetail
    extra = 0
    fields = ('item', 'price', 'quantity', 'total_detail')
    readonly_fields = ('total_detail',)
class PurchaseDetailInline(admin.TabularInline):
    model = PurchaseDetail
    extra = 0
    fields = ('item',  'quantity', 'total_value')
    readonly_fields = ('item',  'quantity', 'total_value')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('store', 'date_added', 'grand_total','get_customer_display', 'amount_paid', 'amount_change', 'cashier', 'receipt_number', 'customer')
    search_fields = ('id', 'receipt_number', 'cashier__first_name', 'cashier__last_name', 'store__name', 'customer__name')
    list_filter = ('date_added', 'store', 'cashier', 'customer')
    ordering = ('-date_added',)
    readonly_fields = ('date_added', 'receipt_number')
    inlines = [SaleDetailInline]
    date_hierarchy = 'date_added'
    list_per_page = 15

    def get_customer_display(self, obj):
        return obj.get_customer_display()
    get_customer_display.short_description = 'Customer'

    fieldsets = (
        (None, {
            'fields': ('store', 'cashier', 'receipt_number', 'customer')
        }),
        ('Financial Details', {
            'fields': ('sub_total', 'tax_amount', 'tax_percentage', 'grand_total', 'amount_paid', 'amount_change')
        }),
        ('Timestamps', {
            'fields': ('date_added',)
        }),
    )

'''@admin.register(SaleDetail)
class SaleDetailAdmin(admin.ModelAdmin):
    list_display = ('id', 'sale', 'item', 'price', 'quantity', 'total_detail')
    search_fields = ('sale__id', 'item__name')
    list_filter = ('sale', 'item')
    ordering = ('sale', 'item')'''

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ( 'vendor', 'order_date', 'delivery_date', 'delivery_status', 'total_value', 'slug')
    search_fields = ('vendor__name', 'slug')
    list_filter = ('order_date', 'delivery_status', 'store')
    ordering = ('-order_date',)
    inlines = [PurchaseDetailInline]
    list_per_page = 15



'''@admin.register(PurchaseDetail)
class PurchaseDetailAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'item', 'quantity', 'total_value')
    search_fields = ('item__name',)
    list_filter = ('purchase_order',)'''

@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ('id', 'percentage')
    search_fields = ('percentage',)
    ordering = ('percentage',)
    list_per_page = 10