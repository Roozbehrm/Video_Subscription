import requests
from django.conf import settings

_BASE = "https://sandbox.zarinpal.com" if settings.ZARINPAL_SANDBOX else "https://payment.zarinpal.com"
REQUEST_URL = f"{_BASE}/pg/v4/payment/request.json"
VERIFY_URL = f"{_BASE}/pg/v4/payment/verify.json"
_STARTPAY_BASE = _BASE


class ZarinpalError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def request_payment(*, amount_rial: int, description: str, callback_url: str, mobile: str = "", email: str = "") -> str:
   
    payload = {
        "merchant_id": settings.ZARINPAL_MERCHANT_ID,
        "amount": amount_rial,
        "description": description,
        "callback_url": callback_url,
        "metadata": {"mobile": mobile, "email": email},
    }
    resp = requests.post(REQUEST_URL, json=payload, timeout=10)
    data = resp.json().get("data") or {}
    if data.get("code") != 100:
        errors = resp.json().get("errors") or {}
        raise ZarinpalError(errors.get("message", "Zarinpal request failed"), data.get("code"))
    return data["authority"]


def start_pay_url(authority: str) -> str:
    return f"{_STARTPAY_BASE}/pg/StartPay/{authority}"


def verify_payment(*, amount_rial: int, authority: str):
    """Returns (ok: bool, ref_id: str, message: str). Code 100 = fresh success,
    101 = already verified (treat as success, e.g. user double-hit the callback)."""
    payload = {
        "merchant_id": settings.ZARINPAL_MERCHANT_ID,
        "amount": amount_rial,
        "authority": authority,
    }
    resp = requests.post(VERIFY_URL, json=payload, timeout=10)
    data = resp.json().get("data") or {}
    code = data.get("code")
    if code in (100, 101):
        return True, str(data.get("ref_id", "")), "Payment verified."
    errors = resp.json().get("errors") or {}
    return False, "", errors.get("message", "Payment verification failed.")
