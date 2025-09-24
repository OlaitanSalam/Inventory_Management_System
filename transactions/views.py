import json
import logging
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from dateutil.parser import parse
from django.utils import timezone
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from openpyxl import Workbook
from store.models import Item, StoreInventory, StockAlert, Store, Variety  # Added Variety import
from .models import Sale, SaleDetail, PurchaseOrder, PurchaseDetail, TaxRate, Transfer, TransferDetail
from accounts.models import Vendor
from store.views import update_stock_and_check_alert
from django.forms import inlineformset_factory
from .forms import PurchaseOrderForm, PurchaseDetailForm
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from .models import StockMovement

logger = logging.getLogger(__name__)

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

def export_sales_to_excel(request):
    if request.user.is_authenticated:
        sales = Sale.objects.filter(store=request.user.store)
    else:
        sales = Sale.objects.none()

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Sales'

    columns = [
        'ID', 'Date', 'Sub Total',
        'Grand Total', 'Tax Amount', 'Tax Percentage',
        'Amount Paid', 'Amount Change'
    ]
    worksheet.append(columns)

    for sale in sales:
        date_added = sale.date_added.replace(tzinfo=None) if sale.date_added.tzinfo else sale.date_added
        worksheet.append([
            sale.id,
            date_added,
            sale.sub_total,
            sale.grand_total,
            sale.tax_amount,
            sale.tax_percentage,
            sale.amount_paid,
            sale.amount_change
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=sales.xlsx'
    workbook.save(response)
    return response

class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = "transactions/sales_list.html"
    context_object_name = "sales"
    paginate_by = 10
    ordering = ['date_added']

    def get_queryset(self):
        return Sale.objects.filter(store=self.request.user.store)

class SaleDetailView(LoginRequiredMixin, DetailView):
    model = Sale
    template_name = "transactions/saledetail.html"

    def get_queryset(self):
        return Sale.objects.filter(store=self.request.user.store)

def SaleCreateView(request):
    context = {
        "active_icon": "sales",
        "tax_rates": TaxRate.objects.all()
    }
    if request.user.store.central:
        context['branch_stores'] = Store.objects.exclude(id=request.user.store.id)
    else:
        context['branch_stores'] = []

    if request.method == 'POST':
        if is_ajax(request=request):
            try:
                data = json.loads(request.body)
                logger.info(f"Received data: {data}")

                required_fields = [
                    'sub_total', 'grand_total',
                    'amount_paid', 'amount_change', 'items'
                ]
                for field in required_fields:
                    if field not in data:
                        raise ValueError(f"Missing required field: {field}")

                if request.user.store.central:
                    customer_id = data.get('customer')
                    customer = Store.objects.get(id=customer_id) if customer_id else None
                else:
                    customer = None

                sale_attributes = {
                    "sub_total": float(data["sub_total"]),
                    "grand_total": float(data["grand_total"]),
                    "tax_amount": float(data.get("tax_amount", 0.0)),
                    "tax_percentage": float(data.get("tax_percentage", 0.0)),
                    "amount_paid": float(data["amount_paid"]),
                    "amount_change": float(data["amount_change"]),
                    "store": request.user.store,
                    "cashier": request.user,
                    "customer": customer,
                }

                with transaction.atomic():
                    new_sale = Sale.objects.create(**sale_attributes)
                    logger.info(f"Sale created: {new_sale}")

                    items = data["items"]
                    if not isinstance(items, list):
                        raise ValueError("Items should be a list")

                    for item in items:
                        if not all(k in item for k in ["id", "price", "quantity", "total_item"]):
                            raise ValueError("Item is missing required fields")

                        item_id = item["id"]
                        variety = None
                        effective_price = None
                        # Check if the ID indicates a variety (starts with "v_")
                        if item_id.startswith("v_"):
                            variety_id = int(item_id[2:])  # Extract variety ID
                            variety = Variety.objects.get(id=variety_id)
                            base_item = variety.base_item  # Get the base item linked to the variety
                            
                            effective_price = variety.price
                        else:
                            base_item = Item.objects.get(id=int(item_id))  # Regular item
                            if base_item.has_varieties:  # Prevent direct sale of items with varieties
                                raise ValueError(f"Cannot sell {base_item.name} directly; please select a variety.")

                        # Use base_item for inventory check and update
                            inventory = StoreInventory.objects.filter(
                            item=base_item,
                            store=new_sale.store
                            ).first()
                            effective_price = inventory.effective_price if inventory else base_item.price or 0.0

                        
                        # Validate price from frontend matches backend
                        if float(item["price"]) != float(effective_price):
                            raise ValueError(f"Price mismatch for item: {base_item.name}")

                        inventory = StoreInventory.objects.filter(item=base_item, store=new_sale.store).first()
                        
                        if not inventory or inventory.quantity < int(item["quantity"]):
                            raise ValueError(f"Not enough stock for item: {base_item.name}")

                        update_stock_and_check_alert(inventory, -int(item["quantity"]))

                        # Create SaleDetail with base_item and variety if applicable
                        detail_attributes = {
                            "sale": new_sale,
                            "item": base_item,  # Always set to base item
                            "variety": variety if item_id.startswith("v_") else None,  # Set variety if it's a variety sale
                            "price": float(effective_price),  # Price from AJAX data (item or variety price)
                            "quantity": int(item["quantity"]),
                            "total_detail": float(item["total_item"])
                        }
                        SaleDetail.objects.create(**detail_attributes)
                        logger.info(f"Sale detail created: {detail_attributes}")

                return JsonResponse({
                    'status': 'success',
                    'message': 'Sale created successfully!',
                    'redirect': reverse('sale-detail', args=[new_sale.id])
                })

            except json.JSONDecodeError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid JSON format in request body!'
                }, status=400)
            except Item.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Item does not exist!'
                }, status=400)
            except Variety.DoesNotExist:  # Added exception for Variety
                return JsonResponse({
                    'status': 'error',
                    'message': 'Variety does not exist!'
                }, status=400)
            except ValueError as ve:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Value error: {str(ve)}'
                }, status=400)
            except TypeError as te:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Type error: {str(te)}'
                }, status=400)
            except Exception as e:
                logger.error(f"Exception during sale creation: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'There was an error during the creation: {str(e)}'
                }, status=500)

    return render(request, "transactions/sale_create.html", context)

class SaleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Sale
    template_name = "transactions/saledelete.html"

    def get_success_url(self):
        return reverse("saleslist")

    def test_func(self):
        return self.request.user.is_superuser

def export_purchases_to_excel(request):
    if request.user.is_authenticated:
        purchase_orders = PurchaseOrder.objects.filter(store=request.user.store)
    else:
        purchase_orders = PurchaseOrder.objects.none()

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Purchases'

    columns = ['ID', 'Vendor', 'Order Date', 'Delivery Date', 'Delivery Status', 'Total Value']
    worksheet.append(columns)

    for po in purchase_orders:
        order_date = po.order_date.replace(tzinfo=None) if po.order_date.tzinfo else po.order_date
        delivery_date = po.delivery_date.replace(tzinfo=None) if po.delivery_date and po.delivery_date.tzinfo else po.delivery_date
        worksheet.append([
            po.id, po.vendor.name, order_date, delivery_date,
            po.get_delivery_status_display(), po.total_value
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=purchases.xlsx'
    workbook.save(response)
    return response

class PurchaseOrderListView(LoginRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = "transactions/purchases_list.html"
    context_object_name = "purchases"
    paginate_by = 10

    def get_queryset(self):
        if self.request.user.is_superuser:
            return PurchaseOrder.objects.all()
        else:
            return PurchaseOrder.objects.filter(store=self.request.user.store)

class PurchaseOrderDetailView(LoginRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = "transactions/purchaseorderdetail.html"
    context_object_name = "purchase_order"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return PurchaseOrder.objects.all()
        else:
            return PurchaseOrder.objects.filter(store=self.request.user.store)

# transactions/views.py (replace the PurchaseOrderCreateView function)
def PurchaseOrderCreateView(request):
    if request.user.store.central:
        vendors = Vendor.objects.all()
    else:
        central_stores = Store.objects.filter(central=True)
        if central_stores.exists():
            vendors = Vendor.objects.filter(name__in=[store.name for store in central_stores])
        else:
            vendors = Vendor.objects.none()

     # Single item prefill
    pre_fill_item = None
    pre_fill_item_id = request.session.pop('pre_fill_item', None)
    if pre_fill_item_id:
        try:
            item = Item.objects.get(id=pre_fill_item_id)
            pre_fill_item = {
                "id": item.id,
                "name": item.name,
                "price": float(getattr(item, "purchase_price", None) or getattr(item, "price", 0) or 0)
            }
        except Item.DoesNotExist:
            pass

    # Multiple items prefill
    pre_fill_items = []
    pre_fill_item_ids = request.session.pop('pre_fill_items', None)
    if pre_fill_item_ids:
        items = Item.objects.filter(id__in=pre_fill_item_ids)
        for it in items:
            pre_fill_items.append({
                "id": it.id,
                "name": it.name,
                "price": float(getattr(it, "purchase_price", None) or getattr(it, "price", 0) or 0)
            })

    context = {
        "active_icon": "purchases",
        "vendors": vendors,
        "pre_fill_item": json.dumps(pre_fill_item) if pre_fill_item else "null",
        "pre_fill_items": json.dumps(pre_fill_items) if pre_fill_items else "[]",
    }

    if request.method == 'POST':
        if is_ajax(request):
            try:
                data = json.loads(request.body)
                logger.info(f"Received data: {data}")

                required_fields = ['vendor', 'delivery_date', 'delivery_status', 'items']
                for field in required_fields:
                    if field not in data:
                        raise ValueError(f"Missing required field: {field}")

                # parse delivery_date
                delivery_date_str = data["delivery_date"]
                delivery_date = parse(delivery_date_str)
                if not timezone.is_aware(delivery_date):
                    delivery_date = timezone.make_aware(delivery_date, timezone.get_default_timezone())

                # Important: create the PurchaseOrder as PENDING initially.
                # We'll set the real delivery_status after creating the details, then call save()
                purchase_order_attributes = {
                    "vendor_id": data["vendor"],
                    "delivery_date": delivery_date,
                    "delivery_status": 'P',   # <-- force pending at creation
                    "store": request.user.store,
                    "created_by": request.user
                }

                with transaction.atomic():
                    new_purchase_order = PurchaseOrder.objects.create(**purchase_order_attributes)
                    logger.info(f"PurchaseOrder created (PENDING): {new_purchase_order}")

                    items = data["items"]
                    if not isinstance(items, list):
                        raise ValueError("Items should be a list")

                    for item in items:
                        if not all(k in item for k in ["id", "quantity", "total_item"]):
                            raise ValueError("Item is missing required fields")
                        if int(item["quantity"]) <= 0 or float(item["total_item"]) <= 0:
                            raise ValueError("Quantity and total amount must be greater than 0")

                        item_instance = Item.objects.get(id=int(item["id"]))

                        detail_attributes = {
                            "purchase_order": new_purchase_order,
                            "item": item_instance,
                            "quantity": int(item["quantity"]),
                            "total_value": float(item["total_item"]),
                            "description": item.get("description", "")
                        }
                        PurchaseDetail.objects.create(**detail_attributes)
                        logger.info(f"PurchaseDetail created: {detail_attributes}")

                    # Calculate and set total value
                    total_value = sum(float(item["total_item"]) for item in items)
                    new_purchase_order.total_value = total_value

                    # Now set the real delivery status requested by the user (P or S)
                    requested_status = data.get("delivery_status", 'P')
                    new_purchase_order.delivery_status = requested_status

                    # This save() will now detect the transition (P -> S) and perform inventory updates
                    new_purchase_order.save()
                    logger.info(f"PurchaseOrder saved with status {new_purchase_order.delivery_status}")

                return JsonResponse({
                    'status': 'success',
                    'message': 'Purchase order created successfully!',
                    'redirect': '/transactions/purchase-orders/'
                })

            except json.JSONDecodeError:
                return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
            except Item.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Item does not exist'}, status=400)
            except ValueError as ve:
                return JsonResponse({'status': 'error', 'message': str(ve)}, status=400)
            except Exception as e:
                logger.error(f"Error in PurchaseOrder creation: {e}")
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return render(request, "transactions/purchases_form.html", context=context)


class PurchaseOrderUpdateView(LoginRequiredMixin, UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "transactions/purchaseorderform.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        PurchaseDetailFormSet = inlineformset_factory(
            PurchaseOrder,
            PurchaseDetail,
            form=PurchaseDetailForm,
            fields=('item', 'quantity', 'total_value'),
            extra=1,
            can_delete=True
        )
        if self.request.POST:
            context['formset'] = PurchaseDetailFormSet(self.request.POST, instance=self.object)
        else:
            context['formset'] = PurchaseDetailFormSet(instance=self.object)
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not (self.object.delivery_status == 'P' and self.object.created_by == request.user):
            if self.object.delivery_status != 'P':
                message = "You cannot edit this purchase order anymore because it was upon successful transactions."
            else:
                creator_email = self.object.created_by.email
                message = f"You cannot edit this purchase order because it was initiated by another user. Please contact {creator_email} or the admin."
            return render(request, 'transactions/permission_denied_purchase_order.html', {'message': message})
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not (self.object.delivery_status == 'P' and self.object.created_by == request.user):
            if self.object.delivery_status != 'P':
                message = "You cannot edit this purchase order anymore because it was upon successful transactions."
            else:
                creator_email = self.object.created_by.email
                message = f"You cannot edit this purchase order because it was initiated by another user. Please contact {creator_email} or the admin."
            return render(request, 'transactions/permission_denied_purchase_order.html', {'message': message})
        form = self.get_form()
        PurchaseDetailFormSet = inlineformset_factory(
            PurchaseOrder,
            PurchaseDetail,
            form=PurchaseDetailForm,
            fields=('item', 'quantity', 'total_value'),
            extra=1,
            can_delete=True
        )
        formset = PurchaseDetailFormSet(request.POST, instance=self.object)
        if form.is_valid() and formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            self.object.total_value = sum(detail.total_value for detail in self.object.details.all())
            self.object.save()
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

    def get_success_url(self):
        return reverse("purchaseorderslist")
    
class PurchaseOrderDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = PurchaseOrder
    template_name = "transactions/purchasedelete.html"

    def get_success_url(self):
        return reverse("purchaseorderslist")

    def test_func(self):
        return self.request.user.is_superuser

@login_required
def TransferCreateView(request):
    if not request.user.store.central:
        return redirect('saleslist')

    context = {
        "active_icon": "transfers",
        "branch_stores": Store.objects.exclude(id=request.user.store.id),
    }

    if request.method == 'POST' and is_ajax(request):
        try:
            data = json.loads(request.body)
            logger.info(f"Received data: {data}")

            # Validate required fields
            required_fields = ['sub_total', 'grand_total', 'items', 'destination_store']
            for field in required_fields:
                if field not in data or data[field] in [None, '', []]:
                    raise ValidationError(f"Missing or empty required field: {field}")

            # Validate sub_total and grand_total
            try:
                sub_total = float(data['sub_total'])
                grand_total = float(data['grand_total'])
                if sub_total < 0 or grand_total < 0:
                    raise ValidationError("Subtotal and grand total must be non-negative.")
            except (ValueError, TypeError):
                raise ValidationError("Subtotal and grand total must be valid numbers.")

            # Validate items
            items = data['items']
            if not items:
                raise ValidationError("At least one item is required for the transfer.")

            destination_store = Store.objects.get(id=data['destination_store'])

            transfer_attributes = {
                "sub_total": sub_total,
                "grand_total": grand_total,
                "store": request.user.store,
                "destination_store": destination_store,
                "cashier": request.user,
            }

            with transaction.atomic():
                new_transfer = Transfer.objects.create(**transfer_attributes)
                logger.info(f"Transfer created: {new_transfer}")

                for item in items:
                    if not all(k in item for k in ["id", "price", "quantity", "total_item"]):
                        raise ValidationError("Item is missing required fields")

                    item_instance = Item.objects.get(id=int(item["id"]))
                    central_inventory = StoreInventory.objects.filter(
                        item=item_instance,
                        store=new_transfer.store
                    ).first()
                    
                    if not central_inventory or central_inventory.quantity < int(item["quantity"]):
                        raise ValidationError(f"Not enough stock for item: {item_instance.name} in central store")

                    central_inventory.quantity -= int(item["quantity"])
                    central_inventory.save()

                    destination_inventory, created = StoreInventory.objects.get_or_create(
                        item=item_instance,
                        store=destination_store,
                        defaults={'quantity': 0, 'min_stock_level': 0}
                    )
                    destination_inventory.quantity += int(item["quantity"])
                    destination_inventory.save()

                    detail_attributes = {
                        "transfer": new_transfer,
                        "item": item_instance,
                        "price": float(item["price"]),
                        "quantity": int(item["quantity"]),
                        "total_detail": float(item["total_item"])
                    }
                    TransferDetail.objects.create(**detail_attributes)
                    logger.info(f"Transfer detail created: {detail_attributes}")

            return JsonResponse({
                'status': 'success',
                'message': 'Transfer created successfully!',
                'redirect': reverse('transfer-detail', args=[new_transfer.id])
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON format in request body!'
            }, status=400)
        except Store.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Destination store does not exist!'
            }, status=400)
        except Item.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Item does not exist!'
            }, status=400)
        except ValidationError as ve:
            return JsonResponse({
                'status': 'error',
                'message': str(ve)
            }, status=400)
        except Exception as e:
            logger.error(f"Exception during transfer creation: {e}")
            return JsonResponse({
                'status': 'error',
                'message': f'There was an error during the creation: {str(e)}'
            }, status=500)

    return render(request, "transactions/transfer_create.html", context)

class TransferDetailView(LoginRequiredMixin, DetailView):
    model = Transfer
    template_name = "transactions/transferdetail.html"

    def get_queryset(self):
        return Transfer.objects.filter(store=self.request.user.store)

class TransferListView(LoginRequiredMixin, ListView):
    model = Transfer
    template_name = "transactions/transfers_list.html"
    context_object_name = "transfers"
    paginate_by = 10
    ordering = ['date_added']

    def get_queryset(self):
        return Transfer.objects.filter(store=self.request.user.store)
    

# transactions/views.py

class StockMovementListView(LoginRequiredMixin, ListView):
    model = StockMovement
    template_name = "transactions/stock_movement_list.html"
    context_object_name = "movements"
    paginate_by = 15

    def get_queryset(self):
        qs = StockMovement.objects.all()
        request = self.request

        if request.user.is_superuser:
            store_id = request.GET.get("store")
            if store_id and store_id.isdigit():
                qs = qs.filter(store_id=store_id)
        else:
            qs = qs.filter(store=request.user.store)

        # filter by item
        item_id = request.GET.get("item")
        if item_id and item_id.isdigit():
            qs = qs.filter(item_id=item_id)

        # date filter
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        if start_date and end_date:
            qs = qs.filter(timestamp__date__range=[start_date, end_date])

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # Stores (for superusers only)
        if request.user.is_superuser:
            context["stores"] = Store.objects.all()
            store_id = request.GET.get("store")
            context["selected_store"] = int(store_id) if store_id and store_id.isdigit() else None
        else:
            # non-superuser only sees their own store
            store_id = request.user.store.id
            context["selected_store"] = store_id

        # Items: filter by store if a store is selected
        store_id = request.GET.get("store") or context["selected_store"]
        if store_id:
            context["items"] = Item.objects.filter(store_inventories__store_id=store_id).distinct()
        else:
            context["items"] = Item.objects.all()

        # track which item is selected
        context["selected_item"] = request.GET.get("item")

        return context




 

