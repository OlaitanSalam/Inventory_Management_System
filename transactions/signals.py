from django.db.models.signals import post_save
from django.dispatch import receiver
from store.models import StoreInventory
from .models import PurchaseOrder

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