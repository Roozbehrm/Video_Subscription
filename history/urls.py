from django.urls import path

from .views import PaymentHistoryListView, WatchHistoryListView

urlpatterns = [
    path("watch/", WatchHistoryListView.as_view(), name="watch-history"),
    path("payments/", PaymentHistoryListView.as_view(), name="payment-history"),
]