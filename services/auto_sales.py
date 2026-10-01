"""
Automatic sale + combo generator.

Called on app startup (see app.py) and via a manual route.
"""

import json
import random
import time
from datetime import datetime, timedelta

from models import db
from models.sale import Sale
from models.combo import Combo

from services.grocery_api import search_grocery_products


# ==========================================================
# TUNING
# ==========================================================

SEARCH_TERMS = [
    "chocolate",
    "snacks",
    "drinks",
    "dairy",
    "bread",
    "juice",
    "cereal",
    "cooldrink",
]

SALE_LABELS = [
    "Flash Sale",
    "Weekend Deal",
    "Hot Price",
    "Student Special",
    "Limited Time",
    "Save Now",
]

COMBO_TITLES = {
    "chocolate": "Chocolate Lover's Pack",
    "snacks":    "Snack Attack Bundle",
    "drinks":    "Refreshment Combo",
    "dairy":     "Dairy Essentials Pack",
    "bread":     "Breakfast Starter Pack",
    "juice":     "Juice Party Bundle",
    "cereal":    "Morning Energy Combo",
    "cooldrink": "Cool Drinks Bundle",
}

NUM_SALES = 15
NUM_FEATURED = 3
NUM_COMBOS = 5

SALE_DISCOUNT_MIN = 10
SALE_DISCOUNT_MAX = 35

COMBO_DISCOUNT_MIN = 15
COMBO_DISCOUNT_MAX = 25

COMBO_ITEMS_MIN = 2
COMBO_ITEMS_MAX = 4


# ==========================================================
# HELPERS
# ==========================================================

def _clean_expired():
    """Delete any sale or combo past its ends_on date."""
    today = datetime.utcnow().date()

    Sale.query.filter(Sale.ends_on < today).delete()
    Combo.query.filter(Combo.ends_on < today).delete()

    db.session.commit()


def _pick_random_products(pool, n):
    """n unique products from a pool, keyed by barcode."""
    seen = set()
    out = []

    random.shuffle(pool)

    for p in pool:
        barcode = str(p.get("id") or "")
        if not barcode or barcode in seen:
            continue
        seen.add(barcode)
        out.append(p)

        if len(out) >= n:
            break

    return out


def _build_pool():
    """Search the API across all terms and return a flat list."""
    pool = []

    for i, term in enumerate(SEARCH_TERMS):

        try:
            results = search_grocery_products(term)
        except Exception as e:
            print(f"[auto_sales] search failed for '{term}': {e}")
            continue

        for r in results:
            # Tag which term it came from (used for combo titles)
            r["_source_term"] = term
            pool.append(r)

        # Small delay between API calls to avoid 429
        if i < len(SEARCH_TERMS) - 1:
            time.sleep(0.5)

    return pool


# ==========================================================
# MAIN ENGINE
# ==========================================================

def auto_generate_sales(force=False):
    """
    Generate sales + combos.
    If force is False and we already have enough, does nothing.
    """

    _clean_expired()

    active_sales = Sale.query.filter(Sale.is_auto == True).count()
    active_combos = Combo.query.filter(Combo.is_auto == True).count()

    if not force and active_sales >= NUM_SALES and active_combos >= NUM_COMBOS:
        print("[auto_sales] enough sales already exist — skipping")
        return

    pool = _build_pool()

    if not pool:
        print("[auto_sales] no products from API — aborting")
        return

    print(f"[auto_sales] pool size: {len(pool)} products")

    today = datetime.utcnow().date()

    # --------------------------------------------------
    # 1. SALES
    # --------------------------------------------------

    if force:
        Sale.query.filter(Sale.is_auto == True).delete()
        db.session.commit()

    picks = _pick_random_products(pool, NUM_SALES)

    for idx, p in enumerate(picks):

        barcode = str(p["id"])

        existing = Sale.query.filter_by(barcode=barcode).first()
        if existing and not existing.is_auto:
            continue

        base_price = float(p.get("price") or 0)
        if base_price <= 0:
            continue

        discount = random.uniform(SALE_DISCOUNT_MIN, SALE_DISCOUNT_MAX)
        sale_price = round(base_price * (1 - discount / 100), 2)

        ends_on = today + timedelta(days=random.randint(5, 14))
        featured = idx < NUM_FEATURED

        if existing:
            existing.label = random.choice(SALE_LABELS)
            existing.original_price = base_price
            existing.sale_price = sale_price
            existing.discount_label = f"{int(round(discount))}% OFF"
            existing.starts_on = today
            existing.ends_on = ends_on
            existing.is_featured = featured
            existing.is_auto = True
        else:
            db.session.add(Sale(
                barcode=barcode,
                label=random.choice(SALE_LABELS),
                original_price=base_price,
                sale_price=sale_price,
                discount_label=f"{int(round(discount))}% OFF",
                starts_on=today,
                ends_on=ends_on,
                is_featured=featured,
                is_auto=True,
            ))

    db.session.commit()

    # --------------------------------------------------
    # 2. COMBOS
    # --------------------------------------------------

    if force:
        Combo.query.filter(Combo.is_auto == True).delete()
        db.session.commit()

    # Group pool by source term so combos feel cohesive
    by_term = {}
    for p in pool:
        term = p.get("_source_term", "misc")
        by_term.setdefault(term, []).append(p)

    usable_terms = [t for t, items in by_term.items() if len(items) >= COMBO_ITEMS_MIN]

    if len(usable_terms) < NUM_COMBOS:
        usable_terms = (usable_terms * 2)[:NUM_COMBOS]

    created_combos = 0

    for term in usable_terms[:NUM_COMBOS]:

        items = by_term.get(term, [])
        if len(items) < COMBO_ITEMS_MIN:
            continue

        size = random.randint(
            COMBO_ITEMS_MIN,
            min(COMBO_ITEMS_MAX, len(items))
        )

        chosen = _pick_random_products(items, size)
        if len(chosen) < COMBO_ITEMS_MIN:
            continue

        barcodes = [str(c["id"]) for c in chosen]
        original = sum(float(c.get("price") or 0) for c in chosen)
        if original <= 0:
            continue

        combo_discount = random.uniform(COMBO_DISCOUNT_MIN, COMBO_DISCOUNT_MAX)
        combo_price = round(original * (1 - combo_discount / 100), 2)

        ends_on = today + timedelta(days=random.randint(7, 14))
        title = COMBO_TITLES.get(term, f"{term.title()} Combo")
        image = chosen[0].get("image") or ""

        # ------------------------------------------
        # SNAPSHOTS (so we never lose the store name)
        # ------------------------------------------
        snapshots = []
        for c in chosen:
            snapshots.append({
                "id": str(c.get("id")),
                "name": c.get("name") or "",
                "price": float(c.get("price") or 0),
                "shop_name": c.get("shop_name") or "Unknown Store",
                "image": c.get("image") or "",
                "category": c.get("category") or "General",
            })

        db.session.add(Combo(
            title=title,
            description=(
                f"{size} items bundled together — "
                f"save {int(round(combo_discount))}% when you buy them as a set."
            ),
            barcodes_json=json.dumps(barcodes),
            snapshot_json=json.dumps(snapshots),
            original_price=round(original, 2),
            combo_price=combo_price,
            discount_label=f"SAVE {int(round(combo_discount))}%",
            image_url=image,
            starts_on=today,
            ends_on=ends_on,
            is_auto=True,
        ))

        created_combos += 1

    db.session.commit()

    print(
        f"[auto_sales] generated sales={Sale.query.count()} "
        f"combos={Combo.query.count()}"
    )


# ==========================================================
# BADGE HELPERS
# ==========================================================

def get_active_sales_map():
    """barcode → Sale"""
    today = datetime.utcnow().date()
    active = Sale.query.filter(Sale.ends_on >= today).all()
    return {s.barcode: s for s in active}


def get_active_combos_map():
    """barcode → [Combo, Combo, ...]"""
    today = datetime.utcnow().date()
    combos = Combo.query.filter(Combo.ends_on >= today).all()

    lookup = {}
    for c in combos:
        for b in c.barcodes:
            lookup.setdefault(b, []).append(c)

    return lookup