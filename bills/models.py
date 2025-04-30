from django.db import models
from django.conf import settings
from store.models import Store, Item, StoreInventory

class InternalUsage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    description = models.CharField(max_length=255, blank=True, null=True)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        # Only generate slug for new objects (no id yet)
        is_new = self.id is None
        super().save(*args, **kwargs)
        if is_new and not self.slug:
            self.slug = f"usage-{self.id}"
            # Use update_fields to avoid full save and potential conflicts
            self.save(update_fields=['slug'])

    def total_quantity(self):
        return sum(detail.quantity for detail in self.details.all())
    
    @property
    def total_value(self):
        # Sum the total_price from each related UsageDetail
        return sum(detail.total_price for detail in self.details.all())

    def __str__(self):
        return f"Usage {self.id} by {self.user.first_name} on {self.date}"

class UsageDetail(models.Model):
    usage = models.ForeignKey(InternalUsage, on_delete=models.CASCADE, related_name='details')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price_per_item = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.price_per_item
        super().save(*args, **kwargs)