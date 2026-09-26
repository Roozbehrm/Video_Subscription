from rest_framework import serializers

from .models import Payment, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ("id", "name", "tier", "price", "duration_days", "is_active")


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_canceled = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id", "plan", "start_date", "end_date", "status",
            "auto_renew", "is_canceled", "canceled_at",
        )


class SubscribeSerializer(serializers.Serializer):
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.filter(is_active=True), source="plan"
    )
    payment_token = serializers.CharField(required=False, allow_blank=True)
    auto_renew = serializers.BooleanField(required=False, default=True)


class RenewSerializer(serializers.Serializer):
    payment_token = serializers.CharField(required=False, allow_blank=True)


class ZarinpalCheckoutSerializer(serializers.Serializer):


    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.filter(is_active=True), source="plan"
    )
    kind = serializers.ChoiceField(choices=["purchase", "renewal"], default="purchase")
    subscription_id = serializers.PrimaryKeyRelatedField(
        queryset=Subscription.objects.all(), source="subscription", required=False
    )

    def validate(self, attrs):
        if attrs.get("kind") == "renewal" and "subscription" not in attrs:
            raise serializers.ValidationError(
                {"subscription_id": "Required when kind is 'renewal'."}
            )
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id", "plan", "plan_name", "subscription", "amount",
            "kind", "status", "gateway_ref", "created_at",
        )
