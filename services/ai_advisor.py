"""
SmartShop AI — Cheapest Basket Advisor.

Rule-based intelligent agent that:
  - Reads the student's shopping list
  - Looks up live prices per item per store
  - Groups by store and computes basket totals
  - Finds the cheapest single store
  - Finds the cheapest complete basket
  - Shows alternatives for EVERY item (within a similar price range)
  - Warns if the basket exceeds any budget category
"""

import time
import re
from datetime import datetime


# ==========================================================
# TUNING
# ==========================================================

# An alternative is only considered "similar" if its price is
# between LOW_RATIO × current  and  HIGH_RATIO × current.
SIMILARITY_LOW = 0.60     # don't suggest anything below 60% of current
SIMILARITY_HIGH = 1.40    # don't suggest anything above 140% of current

# If the current item has a pack size ("2kg", "500ml"), we only
# match alternatives within this size ratio of the current size.
SIZE_RATIO_LOW = 0.50     # 2kg item accepts 1kg+ alternatives
SIZE_RATIO_HIGH = 2.00    # 2kg item accepts 4kg- alternatives


# ==========================================================
# CACHE
# ==========================================================

_CACHE = {}
_CACHE_TTL = 300  # 5 minutes


# ==========================================================
# PUBLIC ENTRY POINT
# ==========================================================

def analyse_basket(list_items, category_lookup=None):

    start = datetime.utcnow()

    if not list_items:
        return _empty_result(start)

    item_count = len(list_items)
    total_units = sum(int(i.get("quantity", 1)) for i in list_items)

    current_total = sum(
        float(i.get("price", 0)) * int(i.get("quantity", 1))
        for i in list_items
    )

    switches = []
    store_prices = {}

    for item in list_items:

        barcode = str(item.get("barcode") or item.get("id") or "")
        name = item.get("name", "Unknown")
        qty = int(item.get("quantity", 1))
        current_price = float(item.get("price", 0))
        current_store = item.get("shop_name", "Unknown")

        # Skip items with no price
        if current_price <= 0:
            continue

        # Get raw alternatives (unfiltered)
        raw_alts = _find_alternatives(barcode, name)

        # Filter to *similar* price and pack size
        alternatives = _filter_similar(
            raw_alts, current_price, name
        )

        if not alternatives:
            continue

        # Build a compact options list (max 3)
        options = []
        seen = set()

        for alt in alternatives[:5]:
            price = float(alt.get("price", 0))
            if price <= 0:
                continue

            key = (alt.get("shop_name", ""), round(price, 2))
            if key in seen:
                continue
            seen.add(key)

            options.append({
                "store": alt.get("shop_name", "Unknown"),
                "price": price,
                "name": alt.get("name", name),
                "image": alt.get("image", ""),
            })

            if len(options) >= 3:
                break

        if not options:
            continue

        cheapest = min(options, key=lambda o: o["price"])

        unit_saving = current_price - cheapest["price"]
        total_saving = unit_saving * qty

        is_worse = unit_saving > 0.01
        is_best = abs(unit_saving) <= 0.01

        switches.append({
            "barcode": barcode,
            "name": name,
            "quantity": qty,
            "current_price": current_price,
            "current_store": current_store,
            "options": options,
            "cheapest": cheapest,
            "savings": round(total_saving, 2) if is_worse else 0,
            "savings_pct": round(
                (unit_saving / current_price * 100) if current_price > 0 and is_worse else 0,
                1,
            ),
            "is_worse": is_worse,
            "is_best": is_best,
        })

        for opt in options:
            store = opt["store"]
            store_prices.setdefault(store, {})
            if barcode not in store_prices[store]:
                store_prices[store][barcode] = opt["price"] * qty

    # --------------------------------------------------
    # Per-store totals
    # --------------------------------------------------

    stores = []

    for store, prices in store_prices.items():

        store_total = sum(prices.values())
        items_found = len(prices)

        missing = [
            i.get("name", "Unknown")
            for i in list_items
            if str(i.get("barcode") or i.get("id") or "") not in prices
        ]

        savings = max(current_total - store_total, 0)

        stores.append({
            "name": store,
            "total": round(store_total, 2),
            "items_found": items_found,
            "items_total": item_count,
            "complete": items_found == item_count,
            "missing": missing,
            "savings": round(savings, 2),
        })

    stores.sort(key=lambda s: (not s["complete"], s["total"]))

    cheapest_single = next(
        (s for s in stores if s["complete"]),
        stores[0] if stores else None
    )

    cheapest_complete = next(
        (s for s in stores if s["complete"]),
        None
    )

    switches.sort(key=lambda s: (-s["savings"], s["name"]))

    total_savings = sum(sw["savings"] for sw in switches)

    budget_warnings = _check_budget(
        list_items, store_prices, category_lookup
    )

    elapsed_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

    return {
        "item_count": item_count,
        "total_units": total_units,
        "total_price": round(current_total, 2),
        "stores": stores,
        "cheapest_single": cheapest_single,
        "cheapest_complete": cheapest_complete,
        "switches": switches,
        "total_savings": round(total_savings, 2),
        "budget_warnings": budget_warnings,
        "thinking_time_ms": max(elapsed_ms, 250),
    }


# ==========================================================
# SIMILARITY FILTER
# ==========================================================

def _filter_similar(alternatives, current_price, current_name):
    """
    Keep only alternatives that are close to the current item:
      - Similar price (within SIMILARITY_LOW..SIMILARITY_HIGH)
      - Similar pack size (if both names contain a size)
    """
    if not alternatives:
        return []

    price_low = current_price * SIMILARITY_LOW
    price_high = current_price * SIMILARITY_HIGH

    current_size = _parse_size(current_name)

    filtered = []

    for alt in alternatives:
        alt_price = float(alt.get("price", 0))
        if alt_price <= 0:
            continue

        # Price band
        if not (price_low <= alt_price <= price_high):
            continue

        # Pack size band
        if current_size:
            alt_size = _parse_size(alt.get("name", ""))
            if alt_size:
                if not (
                    current_size * SIZE_RATIO_LOW
                    <= alt_size
                    <= current_size * SIZE_RATIO_HIGH
                ):
                    continue
            # If alt has NO size, keep it (could be same product with no size in name)

        filtered.append(alt)

    # Sort cheapest first
    filtered.sort(key=lambda p: p.get("price", 0))

    return filtered


def _parse_size(name):
    """
    Extract a normalised size from a product name.
    Returns a float in base units:
      - grams  → grams (500g → 500)
      - kg     → grams (2kg → 2000)
      - ml     → ml (500ml → 500)
      - L      → ml (2L → 2000)
    Returns None if no size found.
    """
    if not name:
        return None

    text = name.lower()

    # Match "2kg", "500 g", "2.5kg", "1.5 l", "750ml"
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(kg|g|gram|grams|ml|millilitre|milliliters?|l|litre|liter|litres|liters)\b",
        text,
    )

    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2)

    if unit == "kg":
        return value * 1000.0
    if unit in ("g", "gram", "grams"):
        return value
    if unit in ("l", "litre", "liter", "litres", "liters"):
        return value * 1000.0
    if unit in ("ml", "millilitre", "milliliters"):
        return value

    return None


# ==========================================================
# ALTERNATIVE FINDER (cached)
# ==========================================================

def _find_alternatives(barcode, name):
    key = f"{barcode}::{name}"
    now = time.time()

    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    alternatives = _find_alternatives_uncached(barcode, name)
    _CACHE[key] = (now, alternatives)
    return alternatives


def _find_alternatives_uncached(barcode, name):

    try:
        from services.grocery_api import (
            get_product_by_barcode,
            search_grocery_products,
        )
    except Exception:
        return []

    alternatives = []

    if barcode:
        p = get_product_by_barcode(barcode)
        if p:
            alternatives.append(p)

    if name:
        try:
            results = search_grocery_products(name)

            name_lower = name.lower()
            tokens = [
                t for t in name_lower.split()
                if len(t) > 2 and not t.isdigit()
            ]

            for r in results[:30]:
                r_name = (r.get("name") or "").lower()
                if any(t in r_name for t in tokens):
                    if not any(a["id"] == r["id"] for a in alternatives):
                        alternatives.append(r)
        except Exception:
            pass

    # Broaden if we have nothing
    if len(alternatives) < 2 and name:
        try:
            broad_term = name.split()[0] if name.split() else name
            extra = search_grocery_products(broad_term)

            for r in extra[:15]:
                if not any(a["id"] == r["id"] for a in alternatives):
                    alternatives.append(r)
        except Exception:
            pass

    alternatives.sort(key=lambda p: p.get("price", 0))
    return alternatives


# ==========================================================
# BUDGET CHECK
# ==========================================================

def _check_budget(list_items, store_prices, category_lookup):

    warnings = []

    if not category_lookup:
        return warnings

    by_cat = {}

    for item in list_items:
        cat_id = item.get("cat_id")
        if not cat_id:
            continue

        subtotal = float(item.get("price", 0)) * int(item.get("quantity", 1))
        by_cat[cat_id] = by_cat.get(cat_id, 0) + subtotal

    for cat_id, subtotal in by_cat.items():
        cat = category_lookup.get(cat_id)
        if not cat:
            continue

        limit = float(getattr(cat, "estimated", 0) or 0)
        if limit <= 0:
            continue

        if subtotal > limit:
            warnings.append({
                "category": getattr(cat, "label", "Category"),
                "over_by": round(subtotal - limit, 2),
                "spent": round(subtotal, 2),
                "limit": round(limit, 2),
            })

    return warnings


def _empty_result(start):
    return {
        "item_count": 0,
        "total_units": 0,
        "total_price": 0,
        "stores": [],
        "cheapest_single": None,
        "cheapest_complete": None,
        "switches": [],
        "total_savings": 0,
        "budget_warnings": [],
        "thinking_time_ms": int(
            (datetime.utcnow() - start).total_seconds() * 1000
        ),
    }