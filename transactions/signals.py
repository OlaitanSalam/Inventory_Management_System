from django.db.models.signals import post_save
from django.dispatch import receiver
from store.models import StoreInventory
from .models import PurchaseOrder
from .models import SaleDetail, TransferDetail, PurchaseDetail, StockMovement
from accounts.models import Profile

@receiver(post_save, sender=PurchaseOrder)
def update_item_quantity(sender, instance, created, **kwargs):
    """
    Signal to update store inventory when a purchase is made.
    """
   # if created:
        # Get or create the inventory record for this item in the purchase's store
       # inventory, created = StoreInventory.objects.get_or_create(
           # item=instance.item,
            #store=instance.store,
            #defaults={'quantity': 0}
        #)
        
        # Update the inventory quantity
        #inventory.quantity += instance.quantity
        #inventory.save()

def log_stock_movement(store, item, variety, movement_type, quantity, reference_id, performed_by):
    inventory = StoreInventory.objects.filter(store=store, item=item).first()
    balance = inventory.quantity if inventory else 0

    StockMovement.objects.create(
        store=store,
        item=item,
        variety=variety,
        movement_type=movement_type,
        quantity=quantity,
        balance_after=balance,
        reference_id=str(reference_id),
        performed_by=performed_by,
    )

# ---- SALE ----
@receiver(post_save, sender=SaleDetail)
def log_sale_detail(sender, instance, created, **kwargs):
    if created:
        log_stock_movement(
            store=instance.sale.store,
            item=instance.item,
            variety=instance.variety,
            movement_type="SALE",
            quantity=-instance.quantity,
            reference_id=instance.sale.id,
            performed_by=instance.sale.cashier,
        )

# ---- TRANSFER ----
@receiver(post_save, sender=TransferDetail)
def log_transfer_detail(sender, instance, created, **kwargs):
    if created:
        # Outflow from source
        log_stock_movement(
            store=instance.transfer.store,
            item=instance.item,
            variety=None,
            movement_type="TRANSFER_OUT",
            quantity=-instance.quantity,
            reference_id=instance.transfer.id,
            performed_by=instance.transfer.cashier,
        )
        # Inflow to destination
        log_stock_movement(
            store=instance.transfer.destination_store,
            item=instance.item,
            variety=None,
            movement_type="TRANSFER_IN",
            quantity=instance.quantity,
            reference_id=instance.transfer.id,
            performed_by=instance.transfer.cashier,
        )

# ---- PURCHASE ----
# transactions/signals.py (replace the PurchaseDetail receiver)
@receiver(post_save, sender=PurchaseDetail)
def log_purchase_detail(sender, instance, created, **kwargs):
    """
    Create a StockMovement when a PurchaseDetail is created AND the parent
    purchase_order is already 'S'. Guarded to avoid duplicates.
    Note: normal flow (create order as P, add details, then set to S) will be handled
    by PurchaseOrder.save() — this handler only deals with the rare case where a
    PurchaseDetail is created after the order is already Successful.
    """
    if created and instance.purchase_order.delivery_status == "S":
        # Construct the same reference id pattern used by PurchaseOrder.save()
        ref_id = f"PO-{instance.purchase_order.id}-PD-{instance.id}"
        # Avoid creating duplicate StockMovement entries
        exists = StockMovement.objects.filter(reference_id=ref_id, item=instance.item, movement_type="PURCHASE").exists()
        if not exists:
            log_stock_movement(
                store=instance.purchase_order.store,
                item=instance.item,
                variety=None,
                movement_type="PURCHASE",
                quantity=instance.quantity,
                reference_id=ref_id,
                performed_by=instance.purchase_order.created_by,
            )


# ---- OPENING STOCK ----
@receiver(post_save, sender=StoreInventory)
def log_opening_stock(sender, instance, created, **kwargs):
    if created and instance.quantity > 0:
        log_stock_movement(
            store=instance.store,
            item=instance.item,
            variety=None,
            movement_type="OPENING",
            quantity=instance.quantity,
            reference_id=f"INV-{instance.id}",
            performed_by=None,
        )