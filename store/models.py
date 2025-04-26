"""
Module: models.py

Contains Django models for handling categories, items, and deliveries.

This module defines the following classes:
- Category: Represents a category for items.
- Item: Represents an item in the inventory.
- Delivery: Represents a delivery of an item to a customer.

Each class provides specific fields and methods for handling related data.
"""

from django.db import models
from django.urls import reverse
from django.forms import model_to_dict
from django_extensions.db.fields import AutoSlugField
from phonenumber_field.modelfields import PhoneNumberField
from django.db.models import functions





class Store(models.Model):
    """
    Represents a physical or logical store.
    The 'central' flag is used to mark the admin’s central store.
    """
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    contact_number = models.CharField(max_length=15, blank=True)
    central = models.BooleanField(default=False)  # Indicates the central store (admin's primary)

    def __str__(self):
        return self.name



class Category(models.Model):
    """
    Represents a category for items.
    """
    name = models.CharField(max_length=50)
    slug = AutoSlugField(unique=True, populate_from='name')

    def __str__(self):
        """
        String representation of the category.
        """
        return f"Category: {self.name}"
    

    class Meta:
        verbose_name_plural = 'Categories'


class Item(models.Model):
    """
    Represents an item in the inventory.
    """
    slug = AutoSlugField(unique=True, populate_from='name')
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=256)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    price = models.FloatField(default=0)
    purchase_price = models.FloatField(
        default=0,
        verbose_name="Purchase Price",
        help_text="Cost per one unit (e.g., per item)"
    )
    expiring_date = models.DateTimeField(null=True, blank=True)
 
    

    def __str__(self):
        """
        String representation of the item.
        """
        return (
            f"{self.name} -  {self.category}, "
            
        )

    def get_absolute_url(self):
        """
        Returns the absolute URL for an item detail view.
        """
        return reverse('item-detail', kwargs={'slug': self.slug})

    def to_json(self):
        product = model_to_dict(self)
        product['id'] = self.id
        product['text'] = self.name
        product['category'] = self.category.name
        product['quantity'] = 1
        product['total_product'] = 0
        return product

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Items'

    class Meta:
        constraints = [
            models.UniqueConstraint(
                functions.Lower('name'),
                name='unique_item_name_insensitive'
            )
        ]
    


"""class Delivery(models.Model):
   
    # Represents a delivery of an item to a customer.
    
    item = models.ForeignKey(
        Item, blank=True, null=True, on_delete=models.SET_NULL
    )
    customer_name = models.CharField(max_length=30, blank=True, null=True)
    phone_number = PhoneNumberField(blank=True, null=True)
    location = models.CharField(max_length=20, blank=True, null=True)
    date = models.DateTimeField()
    is_delivered = models.BooleanField(
        default=False, verbose_name='Is Delivered'
    )
    store = models.ForeignKey(
        Store, 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='deliveries'
    )
    
    def save(self, *args, **kwargs):
        # Auto-set store from item if not set
        if not self.store and self.item:
            inventory = self.item.store_inventories.first()
            if inventory:
                self.store = inventory.store
        super().save(*args, **kwargs)

    def __str__(self):
        
        #String representation of the delivery.
        
        return (
            f"Delivery of {self.item} to {self.customer_name} "
            f"at {self.location} on {self.date}"
        )"""


# store/models.py
# ... (existing imports and models: Store, Category, Item, Delivery)

class StoreInventory(models.Model):
    """
    Represents the store-specific inventory record for an Item.
    Each record links a global item to a particular store with its own quantity.
    """
    store = models.ForeignKey(
        Store, 
        on_delete=models.CASCADE, 
        related_name='inventories'
    )
    item = models.ForeignKey(
        Item, 
        on_delete=models.CASCADE, 
        related_name='store_inventories'
    )
    quantity = models.IntegerField(default=0)
    min_stock_level = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('store', 'item')  # Ensures one record per item per store.
        verbose_name_plural = 'Store Inventories'

    def __str__(self):
        return f"{self.item.name} in {self.store.name}: {self.quantity}"
    
class StockAlert(models.Model):
    store_inventory = models.ForeignKey(StoreInventory, on_delete=models.CASCADE, related_name='alerts')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def get_recommendation(self):
        if self.store_inventory.store.central:
            return "Place a requisition to the vendor."
        else:
            return "Place a requisition to the central store."

    def __str__(self):
        return f"Alert for {self.store_inventory.item.name} in {self.store_inventory.store.name}"
