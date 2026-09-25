from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Payment, Plan, Subscription
from .serializers import (
    PlanSerializer,
    RenewSerializer,
    SubscribeSerializer,
    SubscriptionSerializer,
    ZarinpalCheckoutSerializer,
)


def _error_response(exc: services.SubscriptionError) -> Response:
    code = (
        status.HTTP_402_PAYMENT_REQUIRED
        if isinstance(exc, services.PaymentFailed)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(exc)}, status=code)


class PlanViewSet(viewsets.ModelViewSet):


    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        if not (self.request.user and self.request.user.is_staff):
            qs = qs.filter(is_active=True)
        return qs


class SubscriptionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related("plan")

    def create(self, request):
        """Buy a subscription."""
        ser = SubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            sub = services.purchase_subscription(
                request.user,
                ser.validated_data["plan"],
                payment_token=ser.validated_data.get("payment_token"),
                auto_renew=ser.validated_data["auto_renew"],
            )
        except services.SubscriptionError as exc:
            return _error_response(exc)
        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """The current active subscription."""
        sub = (
            services.active_subscriptions(request.user)
            .select_related("plan")
            .order_by("-plan__tier")
            .first()
        )
        if not sub:
            return Response(
                {"detail": "No active subscription."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):

        sub = self.get_object()
        try:
            sub = services.cancel_subscription(sub)
        except services.SubscriptionError as exc:
            return _error_response(exc)
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        """Manually renew (pay again and extend end_date)."""
        sub = self.get_object()
        ser = RenewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            sub = services.renew_subscription(sub, ser.validated_data.get("payment_token"))
        except services.SubscriptionError as exc:
            return _error_response(exc)
        return Response(SubscriptionSerializer(sub).data)


class ZarinpalCheckoutView(APIView):


    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = ZarinpalCheckoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            pay_url = services.start_zarinpal_checkout(
                request.user,
                ser.validated_data["plan"],
                Payment.Kind.RENEWAL if ser.validated_data["kind"] == "renewal" else Payment.Kind.PURCHASE,
                subscription=ser.validated_data.get("subscription"),
            )
        except services.SubscriptionError as exc:
            return _error_response(exc)
        return Response({"pay_url": pay_url})


class ZarinpalCallbackView(APIView):

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        authority = request.query_params.get("Authority", "")
        bank_status = request.query_params.get("Status", "")
        try:
            payment = services.confirm_zarinpal_checkout(authority, bank_status)
        except services.SubscriptionError as exc:
            return _error_response(exc)
        return Response(
            {
                "detail": "Payment successful.",
                "ref_id": payment.gateway_ref,
                "subscription_id": payment.subscription_id,
            }
        )
