from django.db import models
from django_extensions.db.fields import AutoSlugField
from store.models import Item, Store, StoreInventory, Variety
from accounts.models import Vendor, Profile
from django.db import transaction
import uuid
from django.utils import timezone


DELIVERY_CHOICES = [("P", "Pending"), ("S", "Successful")]
MOVEMENT_TYPES = [
    ("OPENING", "Opening Stock"),
    ("PURCHASE", "Purchase"),
    ("SALE", "Sale"),
    ("TRANSFER_OUT", "Transfer Out"),
    ("TRANSFER_IN", "Transfer In"),
    ("USAGE", "Internal Usage"),
    ("ADJUSTMENT", "Manual Adjustment"),
]

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
    # Added method to display customer name or "Walk-in Customer"
    def get_customer_display(self):
        if self.customer:
            return self.customer.name
        else:
            return "Walk-in Customer"

class SaleDetail(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, db_column="sale", related_name="saledetail_set")
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, db_column="item")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    total_detail = models.DecimalField(max_digits=10, decimal_places=2)
    variety = models.ForeignKey(Variety, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        db_table = "sale_details"
        verbose_name = "Sale Detail"
        verbose_name_plural = "Sale Details"

    def __str__(self):
        return f"Detail ID: {self.id} | Sale ID: {self.sale.id} | Quantity: {self.quantity}"
    
# --- New Transfer Model ---
class Transfer(models.Model):
    date_added = models.DateTimeField(auto_now_add=True, verbose_name="Transfer Date")
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='transfers_sent', null=True, blank=True)  # Source store
    destination_store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='transfers_received', null=True, blank=True)  # Target store
    cashier = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True)
    transfer_number = models.CharField(max_length=20, unique=True, editable=False)

    class Meta:
        db_table = "transfers"
        verbose_name = "Transfer"
        verbose_name_plural = "Transfers"
        ordering = ['-date_added']

    def __str__(self):
        return f"Transfer ID: {self.id} | Grand Total: {self.grand_total} | Date: {self.date_added}"

    def save(self, *args, **kwargs):
        if not self.transfer_number:
            self.transfer_number = uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

# --- New TransferDetail Model ---
class TransferDetail(models.Model):
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, db_column="transfer", related_name="transferdetail_set")
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, db_column="item")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    total_detail = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "transfer_details"
        verbose_name = "Transfer Detail"
        verbose_name_plural = "Transfer Details"

    def __str__(self):
        return f"Detail ID: {self.id} | Transfer ID: {self.transfer.id} | Quantity: {self.quantity}"

class PurchaseOrder(models.Model):
    slug = AutoSlugField(unique=True, populate_from="vendor")
    vendor = models.ForeignKey(Vendor, related_name="purchase_orders", on_delete=models.CASCADE)
    order_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateTimeField(blank=True, null=True, verbose_name="Delivery Date")
    delivery_status = models.CharField(choices=DELIVERY_CHOICES, max_length=1, default="P", verbose_name="Delivery Status")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='purchase_orders', null=True, blank=True)
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True)

    

    def __str__(self):
        return f"Purchase Order {self.id} - {self.vendor.name}"

    def save(self, *args, **kwargs):
        """
        Enhanced save:
        - Detect previous delivery_status.
        - After saving, if we just transitioned to 'S' (Successful),
          update inventory quantities and create StockMovement entries.
        """
        previous_status = None
        if self.pk:
            try:
                previous_status = PurchaseOrder.objects.get(pk=self.pk).delivery_status
            except PurchaseOrder.DoesNotExist:
                previous_status = None

        # Save order first (so self.pk exists and we can safely query details)
        super().save(*args, **kwargs)

        # If we transitioned to 'S' from a different status (or from None on first save),
        # apply the inventory changes and log StockMovements.
        if self.delivery_status == 'S' and previous_status != 'S':
            for detail in self.details.all():
                # Update or create the store inventory
                inventory, created = StoreInventory.objects.get_or_create(
                    item=detail.item,
                    store=self.store,
                    defaults={'quantity': 0}
                )
                inventory.quantity += detail.quantity
                inventory.save()

                # Create a unique reference id for this movement (prevents duplicates)
                ref_id = f"PO-{self.id}-PD-{detail.id}"

                # Create StockMovement entry
                StockMovement.objects.create(
                    store=self.store,
                    item=detail.item,
                    variety=None,
                    movement_type="PURCHASE",
                    quantity=detail.quantity,
                    balance_after=inventory.quantity,
                    reference_id=ref_id,
                    performed_by=self.created_by,
                )

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
    

class StockMovement(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="stock_movements")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stock_movements")
    variety = models.ForeignKey(Variety, null=True, blank=True, on_delete=models.SET_NULL, related_name="stock_movements")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()  # + for inflow, - for outflow
    balance_after = models.IntegerField(default=0)  # balance in StoreInventory after movement
    reference_id = models.CharField(max_length=50, blank=True, null=True)  # e.g., sale_id, transfer_id
    performed_by = models.ForeignKey(Profile, null=True, blank=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.movement_type} - {self.item.name} ({self.quantity}) in {self.store.name}"