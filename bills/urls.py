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
    path('usage/<slug:slug>/update/', InternalUsageUpdateView.as_view(), name='usage_update'),
    path('usage/<slug:slug>/delete/', InternalUsageDeleteView.as_view(), name='usage_delete'),
    path('usage/<slug:slug>/detail/', InternalUsageDetailView.as_view(), name='usage_detail')

]