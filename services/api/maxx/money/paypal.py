"""PayPal REST client (Orders v2, Payments v2, Payouts v1, webhook verification).

Every write carries a `PayPal-Request-Id`, so a retry after a crash returns the original result
instead of repeating the money movement. Amounts are `Decimal` and are sent as two-place strings.
The same interface is implemented by `maxx.money.simulator.SimulatedPayPal`, which lets the whole
product run without credentials; the simulator is always labelled as such in the API and the UI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from decimal import Decimal
from typing import Any

import httpx2 as httpx

from maxx.config import settings

log = logging.getLogger(__name__)
CENTS = Decimal("0.01")
# PayPal carrier codes used as-is; any other carrier is sent as OTHER with its name.
PAYPAL_CARRIERS = {"UPS", "USPS", "FEDEX"}
# Payout item states after which nothing more will happen to the money.
PAYOUT_DONE = {"SUCCESS"}
PAYOUT_FAILED = {"FAILED", "RETURNED", "BLOCKED", "REFUNDED", "REVERSED", "DENIED", "CANCELED"}


def money(value: Decimal | str) -> str:
    return str(Decimal(value).quantize(CENTS))


def fee_value(block: dict | None) -> str | None:
    """PayPal's own fee from a `{currency, value}` block, or None when PayPal did not report one."""
    try:
        return money(str((block or {})["value"]))
    except (KeyError, TypeError, ArithmeticError):
        return None


def capture_fee(capture: dict) -> str | None:
    """The fee PayPal kept on a capture (`seller_receivable_breakdown.paypal_fee`)."""
    return fee_value((capture.get("seller_receivable_breakdown") or {}).get("paypal_fee"))


class PayPalError(Exception):
    """A PayPal call failed. `name` is PayPal's error name (for example INSTRUMENT_DECLINED)."""

    def __init__(
        self,
        message: str,
        status: int = 0,
        name: str = "",
        retryable: bool = False,
        debug_id: str = "",
    ):
        super().__init__(message)
        self.status, self.name, self.retryable = status, name, retryable
        # PayPal's id for the failed call; PayPal support asks for it.
        self.debug_id = debug_id


class Pace:
    """At most `per_minute` calls in any rolling minute; callers wait their turn in order."""

    def __init__(self) -> None:
        self.stamps: deque[float] = deque()
        self.lock: asyncio.Lock | None = None
        self.waiting = 0  # callers queued for a turn right now

    async def wait(self, per_minute: int) -> None:
        if per_minute <= 0:
            return
        self.lock = self.lock or asyncio.Lock()
        self.waiting += 1
        try:
            await self._turn(per_minute)
        finally:
            self.waiting -= 1

    async def _turn(self, per_minute: int) -> None:
        assert self.lock is not None
        async with self.lock:
            while True:
                now = time.monotonic()
                while self.stamps and now - self.stamps[0] >= 60:
                    self.stamps.popleft()
                if len(self.stamps) < per_minute:
                    self.stamps.append(now)
                    return
                await asyncio.sleep(60 - (now - self.stamps[0]) + 0.05)


# PayPal's sandbox test Visa. Only ever sent in sandbox mode, by the scripted card-buyer tool.
SANDBOX_CARD = {
    "number": "4111111111111111",
    "expiry": "2030-12",
    "security_code": "123",
    "name": "Maxx Card Buyer",
    "billing_address": {
        "address_line_1": "1 Main St",
        "admin_area_2": "San Jose",
        "admin_area_1": "CA",
        "postal_code": "95131",
        "country_code": "US",
    },
}


class PayPalClient:
    simulated = False

    def __init__(self, base_url: str, client_id: str, secret: str, transport=None):
        self.base_url = base_url.rstrip("/")
        self.client_id, self.secret = client_id, secret
        self.transport = transport
        self._token: tuple[str, float] | None = None
        self._lock = asyncio.Lock()
        self._pace = Pace()

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url, timeout=settings.provider_timeout, transport=self.transport
        )

    async def _access_token(self) -> str:
        async with self._lock:
            if self._token and self._token[1] > time.time() + 60:
                return self._token[0]
            async with self._http() as http:
                response = await http.post(
                    "/v1/oauth2/token",
                    auth=(self.client_id, self.secret),
                    data={"grant_type": "client_credentials"},
                )
            if response.status_code != 200:
                raise PayPalError("PayPal rejected the app credentials.", response.status_code)
            body = response.json()
            self._token = (body["access_token"], time.time() + int(body.get("expires_in", 300)))
            return self._token[0]

    async def _call(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        request_id: str | None = None,
        mock: str | None = None,
        accept: tuple[int, ...] = (200, 201, 202, 204),
    ) -> dict[str, Any]:
        await self._pace.wait(settings.paypal_calls_per_minute)
        headers = {"Authorization": f"Bearer {await self._access_token()}"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id[:108]
        if mock and settings.paypal_negative_testing:
            headers["PayPal-Mock-Response"] = json.dumps({"mock_application_codes": mock})
        headers["Prefer"] = "return=representation"
        async with self._http() as http:
            try:
                response = await http.request(
                    method, path, headers=headers, json=body if body is not None else None
                )
            except httpx.HTTPError as exc:
                raise PayPalError("PayPal is unreachable.", 0, "NETWORK", True) from exc
        if response.status_code in accept:
            return response.json() if response.content else {}
        try:
            detail = response.json()
        except ValueError:
            detail = {}
        name = str(detail.get("name") or "")
        issue = next(iter(detail.get("details") or []), {}).get("issue", "")
        debug_id = str(detail.get("debug_id") or response.headers.get("paypal-debug-id") or "")
        log.warning(
            "PayPal %s %s failed: %s %s debug_id=%s",
            method,
            path,
            response.status_code,
            issue or name,
            debug_id or "-",
        )
        raise PayPalError(
            str(detail.get("message") or "PayPal refused the request."),
            response.status_code,
            issue or name,
            retryable=response.status_code in {429, 500, 502, 503, 504},
            debug_id=debug_id,
        )

    async def create_order(
        self,
        amount: Decimal,
        reference: str,
        request_id: str,
        intent: str = "AUTHORIZE",
        description: str = "Maxx group buy",
        currency: str | None = None,
        mock: str | None = None,
    ) -> dict:
        currency = currency or settings.paypal_currency
        body = {
            "intent": intent,
            "purchase_units": [
                {
                    "reference_id": reference[:256],
                    "description": description[:127],
                    "amount": {"currency_code": currency, "value": money(amount)},
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "brand_name": "Maxx",
                        "user_action": "PAY_NOW" if intent == "CAPTURE" else "CONTINUE",
                        "shipping_preference": "NO_SHIPPING",
                    }
                }
            },
        }
        # `mock` is a simulator-only switch; PayPal negative testing targets the capture call.
        order = await self._call("POST", "/v2/checkout/orders", body, request_id)
        return {"id": order["id"], "status": order.get("status", "CREATED")}

    async def authorize_card(
        self, amount: Decimal, reference: str, request_id: str, description: str
    ) -> dict:
        """One-call hold by card: an AUTHORIZE order paid with the sandbox test card."""
        body = {
            "intent": "AUTHORIZE",
            "purchase_units": [
                {
                    "reference_id": reference[:256],
                    "description": description[:127],
                    "amount": {"currency_code": settings.paypal_currency, "value": money(amount)},
                }
            ],
            "payment_source": {"card": SANDBOX_CARD},
        }
        order = await self._call("POST", "/v2/checkout/orders", body, request_id)
        authorization = order["purchase_units"][0]["payments"]["authorizations"][0]
        if authorization.get("status") not in {"CREATED", "PENDING"}:
            raise PayPalError("PayPal did not authorize the card.", 422, "DECLINED")
        return {"order_id": order["id"], "authorization_id": authorization["id"]}

    async def get_order(self, order_id: str) -> dict:
        order = await self._call("GET", f"/v2/checkout/orders/{order_id}")
        return {"id": order["id"], "status": order.get("status", "")}

    async def authorize_order(self, order_id: str, request_id: str, mock: str | None = None):
        order = await self._call(
            "POST", f"/v2/checkout/orders/{order_id}/authorize", {}, request_id, mock
        )
        unit = order["purchase_units"][0]
        authorization = unit["payments"]["authorizations"][0]
        if authorization.get("status") not in {"CREATED", "PENDING"}:
            raise PayPalError("PayPal did not authorize the payment.", 422, "DECLINED")
        return {"authorization_id": authorization["id"], "status": authorization["status"]}

    async def capture_order(self, order_id: str, request_id: str) -> dict:
        order = await self._call("POST", f"/v2/checkout/orders/{order_id}/capture", {}, request_id)
        capture = order["purchase_units"][0]["payments"]["captures"][0]
        return {
            "capture_id": capture["id"],
            "status": capture["status"],
            "paypal_fee": capture_fee(capture),
        }

    async def capture_authorization(
        self,
        authorization_id: str,
        amount: Decimal,
        request_id: str,
        final_capture: bool = True,
        currency: str | None = None,
        mock: str | None = None,
    ) -> dict:
        body = {
            "amount": {
                "currency_code": currency or settings.paypal_currency,
                "value": money(amount),
            },
            "final_capture": final_capture,
        }
        capture = await self._call(
            "POST",
            f"/v2/payments/authorizations/{authorization_id}/capture",
            body,
            request_id,
            mock,
        )
        return {
            "capture_id": capture["id"],
            "status": capture.get("status", "COMPLETED"),
            "paypal_fee": capture_fee(capture),
        }

    async def refund_capture(
        self, capture_id: str, amount: Decimal, request_id: str, note: str = ""
    ) -> dict:
        body = {
            "amount": {"currency_code": settings.paypal_currency, "value": money(amount)},
            "note_to_payer": note[:255],
        }
        refund = await self._call(
            "POST", f"/v2/payments/captures/{capture_id}/refund", body, request_id
        )
        return {"refund_id": refund["id"], "status": refund.get("status", "COMPLETED")}

    async def get_authorization(self, authorization_id: str) -> str:
        found = await self._call("GET", f"/v2/payments/authorizations/{authorization_id}")
        return str(found.get("status", ""))

    async def get_capture(self, capture_id: str) -> str:
        found = await self._call("GET", f"/v2/payments/captures/{capture_id}")
        return str(found.get("status", ""))

    async def void_authorization(self, authorization_id: str, request_id: str) -> None:
        try:
            await self._call(
                "POST", f"/v2/payments/authorizations/{authorization_id}/void", None, request_id
            )
        except PayPalError as exc:
            # A hold that is already voided is the state we wanted.
            if exc.name != "AUTHORIZATION_ALREADY_VOIDED":
                raise

    async def create_payout(
        self, sender_batch_id: str, items: list[dict], subject: str = "Your Maxx payout"
    ) -> dict:
        body = {
            "sender_batch_header": {
                "sender_batch_id": sender_batch_id,
                "email_subject": subject[:255],
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "receiver": item["receiver"],
                    "sender_item_id": item["sender_item_id"][:63],
                    "note": item.get("note", "")[:4000],
                    "amount": {
                        "currency": item.get("currency", settings.paypal_currency),
                        "value": money(item["amount"]),
                    },
                }
                for item in items
            ],
        }
        batch = await self._call("POST", "/v1/payments/payouts", body, sender_batch_id)
        header = batch.get("batch_header", {})
        return {
            "batch_id": header.get("payout_batch_id", ""),
            "status": header.get("batch_status", "PENDING"),
        }

    async def get_payout_batch(self, payout_batch_id: str) -> list[dict]:
        """Each item of a payout batch with its own status (SUCCESS, UNCLAIMED, FAILED, ...)."""
        batch = await self._call("GET", f"/v1/payments/payouts/{payout_batch_id}")
        return [
            {
                "payout_item_id": str(item.get("payout_item_id", "")),
                "sender_item_id": str((item.get("payout_item") or {}).get("sender_item_id", "")),
                "status": str(item.get("transaction_status", "")),
                "error": str((item.get("errors") or {}).get("name", "")),
                "fee": fee_value(item.get("payout_item_fee")),
            }
            for item in batch.get("items") or []
        ]

    async def add_tracking(
        self, order_id: str, capture_id: str, number: str, carrier: str, request_id: str
    ) -> None:
        """Attach a shipment to the buyer's PayPal order (Orders v2 /track), so PayPal shows it
        and can use it in a dispute. `carrier` is PayPal's carrier code, or OTHER."""
        body: dict = {
            "capture_id": capture_id,
            "tracking_number": number[:64],
            "carrier": carrier if carrier in PAYPAL_CARRIERS else "OTHER",
            "notify_payer": False,
        }
        if body["carrier"] == "OTHER":
            body["carrier_name_other"] = carrier[:64] or "Carrier"
        await self._call("POST", f"/v2/checkout/orders/{order_id}/track", body, request_id)

    async def create_subscription(
        self, plan_id: str, request_id: str, return_url: str, cancel_url: str
    ) -> dict:
        body = {
            "plan_id": plan_id,
            "application_context": {
                "brand_name": "Maxx",
                "user_action": "SUBSCRIBE_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }
        sub = await self._call("POST", "/v1/billing/subscriptions", body, request_id)
        approve = next(
            (link["href"] for link in sub.get("links", []) if link["rel"] == "approve"), ""
        )
        return {
            "id": sub["id"],
            "status": sub.get("status", "APPROVAL_PENDING"),
            "approve_url": approve,
        }

    async def cancel_subscription(self, subscription_id: str, reason: str) -> None:
        await self._call(
            "POST",
            f"/v1/billing/subscriptions/{subscription_id}/cancel",
            {"reason": reason[:128]},
            f"cancel-{subscription_id}",
        )

    def busy(self) -> bool:
        """PayPal calls are already queued behind the per-minute cap."""
        return settings.paypal_calls_per_minute > 0 and self._pace.waiting >= 2

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool:
        lowered = {k.lower(): v for k, v in headers.items()}
        required = [
            "paypal-auth-algo",
            "paypal-cert-url",
            "paypal-transmission-id",
            "paypal-transmission-sig",
            "paypal-transmission-time",
        ]
        if not settings.paypal_webhook_id or any(name not in lowered for name in required):
            return False
        try:
            event = json.loads(body)
        except ValueError:
            return False
        check = await self._call(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            {
                "auth_algo": lowered["paypal-auth-algo"],
                "cert_url": lowered["paypal-cert-url"],
                "transmission_id": lowered["paypal-transmission-id"],
                "transmission_sig": lowered["paypal-transmission-sig"],
                "transmission_time": lowered["paypal-transmission-time"],
                "webhook_id": settings.paypal_webhook_id,
                "webhook_event": event,
            },
        )
        return check.get("verification_status") == "SUCCESS"


def get_paypal():
    """The active PayPal-compatible backend, or None when the money layer is off."""
    from maxx.money import simulator

    mode = settings.paypal_mode
    if mode == "simulator":
        return simulator.get_simulator()
    if mode == "sandbox":
        if not (settings.paypal_client_id and settings.paypal_client_secret):
            raise PayPalError(
                "PAYPAL_MODE=sandbox needs PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET."
            )
        return _sandbox_client()
    return None


_client: PayPalClient | None = None


def _sandbox_client() -> PayPalClient:
    global _client
    if _client is None:
        _client = PayPalClient(
            settings.paypal_base_url, settings.paypal_client_id, settings.paypal_client_secret
        )
    return _client
