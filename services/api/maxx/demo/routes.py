"""Demo-only endpoints for judges. Refused unless the demo setup is on (see tour.enabled)."""

from __future__ import annotations

import asyncio
import hmac
import time
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from maxx.auth import mail, ratelimit
from maxx.auth import store as auth_store
from maxx.auth.deps import CurrentUser, same_origin
from maxx.config import settings
from maxx.demo import catalogue, tour
from maxx.fulfilment import service as fulfil_service
from maxx.fulfilment import store as fulfil_store
from maxx.money import service as money
from maxx.money.paypal import PayPalError
from maxx.negotiate.routes import DEMO_CROWD, RuntimeDep, get_bloc, is_private_copy
from maxx.providers import ProviderError

router = APIRouter(prefix="/demo", dependencies=[Depends(same_origin)])


@router.get("/seller-tour")
def tour_status():
    return {"available": tour.enabled()}


@router.post("/seller-tour", status_code=201)
async def start_tour(runtime: RuntimeDep, user: CurrentUser):
    if not tour.enabled():
        raise HTTPException(404, "Not found.")
    if not user.email_verified:
        raise HTTPException(403, "Confirm your email before starting the seller tour.")
    ratelimit.hit(f"seller-tour:{user.id}", 3, 3600)
    ratelimit.hit("seller-tour:all", 60, 3600)
    try:
        return await tour.start(runtime, user)
    except tour.TourError as exc:
        raise HTTPException(409, str(exc)) from None
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/products")
def products():
    """The everyday demo products anyone can try in a private Bloc. All made up, prices
    illustrative."""
    return [
        {
            "id": p.id,
            "title": p.title,
            "typical_price": str(p.typical),
            "moment": p.moment,
            "unit_count": p.unit_count,
            "unit_noun": p.unit_noun,
        }
        for p in catalogue.PRODUCTS
    ]


@router.post("/lab/{scenario}", status_code=201)
def open_lab(scenario: str, runtime: RuntimeDep, user: CurrentUser, product: str | None = None):
    """The judge's own copy of a demo scenario: same simulated crowd and sellers, but nobody
    else's seat, hold or finished outcome is in it, so it never needs a reset. Unlisted, like
    the seller tour; an unfinished copy is reused rather than duplicated. `product` picks one of
    the everyday demo products; without it each scenario uses its own product."""
    if scenario not in DEMO_CROWD or (product is not None and product not in catalogue.BY_ID):
        raise HTTPException(404, "Not found.")
    return {"bloc_id": lab_copy(runtime, user.id, scenario, product)}


def lab_copy(runtime, user_id: str, scenario: str, product: str | None = None) -> str:
    """The person's open private copy of a demo scenario and product, made if they have none."""
    title = catalogue.for_scenario(scenario, product).title
    for bloc in runtime.store.list_for_user(user_id):
        if (
            bloc.id.startswith(f"lab-{scenario}-")
            and bloc.owner_id == user_id
            and bloc.title == title
            and bloc.status == "OPEN"
            and bloc.closes_at > time.time()
        ):
            return bloc.id
    ratelimit.hit(f"demo-lab:{user_id}", 12, 3600)
    ratelimit.hit("demo-lab:all", 600, 3600)
    tag = uuid.uuid4().hex[:12]
    bloc = runtime.scenario_bloc(f"lab-{scenario}-{tag}", scenario, runtime.mode, product)
    bloc.product_key = f"demo-lab:{user_id[:8]}:{scenario}:{tag}"
    bloc.owner_id = user_id
    runtime.store.create(bloc)
    return bloc.id


# --- Scripted card buyers ------------------------------------------------------------------
# Fills a shared demo Bloc with real PayPal sandbox holds, one guest buyer per call, each paid
# with PayPal's sandbox test card in a single Orders call (no popup). Off unless
# DEMO_BULK_TOKEN is set; the caller sends it in X-Demo-Token. These buyers are test
# accounts, not people: their emails start with "bulk-" under the reserved judge domain.

BULK_PREFIX = "bulk-"
BULK_ADDRESS = {
    "name": "Maxx Card Buyer",
    "line1": "1 Main St",
    "city": "San Jose",
    "region": "CA",
    "postal": "95131",
    "country": "US",
}


class BulkBuyer(BaseModel):
    bloc_id: str = Field(min_length=1, max_length=100)
    max_price: Decimal = Field(gt=0, le=1000, decimal_places=2)


class BulkBloc(BaseModel):
    bloc_id: str = Field(min_length=1, max_length=100)


def _bulk_allowed(token: str) -> None:
    expected = settings.demo_bulk_token
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(404, "Not found.")


@router.post("/bulk/buyer", status_code=201)
async def bulk_buyer(
    body: BulkBuyer, runtime: RuntimeDep, x_demo_token: str = Header(default="")
) -> dict:
    _bulk_allowed(x_demo_token)
    bloc = get_bloc(runtime, body.bloc_id)
    if is_private_copy(bloc):
        raise HTTPException(403, "Card buyers only join shared demo Blocs.")
    tag = uuid.uuid4().hex[:10]
    user = await asyncio.to_thread(
        auth_store.create_user,
        f"{BULK_PREFIX}{tag}{mail.JUDGE_DOMAIN}",
        f"Card buyer {tag[:4].upper()}",
        None,
        True,
    )
    fulfil_store.add_address(user.id, fulfil_store.Address(**BULK_ADDRESS))
    try:
        bloc, payment = await money.card_hold(runtime.store, bloc.id, user.id, body.max_price)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except PayPalError as exc:
        raise HTTPException(502, f"PayPal refused the hold: {exc.name or exc.status}") from None
    return {"authorization_id": payment["authorization_id"], "buyers": len(bloc.members)}


@router.post("/bulk/addresses")
def bulk_addresses(body: BulkBloc, x_demo_token: str = Header(default="")) -> dict:
    """Give each card buyer's won order its saved address, so the seller can ship it."""
    _bulk_allowed(x_demo_token)
    done = 0
    for order in fulfil_store.orders_where(bloc_id=body.bloc_id, status="AWAITING_ADDRESS"):
        user = auth_store.get_user(order["buyer_id"])
        if not user or not user.email.startswith(BULK_PREFIX):
            continue
        saved = fulfil_store.list_addresses(user.id)
        if saved:
            fulfil_service.set_address(user.id, order["id"], saved[0]["id"])
            done += 1
    return {"addressed": done}


@router.post("/bulk/reset")
async def bulk_reset(runtime: RuntimeDep, x_demo_token: str = Header(default="")) -> dict:
    """Restore the shared demo Blocs before a scripted run, like an administrator's reset."""
    _bulk_allowed(x_demo_token)
    async with runtime.lock:
        if any(b.status == "NEGOTIATING" for b in runtime.store.list()):
            raise HTTPException(409, "Wait for active negotiations to finish first.")
        runtime.seed(reset=True)
        return {b.id: b.status for b in runtime.store.list() if b.id.startswith("demo-")}
