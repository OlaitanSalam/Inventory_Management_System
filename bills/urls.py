from django.urls import path
from .views import (
    InternalUsageListView,
    InternalUsageCreateView,
    InternalUsageUpdateView,
    InternalUsageDeleteView,
    InternalUsageDetailView
)

urlpatterns = [
    path('usages/', InternalUsageListView.as_view(), name='usage_list'),
    path('usage/new/', InternalUsageCreateView, name='usage_create'),
    path('usage/<int:pk>/update/', InternalUsageUpdateView.as_view(), name='usage_update'),
    path('usage/<int:pk>/delete/', InternalUsageDeleteView.as_view(), name='usage_delete'),
    path('usage/<int:pk>/detail/', InternalUsageDetailView.as_view(), name='usage_detail')
]