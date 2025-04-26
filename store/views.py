"""
Module: store.views

Contains Django views for managing items, profiles,
and deliveries in the store application.

Classes handle product listing, creation, updating,
deletion, and delivery management.
The module integrates with Django's authentication
and querying functionalities.
"""

# Standard library imports
import operator
from functools import reduce



# Django core imports
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum,Max
from django.utils import timezone
import json

# Authentication and permissions
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Class-based views
from django.views.generic import (
    DetailView, CreateView, UpdateView, DeleteView, ListView
)
from django.views.generic.edit import FormMixin

# Third-party packages
from django_tables2 import SingleTableView
import django_tables2 as tables
from django_tables2.export.views import ExportMixin

# Local app imports
from accounts.models import Profile, Vendor
from transactions.models import Sale, SaleDetail
from .models import Category, Item,  StoreInventory, StockAlert, Store
from .forms import CategoryForm
from .tables import ItemTable
from django.views.generic import TemplateView
from bills.models import InternalUsage, UsageDetail
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView
from .models import Item, StoreInventory
from .forms import ItemForm
import logging
from datetime import timedelta
from django.forms import formset_factory

from django.views import View


logger = logging.getLogger(__name__)

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


 # Adjust imports as needed

@login_required
def dashboard(request):
    current_store = request.user.store
    profiles = Profile.objects.filter(store=current_store)
    inventories = current_store.inventories.select_related('item')
    items = [inv.item for inv in inventories]
    sales = Sale.objects.filter(store=current_store)

    total_items = sum(inv.quantity for inv in inventories)
    items_count = len(items)
    profiles_count = profiles.count()

    # Daily sales calculations
    today = timezone.now().date()
    daily_sales = Sale.objects.filter(store=current_store, date_added__date=today)
    total_quantity_sold_today = SaleDetail.objects.filter(sale__in=daily_sales).aggregate(total=Sum('quantity'))['total'] or 0
    total_revenue_today = daily_sales.aggregate(total=Sum('grand_total'))['total'] or 0

    # Category counts (unchanged)
    category_counts = Category.objects.annotate(
        item_count=Count('item', filter=Q(item__store_inventories__store=current_store))
    ).values("name", "item_count")
    categories = [cat["name"] for cat in category_counts]
    category_counts_list = [cat["item_count"] for cat in category_counts]

    # Sales over time data
    sale_dates = Sale.objects.filter(store=current_store).values("date_added__date").annotate(
        total_sales=Sum("grand_total")
    ).order_by("date_added__date")
    sale_dates_labels = [date["date_added__date"].strftime("%Y-%m-%d") for date in sale_dates]
    sale_dates_values = [float(date["total_sales"]) for date in sale_dates]

    # NEW: Calculate initial date range (last 30 days) for the chart
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    initial_min_date = last_30_days.strftime("%Y-%m-%d")
    initial_max_date = today.strftime("%Y-%m-%d")

    unread_alerts_count = StockAlert.objects.filter(store_inventory__store=current_store, is_read=False).count()

    context = {
        "items": items,
        "profiles": profiles,
        "profiles_count": profiles_count,
        "items_count": items_count,
        "total_items": total_items,
        "vendors": Vendor.objects.all(),
        "sales": sales,
        "categories": categories,
        "category_counts": category_counts_list,
        "sale_dates_labels": sale_dates_labels,
        "sale_dates_values": sale_dates_values,
        "unread_alerts_count": unread_alerts_count,
        "total_quantity_sold_today": total_quantity_sold_today,
        "total_revenue_today": total_revenue_today,
        # NEW: Add initial date range to context
        "initial_min_date": initial_min_date,
        "initial_max_date": initial_max_date,
    }
    return render(request, "store/dashboard.html", context)


class NotificationListView(LoginRequiredMixin, ListView):
    model = StockAlert
    template_name = 'store/notifications.html'
    context_object_name = 'alerts'

    def get_queryset(self):
        current_store = self.request.user.store
        return StockAlert.objects.filter(store_inventory__store=current_store).order_by('-created_at')

@require_POST
def mark_alert_as_read(request, pk):
    alert = get_object_or_404(StockAlert, pk=pk, store_inventory__store=request.user.store)
    alert.is_read = True
    alert.save()
    return redirect('notifications')

@require_POST
def mark_all_alerts_as_read(request):
    StockAlert.objects.filter(store_inventory__store=request.user.store, is_read=False).update(is_read=True)
    return redirect('notifications')

@require_GET
def get_unread_alerts_count(request):
    if request.user.is_authenticated:
        current_store = request.user.store
        count = StockAlert.objects.filter(store_inventory__store=current_store, is_read=False).count()
        return JsonResponse({'count': count})
    return JsonResponse({'count': 0})

def update_stock_and_check_alert(inventory, quantity_change):
    inventory.quantity += quantity_change
    inventory.save()
    if inventory.quantity < inventory.min_stock_level and not StockAlert.objects.filter(store_inventory=inventory, is_read=False).exists():
        StockAlert.objects.create(store_inventory=inventory)

@require_POST
def delete_alert(request, pk):
    alert = get_object_or_404(StockAlert, pk=pk, store_inventory__store=request.user.store)
    alert.delete()
    return redirect('notifications')


class ProductListView(LoginRequiredMixin, ExportMixin, tables.SingleTableView):
    model = Item
    table_class = ItemTable
    template_name = "store/productslist.html"
    context_object_name = "items"
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset()
        current_store = self.request.user.store
        queryset = queryset.filter(
            store_inventories__store=current_store
        ).distinct()
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_store = self.request.user.store
        items_with_quantities = []
        
        for item in context['items']:
            quantity = 0
            try:
                inventory = StoreInventory.objects.get(
                    store=current_store, 
                    item=item
                )
                quantity = inventory.quantity
            except StoreInventory.DoesNotExist:
                pass
            
            items_with_quantities.append({
                'item': item,
                'quantity': quantity
            })
        
        context['items_with_quantities'] = items_with_quantities
        return context


class ItemSearchListView(ProductListView):
    paginate_by = 10

    def get_queryset(self):
        result = super().get_queryset()
        query = self.request.GET.get("q")
        if query:
            query_list = query.split()
            result = result.filter(
                reduce(
                    operator.and_, 
                    (Q(name__icontains=q) for q in query_list)
                )
            )
        current_store = self.request.user.store
        result = result.filter(store_inventories__store=current_store)
        return result

class ProductDetailView(LoginRequiredMixin, FormMixin, DetailView):
    """
    View class to display detailed information about a product.

    Attributes:
    - model: The model associated with the view.
    - template_name: The HTML template used for rendering the view.
    """

    model = Item
    template_name = "store/productdetail.html"

    def get_success_url(self):
        return reverse("product-detail", kwargs={"slug": self.object.slug})




# ... other imports and views ...
class ProductCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def get(self, request):
        ItemFormSet = formset_factory(ItemForm, extra=1)  # Start with one empty form
        formset = ItemFormSet()
        return render(request, 'store/productcreate.html', {'formset': formset})

    def post(self, request):
        ItemFormSet = formset_factory(ItemForm)
        formset = ItemFormSet(request.POST)
        if formset.is_valid():
            for form in formset:
                if form.has_changed():  # Only save forms with data
                    item = form.save()
                    quantity = form.cleaned_data.get('quantity', 0)
                    min_stock_level = form.cleaned_data.get('min_stock_level', 0)
                    store = request.user.store
                    StoreInventory.objects.create(
                        store=store,
                        item=item,
                        quantity=quantity,
                        min_stock_level=min_stock_level
                    )
            return redirect('productslist')
        return render(request, 'store/productcreate.html', {'formset': formset})

    def test_func(self):
        return self.request.user.is_superuser

class ProductUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Item
    form_class = ItemForm
    template_name = "store/productupdate.html"
    success_url = "/products"

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form):
        response = super().form_valid(form)
        quantity = form.cleaned_data.get('quantity')
        min_stock_level = form.cleaned_data.get('min_stock_level')
        store = self.request.user.store
        inventory, created = StoreInventory.objects.get_or_create(
            store=store,
            item=self.object
        )
        if quantity is not None:
            inventory.quantity = quantity
        if min_stock_level is not None:
            inventory.min_stock_level = min_stock_level
        inventory.save()
        return response

    def get_initial(self):
        initial = super().get_initial()
        store = self.request.user.store
        try:
            inventory = StoreInventory.objects.get(store=store, item=self.object)
            initial['quantity'] = inventory.quantity
            initial['min_stock_level'] = inventory.min_stock_level
        except StoreInventory.DoesNotExist:
            pass
        return initial

class ProductDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Item
    template_name = "store/productdelete.html"
    success_url = "/products"

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        else:
            return False

class CategoryCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Category
    template_name = 'store/category_form.html'
    form_class = CategoryForm
    login_url = 'login'

    def test_func(self):
        return self.request.user.is_superuser

    def get_success_url(self):
        return reverse_lazy('category-detail', kwargs={'pk': self.object.pk})

class CategoryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Category
    template_name = 'store/category_form.html'
    form_class = CategoryForm
    login_url = 'login'

    def test_func(self):
        return self.request.user.is_superuser

    def get_success_url(self):
        return reverse_lazy('category-detail', kwargs={'pk': self.object.pk})

class CategoryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Category
    template_name = 'store/category_confirm_delete.html'
    context_object_name = 'category'
    success_url = reverse_lazy('category-list')
    login_url = 'login'

    def test_func(self):
        return self.request.user.is_superuser


'''class DeliveryListView(LoginRequiredMixin, ExportMixin, tables.SingleTableView):
    model = Delivery
    pagination = 10
    template_name = "store/deliveries.html"
    context_object_name = "deliveries"

    def get_queryset(self):
        queryset = super().get_queryset()
        current_store = self.request.user.store
        return queryset.filter(store=current_store)

class DeliverySearchListView(DeliveryListView):
    """
    View class to search and display a filtered list of deliveries.

    Attributes:
    - paginate_by: Number of items per page for pagination.
    """

    paginate_by = 10

    def get_queryset(self):
        result = super(DeliverySearchListView, self).get_queryset()

        query = self.request.GET.get("q")
        if query:
            query_list = query.split()
            result = result.filter(
                reduce(
                    operator.
                    and_, (Q(customer_name__icontains=q) for q in query_list)
                )
            )
        return result


class DeliveryDetailView(LoginRequiredMixin, DetailView):
    """
    View class to display detailed information about a delivery.

    Attributes:
    - model: The model associated with the view.
    - template_name: The HTML template used for rendering the view.
    """

    model = Delivery
    template_name = "store/deliverydetail.html"


class DeliveryCreateView(LoginRequiredMixin, CreateView):
    """
    View class to create a new delivery.

    Attributes:
    - model: The model associated with the view.
    - fields: The fields to be included in the form.
    - template_name: The HTML template used for rendering the view.
    - success_url: The URL to redirect to upon successful form submission.
    """

    model = Delivery
    form_class = DeliveryForm
    template_name = "store/delivery_form.html"
    success_url = "/deliveries"


class DeliveryUpdateView(LoginRequiredMixin, UpdateView):
    """
    View class to update delivery information.

    Attributes:
    - model: The model associated with the view.
    - fields: The fields to be updated.
    - template_name: The HTML template used for rendering the view.
    - success_url: The URL to redirect to upon successful form submission.
    """

    model = Delivery
    form_class = DeliveryForm
    template_name = "store/delivery_form.html"
    success_url = "/deliveries"


class DeliveryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    View class to delete a delivery.

    Attributes:
    - model: The model associated with the view.
    - template_name: The HTML template used for rendering the view.
    - success_url: The URL to redirect to upon successful deletion.
    """

    model = Delivery
    template_name = "store/productdelete.html"
    success_url = "/deliveries"

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        else:
            return False'''


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'store/category_list.html'
    context_object_name = 'categories'
    paginate_by = 10
    login_url = 'login'


class CategoryDetailView(LoginRequiredMixin, DetailView):
    model = Category
    template_name = 'store/category_detail.html'
    context_object_name = 'category'
    login_url = 'login'





@csrf_exempt
@require_POST
@login_required
def get_items_ajax_view(request):
    if is_ajax(request):
        try:
            term = request.POST.get("term", "")
            data = []
            items = Item.objects.filter(name__icontains=term)
            for item in items[:10]:
                data.append({
                    'id': item.id,
                    'text': item.name,
                    
                    'price': float(item.price),  # Include price from Item model
                })
            return JsonResponse(data, safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Not an AJAX request'}, status=400)



#this are my charts Views
class SalesReportView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'store/sales_report.html'
    context_object_name = 'sales'
    paginate_by = 15

    def get_queryset(self):
        qs = super().get_queryset()
        store_id = self.request.GET.get('store')
        if self.request.user.is_superuser:
            if store_id:
                qs = qs.filter(store_id=store_id)
            else:
                central_store = Store.objects.get(central=True)
                qs = qs.filter(store=central_store)
        else:
            qs = qs.filter(store=self.request.user.store)
        
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            qs = qs.filter(date_added__date__range=[start_date, end_date])
        return qs.order_by('-date_added')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_superuser:
            context['stores'] = Store.objects.all()
            store_id = self.request.GET.get('store')
            if store_id:
                context['selected_store'] = store_id
            else:
                central_store = Store.objects.get(central=True)
                context['selected_store'] = central_store.id
        total_revenue = self.get_queryset().aggregate(total=Sum('grand_total'))['total'] or 0
        context['total_revenue'] = total_revenue
        return context

class UsageReportView(LoginRequiredMixin, ListView):
    model = InternalUsage
    template_name = 'store/usage_report.html'
    context_object_name = 'usages'
    paginate_by = 15

    def get_queryset(self):
        qs = super().get_queryset()
        store_id = self.request.GET.get('store')
        if self.request.user.is_superuser:
            if store_id:
                qs = qs.filter(store_id=store_id)
            else:
                central_store = Store.objects.get(central=True)
                qs = qs.filter(store=central_store)
        else:
            qs = qs.filter(store=self.request.user.store)
        
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            qs = qs.filter(date__date__range=[start_date, end_date])
        return qs.order_by('-date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_superuser:
            context['stores'] = Store.objects.all()
            store_id = self.request.GET.get('store')
            if store_id:
                context['selected_store'] = store_id
            else:
                central_store = Store.objects.get(central=True)
                context['selected_store'] = central_store.id
        context['total_value'] = sum(usage.total_value for usage in self.get_queryset())
        return context

class BranchSalesComparisonView(LoginRequiredMixin, TemplateView):
    template_name = 'store/branch_sales_comparison.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sales = Sale.objects.exclude(store__central=True)
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            sales = sales.filter(date_added__date__range=[start_date, end_date])
        
        branch_sales = sales.values('store__name').annotate(total_sales=Sum('grand_total')).order_by('-total_sales')
        context['branch_sales'] = branch_sales
        context['labels'] = json.dumps([branch['store__name'] for branch in branch_sales])
        context['data'] = json.dumps([float(branch['total_sales']) for branch in branch_sales])
        return context


class PerformanceStatsView(LoginRequiredMixin, TemplateView):
    template_name = 'store/performance_stats.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sales_details = SaleDetail.objects.all()
        store_id = self.request.GET.get('store')
        if store_id:
            sales_details = sales_details.filter(sale__store_id=store_id)
        elif self.request.user.is_superuser:
            central_store = Store.objects.get(central=True)
            sales_details = sales_details.filter(sale__store=central_store)
        else:
            sales_details = sales_details.filter(sale__store=self.request.user.store)
        
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            sales_details = sales_details.filter(sale__date_added__date__range=[start_date, end_date])
        
        best_selling = sales_details.values('item__name').annotate(
            total_quantity=Sum('quantity'),
            last_sale_date=Max('sale__date_added')
        ).order_by('-total_quantity')[:5]
        
        today = timezone.now().date()
        for item in best_selling:
            if item['last_sale_date']:
                item['days_since_last_sale'] = (today - item['last_sale_date'].date()).days
            else:
                item['days_since_last_sale'] = None
        
        context['best_selling'] = best_selling
        if self.request.user.is_superuser:
            context['stores'] = Store.objects.all()
            context['selected_store'] = store_id if store_id else central_store.id
        return context
    



from django.views.generic import TemplateView
from django.core.exceptions import PermissionDenied

class RestrictedView(UserPassesTestMixin, TemplateView):
    template_name = "403.html"

    def test_func(self):
        return self.request.user.is_superuser  # Only superusers pass