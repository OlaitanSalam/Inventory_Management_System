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
from store.models import Item, StoreInventory, StockAlert, Store
from .models import Sale, SaleDetail, PurchaseOrder, PurchaseDetail, TaxRate, Transfer, TransferDetail
from accounts.models import Vendor
from store.views import update_stock_and_check_alert

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

                        item_instance = Item.objects.get(id=int(item["id"]))
                        
                        inventory = StoreInventory.objects.filter(
                            item=item_instance,
                            store=new_sale.store
                        ).first()
                        
                        if not inventory or inventory.quantity < int(item["quantity"]):
                            raise ValueError(f"Not enough stock for item: {item_instance.name}")

                        update_stock_and_check_alert(inventory, -int(item["quantity"]))

                        detail_attributes = {
                            "sale": new_sale,
                            "item": item_instance,
                            "price": float(item["price"]),
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
        return PurchaseOrder.objects.filter(store=self.request.user.store)

def PurchaseOrderCreateView(request):
    if request.user.store.central:
        vendors = Vendor.objects.all()
    else:
        central_store = Store.objects.get(central=True)
        vendors = Vendor.objects.filter(name=central_store.name)  # Adjust if Vendor and Store are linked differently
    context = {
        "active_icon": "purchases",
        "vendors": vendors
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
                delivery_date_str = data["delivery_date"]
                delivery_date = parse(delivery_date_str)
                if not timezone.is_aware(delivery_date):
                    delivery_date = timezone.make_aware(delivery_date, timezone.get_default_timezone())
               
                purchase_order_attributes = {
                    "vendor_id": data["vendor"],
                    "delivery_date": delivery_date,
                    "delivery_status": data["delivery_status"],
                    "store": request.user.store
                }

                with transaction.atomic():
                    new_purchase_order = PurchaseOrder.objects.create(**purchase_order_attributes)
                    logger.info(f"PurchaseOrder created: {new_purchase_order}")

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

                    total_value = sum(float(item["total_item"]) for item in items)
                    new_purchase_order.total_value = total_value
                    new_purchase_order.save()

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
    fields = ['vendor', 'delivery_date', 'delivery_status']
    template_name = "transactions/purchaseorderform.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['existing_items'] = list(self.object.details.values('item__id', 'item__name', 'quantity',  'description'))
        return context

    def get_success_url(self):
        return reverse("purchaseorderslist")

class PurchaseOrderDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = PurchaseOrder
    template_name = "transactions/purchasedelete.html"

    def get_success_url(self):
        return reverse("purchaseorderslist")

    def test_func(self):
        return self.request.user.is_superuser
    

# --- New TransferCreateView ---
def TransferCreateView(request):
    # Restrict access to central store users only
    if not request.user.store.central:
        return redirect('saleslist')  # Redirect non-central users to sales list

    context = {
        "active_icon": "transfers",
        "branch_stores": Store.objects.exclude(id=request.user.store.id),  # All stores except central
        
    }

    if request.method == 'POST':
        if is_ajax(request):
            try:
                data = json.loads(request.body)
                logger.info(f"Received data: {data}")

                required_fields = [
                    'sub_total', 'grand_total',
                     'items', 'destination_store'
                ]
                for field in required_fields:
                    if field not in data:
                        raise ValueError(f"Missing required field: {field}")

                destination_store = Store.objects.get(id=data['destination_store'])

                transfer_attributes = {
                    "sub_total": float(data["sub_total"]),
                    "grand_total": float(data["grand_total"]),
                    
                    "store": request.user.store,  # Central store as source
                    "destination_store": destination_store,  # Branch store as target
                    "cashier": request.user,
                }

                with transaction.atomic():
                    new_transfer = Transfer.objects.create(**transfer_attributes)
                    logger.info(f"Transfer created: {new_transfer}")

                    items = data["items"]
                    if not isinstance(items, list):
                        raise ValueError("Items should be a list")

                    for item in items:
                        if not all(k in item for k in ["id", "price", "quantity", "total_item"]):
                            raise ValueError("Item is missing required fields")

                        item_instance = Item.objects.get(id=int(item["id"]))
                        
                        # Deduct from central store inventory
                        central_inventory = StoreInventory.objects.filter(
                            item=item_instance,
                            store=new_transfer.store
                        ).first()
                        
                        if not central_inventory or central_inventory.quantity < int(item["quantity"]):
                            raise ValueError(f"Not enough stock for item: {item_instance.name} in central store")

                        update_stock_and_check_alert(central_inventory, -int(item["quantity"]))

                        # Add to destination store inventory
                        destination_inventory, created = StoreInventory.objects.get_or_create(
                            item=item_instance,
                            store=destination_store,
                            defaults={'quantity': 0}
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
            except Item.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Item does not exist!'
                }, status=400)
            except Store.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Destination store does not exist!'
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
                logger.error(f"Exception during transfer creation: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'There was an error during the creation: {str(e)}'
                }, status=500)

    return render(request, "transactions/transfer_create.html", context)

# --- New TransferDetailView ---
class TransferDetailView(LoginRequiredMixin, DetailView):
    model = Transfer
    template_name = "transactions/transferdetail.html"

    def get_queryset(self):
        return Transfer.objects.filter(store=self.request.user.store)

# --- New TransferListView ---
class TransferListView(LoginRequiredMixin, ListView):
    model = Transfer
    template_name = "transactions/transfers_list.html"
    context_object_name = "transfers"
    paginate_by = 10
    ordering = ['date_added']

    def get_queryset(self):
        return Transfer.objects.filter(store=self.request.user.store)