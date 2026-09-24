from rest_framework import generics

from subscriptions.models import Payment
from subscriptions.serializers import PaymentSerializer

from .models import WatchHistory
from .serializers import WatchHistorySerializer


class WatchHistoryListView(generics.ListAPIView):
    serializer_class = WatchHistorySerializer

    def get_queryset(self):
        return WatchHistory.objects.filter(user=self.request.user).select_related("video")


class PaymentHistoryListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    filterset_fields = ["status", "kind"]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).select_related("plan")