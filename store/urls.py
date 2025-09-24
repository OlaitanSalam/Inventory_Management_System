# Django core imports
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# Local app imports
from . import views
from .views import (
    ProductListView,
    ProductDetailView,
    ProductCreateView,
    ProductUpdateView,
    ProductDeleteView,
    ItemSearchListView,
    #DeliveryListView,
    #DeliveryDetailView,
    #DeliveryCreateView,
    #DeliveryUpdateView,
    #DeliveryDeleteView,
    get_items_ajax_view,
    CategoryListView,
    CategoryDetailView,
    CategoryCreateView,
    CategoryUpdateView,
    CategoryDeleteView,
   NotificationListView,
   mark_alert_as_read, mark_all_alerts_as_read,
    get_unread_alerts_count,
    BulkItemUploadView,
    AddExistingItemToInventoryView

)

# URL patterns
urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Product URLs
    path(
        'products/',
        ProductListView.as_view(),
        name='productslist'
    ),
    path(
        'product/<slug:slug>/',
        ProductDetailView.as_view(),
        name='product-detail'
    ),
    path(
        'new-product/',
        ProductCreateView.as_view(),
        name='product-create'
    ),
    path(
        'product/<slug:slug>/update/',
        ProductUpdateView.as_view(),
        name='product-update'
    ),
    path(
        'product/<slug:slug>/delete/',
        ProductDeleteView.as_view(),
        name='product-delete'
    ),

    # Item search
    path(
        'search/',
        ItemSearchListView.as_view(),
        name='item_search_list_view'
    ),

    # Delivery URLs
   #path(
    #    'deliveries/',
       # DeliveryListView.as_view(),
       # name='deliveries'
  #  ),
   # path(
    #    'delivery/<slug:slug>/',
     #   DeliveryDetailView.as_view(),
      #  name='delivery-detail'
    #),
    #path(
     #   'new-delivery/',
      #  DeliveryCreateView.as_view(),
       # name='delivery-create'
    #),
    #path(
     #   'delivery/<int:pk>/update/',
      #  DeliveryUpdateView.as_view(),
       # name='delivery-update'
    #),
    #path(
     #   'delivery/<int:pk>/delete/',
      #  DeliveryDeleteView.as_view(),
       # name='delivery-delete'
    #),

    # AJAX view
    path(
        'get-items/',
        get_items_ajax_view,
        name='get_items'
    ),

    # Category URLs
    path(
        'categories/',
        CategoryListView.as_view(),
        name='category-list'
    ),
    path(
        'categories/<int:pk>/',
        CategoryDetailView.as_view(),
        name='category-detail'
    ),
    path(
        'categories/create/',
        CategoryCreateView.as_view(),
        name='category-create'
    ),
    path(
        'categories/<int:pk>/update/',
        CategoryUpdateView.as_view(),
        name='category-update'
    ),
    path(
        'categories/<int:pk>/delete/',
        CategoryDeleteView.as_view(),
        name='category-delete'
    ),
    
path('notifications/', NotificationListView.as_view(), name='notifications'),
    path('notifications/mark-as-read/<int:pk>/', mark_alert_as_read, name='mark_alert_as_read'),
    path('notifications/mark-all-as-read/', mark_all_alerts_as_read, name='mark_all_alerts_as_read'),
    path('ajax/get-unread-alerts-count/', get_unread_alerts_count, name='get_unread_alerts_count'),
    path('notifications/delete/<int:pk>/', views.delete_alert, name='delete_alert'),
    path('purchase-from-alerts/', views.create_purchase_from_alerts, name='create_purchase_from_alerts'),

    path('purchase-from-alert/<int:alert_id>/', views.create_purchase_from_alert, name='create_purchase_from_alert'),
    #this are my statistics urls
    path('reports/usage/', views.UsageReportView.as_view(), name='usage_report'),
    path('reports/sales/', views.SalesReportView.as_view(), name='sales_report'),
    path('reports/performance/', views.PerformanceStatsView.as_view(), name='performance_stats'),
    path('reports/branch-comparison/', views.BranchSalesComparisonView.as_view(), name='branch_sales_comparison'),
    path('bulk-upload/', BulkItemUploadView.as_view(), name='bulk_item_upload'),
    path('add-existing-items/', views.AddExistingItemToInventoryView.as_view(), name='add_existing_items'),
    path('export-products/', views.export_products_to_excel, name='export-products'),
]

# Static media files configuration for development
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
