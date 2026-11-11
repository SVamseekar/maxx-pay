"""Agentic checkout: the agent proposes, a guard checks, the person confirms, PayPal moves money.

The agent never holds a credential and never decides to spend. It turns a price verdict into a
proposal; the server signs that proposal; PayPal tools (`create_order`, `get_order`,
`capture_order`, named as in PayPal's Agent Toolkit) run only through `guard`, which compares what
is about to be charged with what the person was shown and agreed to.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets as stdlib_secrets
import time
from decimal import Decimal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from maxx import schema, secrets, storage
from maxx.config import settings
from maxx.money import chain, ledger, subscriptions
from maxx.money.paypal import CENTS, PayPalError, get_paypal
from maxx.scan import PriceRow

TOOLS = [
    {
        "name": "create_order",
        "description": "Create a PayPal order for the exact total the person approved.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_token": {"type": "string"},
                "confirm_total": {"type": "string"},
            },
            "required": ["proposal_token", "confirm_total"],
        },
    },
    {
        "name": "get_order",
        "description": "Read the status of a PayPal order created by this agent.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "capture_order",
        "description": "Capture an order the person has approved in PayPal. Never captures more "
        "than the signed proposal.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposeRequest(Strict):
    item_title: str = Field(min_length=3, max_length=300)
    qty: int = Field(default=1, ge=1, le=20)
    # The scan's own offers, sealed by the server when it answered the scan. The browser cannot
    # change a price, a stock flag or the "same item" check without breaking the seal.
    offers_seal: str = Field(max_length=24000)


class ConfirmRequest(Strict):
    proposal_token: str = Field(max_length=2000)
    confirm_total: str = Field(max_length=20)
    method: str = Field(default="paypal", pattern="^(paypal|pyusd)$")


class Refused(ValueError):
    """The guard or the proposal rules said no. The message is safe to show the person."""


def _mac(payload: bytes) -> str:
    key = secrets._key("checkout-proposal")
    return base64.urlsafe_b64encode(hmac.new(key, payload, hashlib.sha256).digest()).decode()


def seal(proposal: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(proposal, sort_keys=True).encode()).decode()
    return f"{payload}.{_mac(payload.encode())}"


def unseal(token: str, user_id: str) -> dict:
    payload, _, mac = token.partition(".")
    if not payload or not hmac.compare_digest(mac, _mac(payload.encode())):
        raise Refused("This offer was not made by Maxx. Ask for a fresh one.")
    proposal = json.loads(base64.urlsafe_b64decode(payload))
    if proposal["user_id"] != user_id:
        raise Refused("This offer belongs to someone else.")
    if proposal["expires"] < time.time():
        raise Refused("This offer expired. Ask for a fresh one.")
    return proposal


SCAN_OFFERS_MINUTES = 60


def seal_offers(rows: list, current_price: Decimal | None) -> str:
    """Seal a scan's offers as the server found them, for a checkout proposal later."""
    return seal(
        {
            "kind": "scan-offers",
            "rows": [PriceRow.model_validate(row).model_dump(mode="json") for row in rows][:8],
            "current_price": str(current_price) if current_price is not None else None,
            "expires": int(time.time()) + SCAN_OFFERS_MINUTES * 60,
        }
    )


def unseal_offers(token: str) -> tuple[list[PriceRow], Decimal | None]:
    payload, _, mac = token.partition(".")
    if not payload or not hmac.compare_digest(mac, _mac(payload.encode())):
        raise Refused("These offers did not come from a Maxx scan. Scan the item again.")
    sealed = json.loads(base64.urlsafe_b64decode(payload))
    if sealed.get("kind") != "scan-offers":
        raise Refused("These offers did not come from a Maxx scan. Scan the item again.")
    if sealed["expires"] < time.time():
        raise Refused("This scan is over an hour old. Scan the item again for current prices.")
    current = sealed["current_price"]
    return [PriceRow.model_validate(row) for row in sealed["rows"]], (
        Decimal(current) if current is not None else None
    )


def propose(user_id: str, request: ProposeRequest) -> dict:
    """Pick the cheapest trustworthy offer. Only verified, in-stock, fully priced rows qualify."""
    rows, current_price = unseal_offers(request.offers_seal)
    candidates = []
    for row in rows:
        if (
            row.same_item
            and row.in_stock
            and row.shipping is not None
            and row.url.scheme == "https"
        ):
            unit = row.price + row.shipping
            candidates.append((unit, row))
    if not candidates:
        raise Refused("No verified in-stock offer with a known delivered price. Nothing to buy.")
    unit, best = min(candidates, key=lambda c: c[0])
    total = (unit * request.qty).quantize(CENTS)
    if current_price is not None and unit >= current_price:
        raise Refused("No offer is cheaper than the price you were looking at.")
    limit = subscriptions.checkout_limit(user_id)
    if total > Decimal(limit):
        raise Refused(f"Agent checkout is limited to ${limit} per order for your plan.")
    proposal = {
        "user_id": user_id,
        "title": request.item_title.strip()[:300],
        "merchant": urlsplit(str(best.url)).hostname or "",
        "url": str(best.url),
        "qty": request.qty,
        "unit_price": str(best.price),
        "shipping": str(best.shipping),
        "total": str(total),
        "currency": settings.paypal_currency,
        "evidence": best.evidence[:300],
        "saves": str((current_price - unit).quantize(CENTS) * request.qty)
        if current_price
        else None,
        "expires": int(time.time()) + settings.checkout_proposal_minutes * 60,
    }
    return {
        **{k: v for k, v in proposal.items() if k != "user_id"},
        "proposal_token": seal(proposal),
        "plan": [
            {"tool": "create_order", "when": "after you confirm", "amount": proposal["total"]},
            {"tool": "get_order", "when": "after you approve in PayPal"},
            {"tool": "capture_order", "when": "once approved", "amount": proposal["total"]},
        ],
        "tools": [t["name"] for t in TOOLS],
    }


def guard(
    proposal: dict, confirm_total: str, amount: Decimal | None = None, limit: str | None = None
) -> Decimal:
    """Refuse any charge that is not exactly what the person was shown and agreed to."""
    total = Decimal(proposal["total"])
    try:
        agreed = Decimal(confirm_total)
    except ArithmeticError:
        raise Refused("Confirm the total to continue.") from None
    if abs(agreed - total) > CENTS:
        raise Refused("The total you confirmed does not match the offer.")
    if amount is not None and abs(amount - total) > CENTS:
        raise Refused("The order amount does not match the offer. Nothing was charged.")
    if total > Decimal(limit or settings.checkout_max_amount):
        raise Refused("This order is over your agent checkout limit.")
    return total


def info(payment: dict) -> dict:
    try:
        return json.loads(payment["meta"])
    except ValueError:
        return {}


async def create_order(
    user_id: str, token: str, confirm_total: str, method: str = "paypal"
) -> dict:
    pp = get_paypal()
    if pp is None:
        raise Refused("Payments are turned off.")
    proposal = unseal(token, user_id)
    total = guard(proposal, confirm_total, limit=subscriptions.checkout_limit(user_id))
    digest = hashlib.sha256(token.encode()).hexdigest()
    # One open order per offer: confirming twice returns the first order instead of a second charge.
    for existing in ledger.for_user(user_id):
        details = info(existing)
        if (
            existing["kind"] == "checkout"
            and details.get("offer") == digest
            and existing["status"] in {"CAPTURED", "REFUNDED"}
        ):
            # Paid already, by either method: confirming again must not open a second order.
            raise Refused("You already bought this offer. It is in your receipts.")
        if (
            existing["kind"] == "checkout"
            and details.get("offer") == digest
            and details.get("method") == method
            and existing["status"] in {"CREATED", "APPROVED"}
        ):
            return {
                "order_id": existing["order_id"],
                "amount": str(total),
                "reused": True,
                **pay_details(existing),
            }
    if method == "pyusd":
        return pyusd_order(user_id, proposal, total, digest, pp.simulated)
    request_id = "checkout-" + digest[:40]
    order = await pp.create_order(
        total,
        reference=f"checkout:{proposal['merchant']}",
        request_id=request_id,
        intent="CAPTURE",
        description=f"Maxx checkout: {proposal['title']}"[:127],
    )
    ledger.new_payment(
        "checkout",
        order["id"],
        total,
        pp.simulated,
        user_id=user_id,
        meta=json.dumps({"title": proposal["title"], "offer": digest, "method": "paypal"}),
    )
    return {"order_id": order["id"], "amount": str(total), "reused": False}


def pay_details(payment: dict) -> dict:
    details = info(payment)
    if details.get("method") != "pyusd":
        return {}
    return {
        "method": "pyusd",
        "pyusd": {
            "address": chain.deposit_address(),
            "contract": chain.contract_address(),
            "chain": settings.pyusd_chain,
            "units": details["units"],
            "amount": chain.display_units(details["units"]),
            "simulated": isinstance(chain.get_chain(), chain.SimulatedChain),
        },
    }


def pyusd_order(user_id: str, proposal: dict, total: Decimal, digest: str, simulated: bool) -> dict:
    if chain.get_chain() is None:
        raise Refused("PYUSD payments are not set up on this server.")
    taken = ledger.open_pyusd_units()
    for _ in range(50):
        units = chain.tagged_units(total, chain.new_tag())
        if units not in taken:
            break
    else:
        raise Refused("Too many open PYUSD orders for this amount. Try again shortly.")
    order_id = "PYUSD-" + stdlib_secrets.token_hex(8).upper()
    payment = ledger.new_payment(
        "checkout",
        order_id,
        total,
        simulated,
        user_id=user_id,
        meta=json.dumps(
            {"title": proposal["title"], "offer": digest, "method": "pyusd", "units": units}
        ),
    )
    return {"order_id": order_id, "amount": str(total), "reused": False, **pay_details(payment)}


async def verify_pyusd(user_id: str, order_id: str, tx_hash: str) -> dict:
    """Accept a PYUSD transfer as payment for a checkout order, once and only if it matches."""
    payment = ledger.by_order(order_id)
    if not payment or payment["user_id"] != user_id or info(payment).get("method") != "pyusd":
        raise LookupError("Order not found.")
    if payment["status"] == "CAPTURED":
        return {
            "order_id": order_id,
            "status": "COMPLETED",
            "tx_hash": "0x" + payment["capture_id"],
        }
    if not chain.TX_HASH.match(tx_hash):
        raise Refused("That does not look like a transaction hash.")
    if payment["status"] != "CREATED":
        raise Refused("This order can no longer be paid.")
    proof = tx_hash.lower()[2:]
    source = chain.get_chain()
    if source is None:
        raise Refused("PYUSD payments are not set up on this server.")
    try:
        transfer = await source.transfer(tx_hash.lower())
        # A transfer mined before the order existed cannot be for it (allow for clock skew).
        chain.check(transfer, int(info(payment)["units"]), not_before=payment["created_at"] - 120)
    except chain.ChainError as exc:
        raise Refused(str(exc)) from None
    # Claim the transaction and settle the order in one database transaction: the primary key on
    # used_transactions makes a second claim fail, and the status guard makes a double submit fail.
    stamp = int(time.time())
    try:
        with storage.get_store().engine.begin() as db:
            db.execute(
                schema.used_transactions.insert().values(
                    tx_hash=proof, payment_id=payment["id"], used_at=stamp
                )
            )
            done = db.execute(
                update(schema.payments)
                .where(schema.payments.c.id == payment["id"], schema.payments.c.status == "CREATED")
                .values(
                    status="CAPTURED",
                    capture_id=proof,
                    captured_amount=Decimal(payment["max_amount"]),
                    updated_at=stamp,
                )
            )
            if done.rowcount != 1:
                raise IntegrityError("order no longer open", None, Exception())
    except IntegrityError:
        raise Refused("That transaction was already used, or the order was already paid.") from None
    return {"order_id": order_id, "status": "COMPLETED", "tx_hash": "0x" + proof}


async def get_order(user_id: str, order_id: str) -> dict:
    pp = get_paypal()
    payment = ledger.by_order(order_id)
    if pp is None or not payment or payment["user_id"] != user_id or payment["kind"] != "checkout":
        raise LookupError("Order not found.")
    return {"order_id": order_id, **await pp.get_order(order_id), "ledger": payment["status"]}


async def capture_order(user_id: str, order_id: str) -> dict:
    pp = get_paypal()
    payment = ledger.by_order(order_id)
    if pp is None or not payment or payment["user_id"] != user_id or payment["kind"] != "checkout":
        raise LookupError("Order not found.")
    if info(payment).get("method") == "pyusd":
        raise Refused("Pay this order with PYUSD, then submit the transaction hash.")
    if payment["status"] == "CAPTURED":
        return {"order_id": order_id, "status": "COMPLETED", "capture_id": payment["capture_id"]}
    if (await pp.get_order(order_id))["status"] != "APPROVED":
        raise Refused("Approve the payment in PayPal first.")
    amount = Decimal(payment["max_amount"])
    if amount > Decimal(subscriptions.checkout_limit(user_id)):
        raise Refused("This order is over the agent checkout limit.")
    try:
        capture = await pp.capture_order(order_id, request_id=f"capture-{payment['id']}")
    except PayPalError as exc:
        ledger.update_payment(payment["id"], status="FAILED", error=exc.name[:60] or "declined")
        raise Refused("PayPal could not complete the payment.") from exc
    ledger.update_payment(
        payment["id"],
        status="CAPTURED",
        capture_id=capture["capture_id"],
        captured_amount=amount,
        paypal_fee=capture.get("paypal_fee"),
    )
    return {"order_id": order_id, "status": capture["status"], "capture_id": capture["capture_id"]}
