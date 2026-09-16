import requests
from django.conf import settings


class FlutterwaveError(Exception):
    pass


class FlutterwaveGateway:
    """
    Thin adapter around Flutterwave's API. All Flutterwave-specific
    request/response shape lives here — the rest of the app only
    calls these methods, so switching gateways later means writing a
    new adapter class, not touching models/serializers/views.
    """

    BASE_URL = "https://api.flutterwave.com/v3"

    def __init__(self):
        self.secret_key = settings.FLUTTERWAVE_SECRET_KEY

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def initiate_payment(self, *, tx_ref, amount, currency, customer_email,
                          customer_name, redirect_url):
        """
        Creates a hosted checkout payment link. Returns the URL the
        customer should be redirected to.
        """
        payload = {
            "tx_ref": tx_ref,
            "amount": str(amount),
            "currency": currency,
            "redirect_url": redirect_url,
            "customer": {
                "email": customer_email,
                "name": customer_name,
            },
        }
        resp = requests.post(
            f"{self.BASE_URL}/payments",
            json=payload,
            headers=self._headers(),
            timeout=15,
        )
        data = resp.json()

        if resp.status_code != 200 or data.get("status") != "success":
            raise FlutterwaveError(data.get("message", "Failed to initiate payment"))

        return data["data"]["link"]

    def verify_transaction(self, gateway_transaction_id):
        """
        Server-to-server verification — the source of truth for what
        actually happened, independent of what a webhook payload claims.
        """
        resp = requests.get(
            f"{self.BASE_URL}/transactions/{gateway_transaction_id}/verify",
            headers=self._headers(),
            timeout=15,
        )
        data = resp.json()

        if resp.status_code != 200 or data.get("status") != "success":
            raise FlutterwaveError(data.get("message", "Failed to verify transaction"))

        return data["data"]  # contains status, amount, currency, tx_ref, etc.