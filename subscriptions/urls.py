from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import PlanViewSet, SubscriptionViewSet, ZarinpalCallbackView, ZarinpalCheckoutView

router = SimpleRouter()
router.register("plans", PlanViewSet, basename="plan")
router.register("subscriptions", SubscriptionViewSet, basename="subscription")

urlpatterns = [
    path(
        "subscriptions/checkout/zarinpal/",
        ZarinpalCheckoutView.as_view(),
        name="zarinpal-checkout",
    ),
    path(
        "subscriptions/callback/zarinpal/",
        ZarinpalCallbackView.as_view(),
        name="zarinpal-callback",
    ),
] + router.urls
