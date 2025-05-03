from store.models import StockAlert

def unread_alerts_count(request):
    if request.user.is_authenticated:
        current_store = request.user.store
        count = StockAlert.objects.filter(store_inventory__store=current_store, is_read=False).count()
        return {'unread_alerts_count': count}
    return {'unread_alerts_count': 0}