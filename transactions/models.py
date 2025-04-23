from django.db import models
from django_extensions.db.fields import AutoSlugField
from store.models import Item, Store, StoreInventory
from accounts.models import Vendor, Customer, Profile
from django.db import transaction
import uuid

DELIVERY_CHOICES = [("P", "Pending"), ("S", "Successful")]

class TaxRate(models.Model):
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f" ({self.percentage}%)"

class Sale(models.Model):
    date_added = models.DateTimeField(auto_now_add=True, verbose_name="Sale Date")
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    tax_percentage = models.FloatField(default=0.0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    amount_change = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sales', null=True, blank=True)
    cashier = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True)
    receipt_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases')

    class Meta:
        db_table = "sales"
        verbose_name = "Sale"
        verbose_name_plural = "Sales"
        ordering = ['-date_added']

    def __str__(self):
        return f"Sale ID: {self.id} | Grand Total: {self.grand_total} | Date: {self.date_added}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    def sum_products(self):
        return sum(detail.quantity for detail in self.saledetail_set.all())

class SaleDetail(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, db_column="sale", related_name="saledetail_set")
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, db_column="item")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    total_detail = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "sale_details"
        verbose_name = "Sale Detail"
        verbose_name_plural = "Sale Details"

    def __str__(self):
        return f"Detail ID: {self.id} | Sale ID: {self.sale.id} | Quantity: {self.quantity}"

class PurchaseOrder(models.Model):
    slug = AutoSlugField(unique=True, populate_from="vendor")
    vendor = models.ForeignKey(Vendor, related_name="purchase_orders", on_delete=models.CASCADE)
    order_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateTimeField(blank=True, null=True, verbose_name="Delivery Date")
    delivery_status = models.CharField(choices=DELIVERY_CHOICES, max_length=1, default="P", verbose_name="Delivery Status")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='purchase_orders', null=True, blank=True)
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        return f"Purchase Order {self.id} - {self.vendor.name}"

    def save(self, *args, **kwargs):
        if self.pk:
            original = PurchaseOrder.objects.get(pk=self.pk)
            if original.delivery_status != self.delivery_status and self.delivery_status == 'S':
                for detail in self.details.all():
                    inventory, created = StoreInventory.objects.get_or_create(
                        item=detail.item, store=self.store, defaults={'quantity': 0}
                    )
                    inventory.quantity += detail.quantity
                    inventory.save()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-order_date"]

class PurchaseDetail(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, related_name="details", on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    description = models.TextField(max_length=300, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=0)
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item.name} (Order {self.purchase_order.id})"