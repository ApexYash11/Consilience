"""Payment service skeleton (Stripe integration placeholder)."""
from typing import Any


class PaymentService:
    def create_checkout(self, user_id: str, plan: str):
        # TODO: integrate Stripe checkout
        raise NotImplementedError()

    def handle_webhook(self, payload: bytes, signature: str):
        # TODO: verify and process stripe webhook
        raise NotImplementedError()
