# bills/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UsageDetail
from store.models import StoreInventory
from transactions.models import StockMovement


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


# --- INTERNAL USAGE ---
@receiver(post_save, sender=UsageDetail)
def log_internal_usage(sender, instance, created, **kwargs):
    """
    Logs stock movement whenever an InternalUsage detail is created.
    Fixes:
    - Correctly fetches updated inventory for accurate balance_after
    - Ensures performed_by is set to usage.user
    """
    if created:
        # Make sure inventory balance is recalculated after deduction
        inventory = StoreInventory.objects.filter(store=instance.usage.store, item=instance.item).first()
        balance = inventory.quantity if inventory else 0

        StockMovement.objects.create(
            store=instance.usage.store,
            item=instance.item,
            variety=None,
            movement_type="USAGE",
            quantity=-instance.quantity,   # outflow
            balance_after=balance,         # current stock after deduction
            reference_id=f"USAGE-{instance.usage.id}",
            performed_by=instance.usage.user,  # FIX: track the user who did it
        )
