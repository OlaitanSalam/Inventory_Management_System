"""
Module: admin.py

Django admin configurations for managing categories, items, and deliveries.

This module defines the following admin classes:
- CategoryAdmin: Configuration for the Category model in the admin interface.
- ItemAdmin: Configuration for the Item model in the admin interface.
- DeliveryAdmin: Configuration for the Delivery model in the admin interface.
"""

from django.contrib import admin
from .models import Category, Item, Store, StoreInventory, StockAlert


class CategoryAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Category model.
    """
    list_display = ('name', 'slug')
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 10


class ItemAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Item model.
    """
    list_display = (
        'name', 'category',  'price', 'expiring_date'
    )
    search_fields = ('name', 'category__name')
    list_filter = ('category', )
    ordering = ('name',)
    list_per_page = 10


"""class DeliveryAdmin(admin.ModelAdmin):
    
    #Admin configuration for the Delivery model.
    
    list_display = (
        'item', 'customer_name', 'phone_number',
        'location', 'date', 'is_delivered'
    )
    search_fields = ('item__name', 'customer_name')
    list_filter = ('is_delivered', 'date')
    ordering = ('-date',)"""

@admin.register(StoreInventory)
class StoreInventoryAdmin(admin.ModelAdmin):
    list_display = ('store', 'item', 'quantity', 'min_stock_level')
    list_filter = ('store', 'item__category')
    search_fields = ('item__name', 'store__name')
    list_per_page = 15
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Customize the item queryset if needed
        return form

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('store_inventory', 'created_at', 'is_read')
    list_filter = ('is_read', 'store_inventory__store')
    list_per_page = 15
admin.site.register(Category, CategoryAdmin)
admin.site.register(Item, ItemAdmin)
#admin.site.register(Delivery, DeliveryAdmin)
admin.site.register(Store)
