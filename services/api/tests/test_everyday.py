"""Everyday demo products: each opens a private Bloc priced for that product, and the web app
lists exactly the same products."""

import asyncio
import re
from decimal import Decimal

from fastapi.testclient import TestClient

from maxx.config import ROOT, settings
from maxx.demo import catalogue
from maxx.main import app
from maxx.negotiate.adapters import FixtureAdapter
from maxx.negotiate.blocs import transition
from maxx.negotiate.runner import run_negotiation
from tests.conftest import sign_up
from tests.test_fulfilment import runtime as runtime  # noqa: F401 - shared fixture


def test_the_web_app_lists_the_same_products_at_the_same_prices():
    web = (ROOT / "apps/web/app/lib/everyday.ts").read_text()
    rows = re.findall(r'id: "([^"]+)", name: "[^"]+", title: "([^"]+)", typical: (\d+)', web)
    assert [(i, t, Decimal(p)) for i, t, p in rows] == [
        (p.id, p.title, p.typical) for p in catalogue.PRODUCTS
    ]


def test_products_are_listed_with_illustrative_prices(runtime):  # noqa: F811
    with TestClient(app) as client:
        rows = client.get("/demo/products").json()
    assert len(rows) == len(catalogue.PRODUCTS) == 10
    pods = next(r for r in rows if r["id"] == "laundry-pods")
    assert pods["typical_price"] == "33" and pods["unit_count"] == 96


def test_each_product_opens_its_own_private_bloc_priced_for_it(runtime, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "paypal_mode", "off")
    with TestClient(app) as judge:
        sign_up(judge, "judge@example.com", "Jude")
        assert judge.post("/demo/lab/success?product=nonsense").status_code == 404
        skillet = judge.post("/demo/lab/success?product=skillet").json()["bloc_id"]
        mixer = judge.post("/demo/lab/success?product=stand-mixer").json()["bloc_id"]
        assert skillet != mixer
        assert judge.post("/demo/lab/success?product=skillet").json()["bloc_id"] == skillet
        assert judge.post("/demo/lab/success").json()["bloc_id"] not in {skillet, mixer}
        view = judge.get(f"/blocs/{skillet}").json()
    assert view["title"] == "Demo cast iron skillet · 12-inch"
    assert Decimal(view["typical_price"]) == Decimal("35")
    limits = {Decimal(m["max_price"]) for m in view["members"]}
    assert max(limits) == Decimal("35.00") and min(limits) == Decimal("22.75")
    assert len(view["members"]) == 600 and all(m["simulated"] for m in view["members"])


def test_a_cheap_everyday_product_negotiates_to_prices_inside_every_limit(runtime):  # noqa: F811
    bloc = runtime.scenario_bloc("lab-success-test", "success", "fixture", "laundry-pods")
    transition(bloc, "NEGOTIATING")
    runtime.store.create(bloc)
    asyncio.run(run_negotiation(runtime.store, bloc.id, FixtureAdapter(), round_delay=0))
    done = runtime.store.get(bloc.id)
    assert done.status == "SETTLED" and done.outcome.allocations
    limits = {m.id: m.max_price for m in done.members}
    assert all(a.price <= limits[a.member_id] for a in done.outcome.allocations)
    assert all(a.price < Decimal("33") for a in done.outcome.allocations)


def test_the_three_shared_demo_scenarios_show_three_different_products(runtime):  # noqa: F811
    titles = {runtime.store.get(f"demo-{s}").title for s in ("success", "failure", "flaky")}
    assert titles == {
        "Demo headphones · Black",
        "Demo stand mixer · 4.5 qt",
        "Demo air purifier · HEPA",
    }
    # A judge's private copy of a scenario uses the same product as the shared one.
    copy = runtime.scenario_bloc("lab-failure-x", "failure", "fixture")
    assert copy.title == "Demo stand mixer · 4.5 qt" and copy.typical_price == Decimal("230")
