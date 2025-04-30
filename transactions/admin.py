from django.contrib import admin
from .models import Sale, SaleDetail, PurchaseOrder, PurchaseDetail, TaxRate, Transfer, TransferDetail

class SaleDetailInline(admin.TabularInline):
    model = SaleDetail
    extra = 0
    fields = ('item', 'price', 'quantity', 'total_detail')
    
class PurchaseDetailInline(admin.TabularInline):
    model = PurchaseDetail
    extra = 0
    fields = ('item',  'quantity', 'total_value')
    

class TransferDetailInline(admin.TabularInline):
    """
    Inline admin configuration for TransferDetail, allowing transfer items to be edited
    directly within the Transfer admin interface.
    """
    model = TransferDetail
    extra = 0  # No extra empty forms by default
    fields = ('item', 'price', 'quantity', 'total_detail')  # Fields to display
    verbose_name = "Transfer Item"  # Singular name for clarity
    verbose_name_plural = "Transfer Items"  # Plural name for clarity
    

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


# --- New Admin Configuration for Transfer ---
@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Transfer model, providing a comprehensive interface
    for managing store-to-store transfers in the admin panel.
    
    Features:
    - Displays key transfer details in the list view.
    - Supports searching by transfer number, cashier, or store names.
    - Allows filtering by date, source store, destination store, or cashier.
    - Includes inline editing for TransferDetail via TransferDetailInline.
    - Organizes fields into logical fieldsets for clarity.
    """
    list_display = (
        'store', 'date_added', 'destination_store', 'grand_total',
         'cashier', 'transfer_number'
    )  # Fields shown in the list view
    search_fields = (
        'id', 'transfer_number', 'cashier__first_name', 'cashier__last_name',
        'store__name', 'destination_store__name'
    )  # Fields searchable in admin
    list_filter = ('date_added', 'store', 'destination_store', 'cashier')  # Filter options
    ordering = ('-date_added',)  # Default sorting by newest first
    readonly_fields = ('date_added', 'transfer_number')  # Prevent editing of auto-generated fields
    inlines = [TransferDetailInline]  # Include inline TransferDetail editing
    date_hierarchy = 'date_added'  # Allow date-based navigation
    list_per_page = 15  # Consistent pagination with other models

    fieldsets = (
        (None, {
            'fields': ('store', 'destination_store', 'cashier', 'transfer_number'),
            'description': 'Core details of the transfer, including source and destination stores.'
        }),
        ('Financial Details', {
            'fields': ('sub_total',  'grand_total', ),
            'description': 'Financial information related to the transfer.'
        }),
        ('Timestamps', {
            'fields': ('date_added',),
            'description': 'Timestamp of when the transfer was created.'
        }),
    )

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