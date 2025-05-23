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
from transactions.models import Sale, SaleDetail,Transfer,TransferDetail
from .models import Category, Item,  StoreInventory, StockAlert, Store
from .tables import ItemTable
from django.views.generic import TemplateView
from bills.models import InternalUsage, UsageDetail
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView
from .models import Item, StoreInventory
from .forms import ItemForm, CategoryForm, AddExistingItemForm
import logging
from datetime import timedelta
from django.forms import formset_factory
import pandas as pd
from django.contrib import messages
from django.views import View


logger = logging.getLogger(__name__)

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


 # Adjust imports as needed

@login_required
def dashboard(request):
    if not hasattr(request.user, 'store') or request.user.store is None:
        return render(request, 'store/no_store.html', {
            'message': 'No store is associated with your account. Please contact the administrator.'
        })

    current_store = request.user.store
    is_central_store = current_store.central

    profiles = Profile.objects.filter(store=current_store)
    inventories = current_store.inventories.select_related('item')
    items = [inv.item for inv in inventories]
    total_items = sum(inv.quantity for inv in inventories)
    items_count = len(items)
    profiles_count = profiles.count()

    today = timezone.now().date()

    if is_central_store:
        # Central store: Calculate transfer metrics
        daily_transfers = Transfer.objects.filter(store=current_store, date_added__date=today)
        total_quantity_transferred_today = TransferDetail.objects.filter(transfer__in=daily_transfers).aggregate(total=Sum('quantity'))['total'] or 0
        total_transfer_revenue_today = daily_transfers.aggregate(total=Sum('grand_total'))['total'] or 0
    else:
        # Branch store: Calculate sales metrics
        daily_sales = Sale.objects.filter(store=current_store, date_added__date=today)
        total_quantity_sold_today = SaleDetail.objects.filter(sale__in=daily_sales).aggregate(total=Sum('quantity'))['total'] or 0
        total_sales_revenue_today = daily_sales.aggregate(total=Sum('grand_total'))['total'] or 0

    # Other context data (unchanged)
    category_counts = Category.objects.annotate(
        item_count=Count('item', filter=Q(item__store_inventories__store=current_store))
    ).values("name", "item_count")
    categories = [cat["name"] for cat in category_counts]
    category_counts_list = [cat["item_count"] for cat in category_counts]

    # Line chart data based on store type
    if is_central_store:
        transfer_dates = Transfer.objects.filter(store=current_store).values("date_added__date").annotate(
            total_transfers=Sum("grand_total")
        ).order_by("date_added__date")
        chart_title = "Daily Transfers"
        chart_labels = [date["date_added__date"].strftime("%Y-%m-%d") for date in transfer_dates]
        chart_values = [float(date["total_transfers"]) for date in transfer_dates]
    else:
        sale_dates = Sale.objects.filter(store=current_store).values("date_added__date").annotate(
            total_sales=Sum("grand_total")
        ).order_by("date_added__date")
        chart_title = "Daily Sales"
        chart_labels = [date["date_added__date"].strftime("%Y-%m-%d") for date in sale_dates]
        chart_values = [float(date["total_sales"]) for date in sale_dates]

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
        "categories": categories,
        "category_counts": category_counts_list,
        "chart_title": chart_title,
        "chart_labels": json.dumps(chart_labels),  # JSON-safe for JavaScript
        "chart_values": json.dumps(chart_values),  # JSON-safe for JavaScript
        "unread_alerts_count": unread_alerts_count,
        "initial_min_date": initial_min_date,
        "initial_max_date": initial_max_date,
        "is_central_store": is_central_store,
    }

    if is_central_store:
        context.update({
            "total_quantity_transferred_today": total_quantity_transferred_today,
            "total_transfer_revenue_today": total_transfer_revenue_today,
        })
    else:
        context.update({
            "total_quantity_sold_today": total_quantity_sold_today,
            "total_sales_revenue_today": total_sales_revenue_today,
        })

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
    model = Sale  # Base model, but we'll override get_queryset
    template_name = 'store/sales_report.html'
    context_object_name = 'transactions'  # Use a generic name for both sales and transfers
    paginate_by = 15

    def get_queryset(self):
        store_id = self.request.GET.get('store')
        if self.request.user.is_superuser:
            if store_id:
                selected_store = Store.objects.get(id=store_id)
            else:
                selected_store = Store.objects.get(central=True)
        else:
            selected_store = self.request.user.store

        # Fetch transfers for central store, sales for others
        if selected_store.central:
            qs = Transfer.objects.filter(store=selected_store)
        else:
            qs = Sale.objects.filter(store=selected_store)

        # Apply date filters
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            qs = qs.filter(date_added__date__range=[start_date, end_date])

        return qs.order_by('-date_added')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store_id = self.request.GET.get('store')
        if self.request.user.is_superuser:
            if store_id:
                selected_store = Store.objects.get(id=store_id)
            else:
                selected_store = Store.objects.get(central=True)
        else:
            selected_store = self.request.user.store

        # Indicate if data is transfers or sales
        context['is_transfer'] = selected_store.central
        # Calculate total revenue (works for both models since both have grand_total)
        context['total_revenue'] = self.get_queryset().aggregate(total=Sum('grand_total'))['total'] or 0

        if self.request.user.is_superuser:
            context['stores'] = Store.objects.all()
            context['selected_store'] = selected_store.id

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
        store_id = self.request.GET.get('store')
        if self.request.user.is_superuser:
            if store_id:
                selected_store = Store.objects.get(id=store_id)
            else:
                selected_store = Store.objects.get(central=True)
        else:
            selected_store = self.request.user.store

        # Fetch details based on store type
        if selected_store.central:
            details = TransferDetail.objects.filter(transfer__store=selected_store)
            date_field = 'transfer__date_added'
        else:
            details = SaleDetail.objects.filter(sale__store=selected_store)
            date_field = 'sale__date_added'

        # Apply date filters
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            details = details.filter(**{f'{date_field}__date__range': [start_date, end_date]})

        # Aggregate best-selling or most-transferred items
        if selected_store.central:
            best_selling = details.values('item__name').annotate(
                total_quantity=Sum('quantity'),
                last_date=Max('transfer__date_added')
            ).order_by('-total_quantity')[:5]
        else:
            best_selling = details.values('item__name').annotate(
                total_quantity=Sum('quantity'),
                last_date=Max('sale__date_added')
            ).order_by('-total_quantity')[:5]

        # Calculate days since last transaction
        today = timezone.now().date()
        for item in best_selling:
            if item['last_date']:
                item['days_since_last'] = (today - item['last_date'].date()).days
            else:
                item['days_since_last'] = None

        context['best_selling'] = best_selling
        context['is_central'] = selected_store.central
        if self.request.user.is_superuser:
            context['stores'] = Store.objects.all()
            context['selected_store'] = selected_store.id

        return context
    


# new view for 403 error page
from django.views.generic import TemplateView
from django.core.exceptions import PermissionDenied

class RestrictedView(UserPassesTestMixin, TemplateView):
    template_name = "403.html"

    def test_func(self):
        return self.request.user.is_superuser  # Only superusers pass
    

# new view for bulk item upload
class BulkItemUploadView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'store/bulk_item_upload.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        if 'file' not in request.FILES:
            messages.error(request, "No file uploaded.")
            return render(request, self.template_name)

        file = request.FILES['file']
        store = request.user.store

        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            inventories_to_create = []
            processed_names = set()  # Track names in the current CSV batch

            for index, row in df.iterrows():
                # Handle category (check for NaN)
                category_value = row.get('category', '')
                if pd.isna(category_value):
                    category_value = ''
                category_name = str(category_value).strip()
                
                if not category_name:
                    messages.error(request, f"Row {index + 2}: Missing category.")
                    continue

                # Handle name and description (check for NaN)
                name = row.get('name', '')
                if pd.isna(name):
                    name = ''
                name = str(name).strip()

                description = row.get('description', '')
                if pd.isna(description):
                    description = ''
                description = str(description).strip()

                # Handle expiring_date (check for NaN)
                expiring_date = row.get('expiring_date')
                if pd.isna(expiring_date):
                    expiring_date = None

                # Check for duplicates in the current CSV batch (case-insensitive)
                name_lower = name.lower()
                if name_lower in processed_names:
                    messages.error(request, f"Row {index + 2}: Duplicate item '{name}' in the file.")
                    continue

                # Get or create category
                try:
                    category = Category.objects.get(name__iexact=category_name)
                except Category.DoesNotExist:
                    category = Category.objects.create(
                        name=category_name, 
                        slug=category_name.lower().replace(' ', '-')
                    )

                # Check if item exists (case-insensitive)
                try:
                    item = Item.objects.get(name__iexact=name)
                except Item.DoesNotExist:
                    # Item doesn't exist: create a new one
                    item_data = {
                        'name': name,
                        'description': description,
                        'category': category,
                        'price': row.get('price', 0.0),
                        'purchase_price': row.get('purchase_price', 0.0),
                        'expiring_date': expiring_date,
                    }
                    form = ItemForm(item_data)
                    if form.is_valid():
                        item = form.save()
                    else:
                        messages.error(request, f"Row {index + 2}: {form.errors.as_text()}")
                        continue
                else:
                    # Item exists: use the existing one
                    pass

                # Check if StoreInventory already exists for this item and store
                if StoreInventory.objects.filter(store=store, item=item).exists():
                    messages.error(request, f"Row {index + 2}: Item '{name}' already exists in your store inventory.")
                    continue

                # Create StoreInventory
                inventories_to_create.append(
                    StoreInventory(
                        store=store,
                        item=item,
                        quantity=int(row.get('quantity', 0)),
                        min_stock_level=int(row.get('min_stock_level', 0))
                    )
                )

                processed_names.add(name_lower)

            # Bulk create StoreInventory entries
            if inventories_to_create:
                StoreInventory.objects.bulk_create(inventories_to_create)
                messages.success(request, f"Successfully added {len(inventories_to_create)} inventory records.")
                return redirect('productslist')
            else:
                messages.error(request, "No valid inventory records to add.")

        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")

        return render(request, self.template_name)

    def test_func(self):
        return self.request.user.is_superuser
    
class AddExistingItemToInventoryView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'store/add_existing_item.html'

    def get(self, request):
        AddExistingItemFormSet = formset_factory(AddExistingItemForm, extra=1)  # Start with one form
        formset = AddExistingItemFormSet(form_kwargs={'store': request.user.store})
        return render(request, self.template_name, {'formset': formset})

    def post(self, request):
        AddExistingItemFormSet = formset_factory(AddExistingItemForm)
        formset = AddExistingItemFormSet(request.POST, form_kwargs={'store': request.user.store})
        if formset.is_valid():
            for form in formset:
                if form.has_changed():  # Only process forms with data
                    item = form.cleaned_data['item']
                    quantity = form.cleaned_data['quantity']
                    min_stock_level = form.cleaned_data['min_stock_level']
                    store = request.user.store
                    StoreInventory.objects.create(
                        store=store,
                        item=item,
                        quantity=quantity,
                        min_stock_level=min_stock_level
                    )
            return redirect('productslist')
        return render(request, self.template_name, {'formset': formset})

    def test_func(self):
        return self.request.user.is_superuser