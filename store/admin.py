"""
Module: admin.py

Django admin configurations for managing categories, items, and deliveries.

This module defines the following admin classes:
- CategoryAdmin: Configuration for the Category model in the admin interface.
- ItemAdmin: Configuration for the Item model in the admin interface.
- DeliveryAdmin: Configuration for the Delivery model in the admin interface.
"""

from django.contrib import admin
from .models import Category, Item, Store, StoreInventory, StockAlert, Variety
from django.core.exceptions import ValidationError


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



@admin.register(Variety)
class VarietyAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_item', 'price')
    list_filter = ('base_item',)
    search_fields = ('name', 'base_item__name')
    list_per_page = 10

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        queryset = Item.objects.filter(has_varieties=True)
        if not queryset.exists():
            self.message_user(request, "No items with varieties available. Please create an item with 'Has Varieties' enabled.", level='warning')
        form.base_fields['base_item'].queryset = queryset
        return form



class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'contact_number', 'central')
    search_fields = ('name', 'address')
    list_filter = ('central',)
    list_per_page = 10
    ordering = ('name',)
    actions = None  # Disable bulk editing to prevent bypassing validation
    
    def save_model(self, request, obj, form, change):
        try:
            # This will call the model's clean() method
            obj.full_clean()
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            # Display error message in admin
            form.add_error('central', e)
            return

admin.site.register(Store, StoreAdmin)

admin.site.register(Category, CategoryAdmin)
admin.site.register(Item, ItemAdmin)
#admin.site.register(Delivery, DeliveryAdmin)


