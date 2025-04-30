import json
from django.shortcuts import render
from django.http import JsonResponse
from django.urls import reverse
from django.db import transaction
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, UpdateView, DeleteView, DetailView
from .models import InternalUsage, UsageDetail
from store.models import Item, StoreInventory

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

class InternalUsageListView(LoginRequiredMixin, ListView):
    model = InternalUsage
    template_name = 'bills/usage_list.html'
    context_object_name = 'usages'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            qs = qs.filter(store=self.request.user.store)
        return qs.order_by('-date')

def InternalUsageCreateView(request):
    if request.method == 'POST':
        if is_ajax(request):
            try:
                data = json.loads(request.body)
                description = data.get('description', '')
                items = data['items']
                if not items:
                    raise ValueError("No items provided")
                with transaction.atomic():
                    usage = InternalUsage.objects.create(
                        user=request.user,
                        store=request.user.store,
                        description=description
                    )
                    for item_data in items:
                        item = Item.objects.get(id=item_data['id'])
                        quantity = int(item_data['quantity'])
                        price_per_item = float(item_data['price_per_item'])
                        inventory = StoreInventory.objects.get(item=item, store=usage.store)
                        if inventory.quantity < quantity:
                            raise ValueError(f"Not enough stock for {item.name}")
                        UsageDetail.objects.create(
                            usage=usage,
                            item=item,
                            quantity=quantity,
                            price_per_item=price_per_item,
                            total_price=quantity * price_per_item
                        )
                        inventory.quantity -= quantity
                        inventory.save()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Usage recorded successfully',
                    'redirect': reverse('usage_list')
                })
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return render(request, 'bills/usage_create.html')

class InternalUsageUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = InternalUsage
    fields = ['description']
    template_name = 'bills/usage_update.html'

    def test_func(self):
        usage = self.get_object()
        return self.request.user.is_superuser or usage.store == self.request.user.store

    def get_success_url(self):
        return reverse('usage_list')

class InternalUsageDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = InternalUsage
    template_name = 'bills/usage_delete.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_success_url(self):
        return reverse('usage_list')

class InternalUsageDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = InternalUsage
    template_name = 'bills/usage_detail.html'
    context_object_name = 'usage'

    def test_func(self):
        usage = self.get_object()
        return self.request.user.is_superuser or usage.store == self.request.user.store