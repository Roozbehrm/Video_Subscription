import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass
class PaymentResult:
    success: bool
    reference: str = ""
    message: str = ""


class BasePaymentGateway(ABC):
    @abstractmethod
    def charge(self, *, user, amount, token=None, description="") -> PaymentResult:
        ...


class MockGateway(BasePaymentGateway):
    """Always succeeds, unless the client sends payment_token == "fail"."""

    def charge(self, *, user, amount, token=None, description="") -> PaymentResult:
        if token == "fail":
            return PaymentResult(False, f"mock-{uuid.uuid4().hex[:12]}", "Card declined (mock).")
        return PaymentResult(True, f"mock-{uuid.uuid4().hex[:12]}")


class AlwaysFailGateway(BasePaymentGateway):
    """Useful in tests to simulate failed (auto-)renewals."""

    def charge(self, *, user, amount, token=None, description="") -> PaymentResult:
        return PaymentResult(False, "", "Gateway unavailable.")


def get_gateway() -> BasePaymentGateway:
    return import_string(settings.PAYMENT_GATEWAY)()
