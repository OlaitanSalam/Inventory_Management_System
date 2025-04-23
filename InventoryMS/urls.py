from django.contrib import admin
from django.urls import path, include
from django.views.defaults import permission_denied


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls')),
    path('staff/', include('accounts.urls')),
    path('transactions/', include('transactions.urls')),
    path('accounts/', include('accounts.urls')),
    path('bills/', include('bills.urls'))
]
