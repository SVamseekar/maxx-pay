"""Demo-only endpoints for judges. Refused unless the demo setup is on (see tour.enabled)."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from maxx.auth import ratelimit
from maxx.auth.deps import CurrentUser, same_origin
from maxx.demo import tour
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


@router.post("/lab/{scenario}", status_code=201)
def open_lab(scenario: str, runtime: RuntimeDep, user: CurrentUser):
    """The judge's own copy of a demo scenario: same simulated crowd and sellers, but nobody
    else's seat, hold or finished outcome is in it, so it never needs a reset. Unlisted, like
    the seller tour; an unfinished copy is reused rather than duplicated."""
    if scenario not in DEMO_CROWD:
        raise HTTPException(404, "Not found.")
    return {"bloc_id": lab_copy(runtime, user.id, scenario)}


def lab_copy(runtime, user_id: str, scenario: str) -> str:
    """The person's open private copy of a demo scenario, made if they have none."""
    for bloc in runtime.store.list_for_user(user_id):
        if (
            bloc.id.startswith(f"lab-{scenario}-")
            and bloc.owner_id == user_id
            and bloc.status == "OPEN"
            and bloc.closes_at > time.time()
        ):
            return bloc.id
    ratelimit.hit(f"demo-lab:{user_id}", 12, 3600)
    ratelimit.hit("demo-lab:all", 600, 3600)
    tag = uuid.uuid4().hex[:12]
    bloc = runtime.scenario_bloc(f"lab-{scenario}-{tag}", scenario, runtime.mode)
    bloc.product_key = f"demo-lab:{user_id[:8]}:{scenario}:{tag}"
    bloc.owner_id = user_id
    runtime.store.create(bloc)
    return bloc.id
