"""Everyday demo products a person can try in their own private Bloc.

Every product is made up: no brand, no merchant, no stock. Each typical price is illustrative,
anchored to an ordinary US price for that kind of item in 2025-2026 (decision note
docs/internal/decisions/2026-11-11-everyday-product-variety.md). The web app shows the same list
from apps/web/app/lib/everyday.ts; tests/test_everyday.py keeps the two in step.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Product:
    id: str
    title: str
    typical: Decimal
    moment: str
    unit_count: int | None = None  # consumables: how many units in one pack
    unit_noun: str | None = None


PRODUCTS: tuple[Product, ...] = (
    Product("skillet", "Demo cast iron skillet · 12-inch", Decimal("35"), "Kitchen"),
    Product("air-fryer", "Demo air fryer · 6 qt", Decimal("120"), "Kitchen"),
    Product("stand-mixer", "Demo stand mixer · 4.5 qt", Decimal("230"), "Kitchen"),
    Product("air-purifier", "Demo air purifier · HEPA", Decimal("190"), "Home"),
    Product("laundry-pods", "Demo laundry pods · 96 loads", Decimal("33"), "Home", 96, "load"),
    Product("toothbrush", "Demo sonic toothbrush", Decimal("60"), "Care"),
    Product("diapers", "Demo diapers · Size 3, 160", Decimal("45"), "Family", 160, "diaper"),
    Product("stroller", "Demo travel stroller", Decimal("300"), "Family"),
    Product("dog-food", "Demo dry dog food · 30 lb", Decimal("55"), "Pets", 30, "lb"),
    Product("headphones", "Demo headphones · Black", Decimal("200"), "Listening"),
)

BY_ID = {p.id: p for p in PRODUCTS}
BY_TITLE = {p.title: p for p in PRODUCTS}
DEFAULT = BY_ID["headphones"]
# Each shared demo scenario shows a different product, so the Blocs list is not three of the same
# thing. The successful deal keeps the headphones shown in the submission video.
SCENARIO_PRODUCT = {"success": "headphones", "failure": "stand-mixer", "flaky": "air-purifier"}


def for_scenario(scenario: str, product: str | None = None) -> Product:
    return BY_ID[product or SCENARIO_PRODUCT.get(scenario, DEFAULT.id)]
