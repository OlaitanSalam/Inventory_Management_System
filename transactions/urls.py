# Django core imports
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# Local app imports
from .views import (
    PurchaseOrderListView,
    PurchaseOrderDetailView,
    PurchaseOrderCreateView,
    PurchaseOrderUpdateView,  # New view for updating PurchaseOrder
    PurchaseOrderDeleteView,
    SaleListView,
    SaleDetailView,
    SaleCreateView,
    SaleDeleteView,
    export_sales_to_excel,
    export_purchases_to_excel,
    TransferListView,  # New
    TransferDetailView,  # New
    TransferCreateView,  # New
)

# URL patterns
urlpatterns = [
    # PurchaseOrder URLs
    path('purchase-orders/', PurchaseOrderListView.as_view(), name='purchaseorderslist'),
    path('purchase-order/<int:pk>/', PurchaseOrderDetailView.as_view(), name='purchaseorder-detail'),
    path('new-purchase-order/', PurchaseOrderCreateView, name='purchaseorder-create'),
    path('purchase-order/<int:pk>/update/', PurchaseOrderUpdateView.as_view(), name='purchaseorder-update'),
    path('purchase-order/<int:pk>/delete/', PurchaseOrderDeleteView.as_view(), name='purchaseorder-delete'),
    #ajax calls for urls

    # Sale URLs
    path('sales/', SaleListView.as_view(), name='saleslist'),
    path('sale/<int:pk>/', SaleDetailView.as_view(), name='sale-detail'),
    path('new-sale/', SaleCreateView, name='sale-create'),
    path('sale/<int:pk>/delete/', SaleDeleteView.as_view(), name='sale-delete'),

    # --- New Transfer URLs ---
    path('transfers/', TransferListView.as_view(), name='transferslist'),
    path('transfer/<int:pk>/', TransferDetailView.as_view(), name='transfer-detail'),
    path('new-transfer/', TransferCreateView, name='transfer-create'),

    # Sales and purchases export
    path('sales/export/', export_sales_to_excel, name='sales-export'),
    path('purchase-orders/export/', export_purchases_to_excel, name='purchaseorders-export'),
]

# Static media files configuration for development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)