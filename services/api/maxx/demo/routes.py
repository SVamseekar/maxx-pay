"""Demo-only endpoints for judges. Refused unless the demo setup is on (see tour.enabled)."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from maxx.auth import ratelimit
from maxx.auth.deps import CurrentUser, same_origin
from maxx.demo import catalogue, tour
from maxx.negotiate.routes import DEMO_CROWD, RuntimeDep
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
