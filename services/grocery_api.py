import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

GROCERY_API_KEY = os.getenv("GROCERY_API_KEY")
GROCERY_API_URL = os.getenv("GROCERY_API_URL")


# ==========================================================
# FILTERS
# ==========================================================

# Only products with a FINAL (post-sale) price >= this value
# will be shown to the user.
MIN_PRODUCT_PRICE = 10.0


# ==========================================================
# SYNTHETIC PRICING
# ==========================================================
#
# The LoyaltyHub API returns placeholder prices (R2, R1.50) for
# most products. We compute a realistic price from:
#   1. The pack size in the name ("2kg", "500ml", "1L")
#   2. The product category
#   3. The barcode (deterministic — same barcode → same price)
#
# Set to False to use raw API prices.
# ==========================================================

USE_SYNTHETIC_PRICES = True


# Price per base unit (R per kg, R per L, or R per item).
# Ranges: (min, max) — a value is chosen deterministically inside.
# Tuples are checked in order; first keyword match wins.
_UNIT_PRICES = [
    # -------- Staples (per kg) --------
    (("rice", "basmati", "jasmine"), "kg", 22, 45),
    (("maize", "mealie", "pap", "samp"), "kg", 15, 35),
    (("flour", "cake flour", "bread flour"), "kg", 15, 30),
    (("sugar", "brown sugar", "white sugar"), "kg", 18, 35),
    (("pasta", "spaghetti", "macaroni", "noodle"), "kg", 25, 60),
    (("oats", "muesli", "cereal", "corn flakes"), "kg", 40, 90),
    (("lentils", "beans", "chickpeas"), "kg", 25, 55),
    (("salt", "spice", "pepper", "masala"), "kg", 30, 80),

    # -------- Liquids (per L) --------
    (("oil", "olive oil", "sunflower oil", "canola"), "L", 45, 120),
    (("milk", "fresh milk", "long life milk"), "L", 18, 35),
    (("juice", "orange juice", "apple juice"), "L", 20, 45),
    (("cooldrink", "coke", "pepsi", "sprite", "fanta"), "L", 15, 30),
    (("water", "still water", "sparkling water"), "L", 6, 15),
    (("yoghurt", "amasi", "maas"), "L", 25, 55),
    (("vinegar", "sauce", "ketchup", "tomato sauce"), "L", 25, 60),
    (("cleaner", "bleach", "detergent", "fabric softener"), "L", 30, 70),
    (("shampoo", "conditioner", "body wash", "lotion"), "L", 60, 180),

    # -------- Per kg (meat / cheese / deli) --------
    (("chicken", "beef", "lamb", "pork", "mince", "steak"), "kg", 80, 200),
    (("fish", "hake", "salmon", "tuna"), "kg", 90, 220),
    (("cheese", "gouda", "cheddar", "feta"), "kg", 120, 280),
    (("bacon", "ham", "sausage", "vienna"), "kg", 70, 180),

    # -------- Per 100g (snacks, chocolate, coffee) --------
    (("chocolate", "slab", "bar", "bunny"), "g100", 10, 40),
    (("coffee", "nescaf", "rico", "jacobs"), "g100", 25, 90),
    (("tea", "rooibos", "five roses", "black tea"), "g100", 12, 40),
    (("biscuit", "cookie", "cracker", "wafer"), "g100", 8, 25),
    (("chips", "simba", "lays", "niknaks", "crisps"), "g100", 10, 30),
    (("nuts", "peanuts", "almonds", "cashews"), "g100", 15, 45),
    (("sweets", "candy", "jelly", "gums"), "g100", 8, 25),

    # -------- Per item (produce, bread, eggs) --------
    (("bread", "loaf", "roll", "bun", "bagel"), "item", 12, 40),
    (("egg", "eggs"), "item", 20, 55),      # per 6-pack
    (("apple", "banana", "orange", "pear"), "kg", 20, 40),
    (("potato", "onion", "carrot", "tomato"), "kg", 15, 35),

    # -------- Household per item --------
    (("toothpaste", "toothbrush", "deodorant"), "item", 20, 70),
    (("soap", "bar soap"), "item", 10, 30),
    (("tissue", "toilet paper", "paper towel"), "item", 20, 90),
    (("dish", "sponge", "cloth"), "item", 15, 40),

    # -------- Baby --------
    (("baby", "purity", "infant", "nappy", "diaper"), "item", 15, 90),

    # -------- Pet --------
    (("cat food", "dog food", "pet food"), "kg", 40, 120),
]


def _parse_size(name):
    """
    Extract (amount, unit) from a product name.
    Returns (value, 'kg'|'L'|'item').
    """
    if not name:
        return None

    text = name.lower()

    # Match patterns like "1kg", "500 g", "2.5kg", "1.5 l", "750ml", "100ml"
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(kg|g|gram|grams|ml|millilitre|milliliters?|l|litre|liter|litres|liters)\b",
        text,
    )

    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2)

    # Normalise to kg, L, or g
    if unit in ("kg",):
        return (value, "kg")

    if unit in ("g", "gram", "grams"):
        # 1000g = 1kg, 100g unit for coffee/chocolate categories
        return (value / 1000.0, "kg")

    if unit in ("l", "litre", "liter", "litres", "liters"):
        return (value, "L")

    if unit in ("ml", "millilitre", "milliliters"):
        return (value / 1000.0, "L")

    return None


def _synthetic_price(barcode, name):
    """
    Deterministic realistic price from barcode + name + pack size.
    """
    if not barcode:
        return 25.0

    # ---------------- seed ----------------
    seed = 0
    for ch in str(barcode):
        seed = (seed * 31 + ord(ch)) & 0xFFFFFFFF

    name_lower = (name or "").lower()

    # ---------------- find matching category ----------------
    unit_type = None
    low, high = 20, 80   # default range

    for keywords, unit, mn, mx in _UNIT_PRICES:
        if any(kw in name_lower for kw in keywords):
            unit_type = unit
            low, high = mn, mx
            break

    # ---------------- pick a value from the range ----------------
    span = high - low
    unit_price = low + (seed % (span * 100)) / 100.0

    # ---------------- parse the pack size ----------------
    size_info = _parse_size(name)

    # ---------------- compute final price ----------------

    # Case 1: category is per kg or per L
    if unit_type in ("kg", "L"):

        if size_info:
            amount, unit = size_info

            # If the pack is in kg but the category is L (or vice versa),
            # treat them as equivalent (1kg ≈ 1L for pricing purposes)
            price = unit_price * amount

        else:
            # No size found — assume a typical 1kg / 1L pack
            price = unit_price

    # Case 2: category is per 100g (chocolate, coffee, etc.)
    elif unit_type == "g100":

        if size_info:
            amount, unit = size_info
            if unit == "kg":
                grams = amount * 1000
            else:
                grams = amount  # default
            # unit_price is R per 100g
            price = unit_price * (grams / 100.0)

        else:
            # Assume a typical 100g pack
            price = unit_price

    # Case 3: category is per item (bread, eggs, soap, etc.)
    elif unit_type == "item":

        # For per-item pricing, size doesn't affect the price
        # UNLESS the name mentions multi-packs like "6 pack" or "2 x 500g"
        # For simplicity: if a size is present, scale it
        if size_info:
            amount, unit = size_info
            if unit == "kg":
                price = unit_price * max(amount, 1)
            elif unit == "L":
                price = unit_price * max(amount, 1)
            else:
                price = unit_price
        else:
            price = unit_price

    # Case 4: no match — use fallback
    else:
        if size_info:
            amount, unit = size_info
            if unit == "kg":
                price = low * max(amount, 1)
            elif unit == "L":
                price = low * max(amount, 1)
            else:
                price = low
        else:
            price = low

    # ---------------- clamp to sane bounds ----------------
    price = max(price, 5.0)
    price = min(price, 500.0)

    return round(price, 2)


# ==========================================================
# HELPERS
# ==========================================================

def _extract_items(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("data", "results", "items", "products", "prices"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def _normalise(item):

    product = item.get("product") or {}
    retailer = item.get("retailer") or {}

    # ---------------- NAME ----------------
    name = (
        item.get("name")
        or product.get("name")
        or item.get("title")
        or "Unknown Product"
    )

    # ---------------- RAW PRICE ----------------
    raw_price = (
        item.get("price")
        or item.get("current_price")
        or item.get("amount")
        or 0
    )
    try:
        raw_price = float(raw_price)
    except (TypeError, ValueError):
        raw_price = 0.0

    # ---------------- BARCODE ----------------
    barcode = (
        item.get("barcode")
        or product.get("barcode")
        or item.get("retailer_sku")
        or name
    )

    # ---------------- FINAL PRICE ----------------
    if USE_SYNTHETIC_PRICES:
        price = _synthetic_price(barcode, name)
    else:
        price = raw_price

    # ---------------- SHOP NAME ----------------
    shop_name = (
        item.get("shop_name")
        or item.get("store")
        or item.get("store_name")
        or item.get("retailer_name")
        or (retailer.get("name") if isinstance(retailer, dict) else retailer)
        or "Unknown Store"
    )
    if isinstance(shop_name, str):
        shop_name = shop_name.capitalize()

    # ---------------- IMAGE ----------------
    image = (
        item.get("image")
        or item.get("image_url")
        or product.get("image")
        or product.get("image_url")
        or ""
    )

    # ---------------- CATEGORY ----------------
    category = (
        item.get("category")
        or product.get("category")
        or "General"
    )

    # ---------------- DESCRIPTION ----------------
    description = (
        item.get("description")
        or product.get("description")
        or ""
    )

    # ---------------- STOCK ----------------
    stock = (
        item.get("stock_quantity")
        or item.get("stock")
        or 10
    )
    try:
        stock = int(stock)
    except (TypeError, ValueError):
        stock = 10

    # ---------------- LOCATION ----------------
    location = (
        item.get("location")
        or item.get("store_location")
        or ""
    )

    return {
        "id": str(barcode),
        "name": name,
        "price": price,
        "shop_name": shop_name,
        "image": image,
        "category": category,
        "description": description,
        "stock_quantity": stock,
        "location": location,
    }


def _apply_price_filter(products):
    """Keep only products whose CURRENT price is >= MIN_PRODUCT_PRICE."""
    if MIN_PRODUCT_PRICE <= 0:
        return products

    return [
        p for p in products
        if float(p.get("price") or 0) >= MIN_PRODUCT_PRICE
    ]


# ==========================================================
# SEARCH PRODUCTS
# ==========================================================

def search_grocery_products(search_term):

    if not GROCERY_API_KEY or not GROCERY_API_URL:
        print("❌ Missing GROCERY_API_KEY or GROCERY_API_URL in .env")
        return []

    headers = {
        "Authorization": f"Bearer {GROCERY_API_KEY}",
        "Accept": "application/json",
    }

    params = {"search": search_term, "limit": 50}

    try:
        response = requests.get(
            GROCERY_API_URL,
            headers=headers,
            params=params,
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        print("❌ Request failed:", e)
        return []

    print("API STATUS:", response.status_code)

    if response.status_code != 200:
        return []

    try:
        data = response.json()
    except ValueError:
        print("❌ API did not return JSON")
        return []

    raw_items = _extract_items(data)
    products = [_normalise(item) for item in raw_items]

    products.sort(key=lambda p: p["price"])

    return products


# ==========================================================
# GET ONE PRODUCT BY BARCODE
# ==========================================================

def get_product_by_barcode(barcode):

    if not GROCERY_API_KEY or not GROCERY_API_URL:
        return None

    headers = {
        "Authorization": f"Bearer {GROCERY_API_KEY}",
        "Accept": "application/json",
    }

    params = {"barcode": barcode, "limit": 1}

    try:
        response = requests.get(
            GROCERY_API_URL,
            headers=headers,
            params=params,
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        print("❌ Barcode request failed:", e)
        return None

    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    items = _extract_items(data)

    if not items:
        return None

    return _normalise(items[0])


# ==========================================================
# GET RELATED PRODUCTS
# ==========================================================

def get_related_products(category, exclude_barcode=None, limit=4):

    if not GROCERY_API_KEY or not GROCERY_API_URL:
        return []

    headers = {
        "Authorization": f"Bearer {GROCERY_API_KEY}",
        "Accept": "application/json",
    }

    search_term = category if category and category != "General" else "food"

    params = {"search": search_term, "limit": limit + 5}

    try:
        response = requests.get(
            GROCERY_API_URL,
            headers=headers,
            params=params,
            timeout=15,
        )
    except requests.exceptions.RequestException:
        return []

    if response.status_code != 200:
        return []

    try:
        data = response.json()
    except ValueError:
        return []

    items = _extract_items(data)
    products = [_normalise(i) for i in items]

    if exclude_barcode:
        products = [p for p in products if p["id"] != str(exclude_barcode)]

    return products[:limit]


# ==========================================================
# FIND BEST PRICE
# ==========================================================

def find_best_price(product_name):

    results = search_grocery_products(product_name)

    if not results:
        return None

    return results[0]


# ==========================================================
# ATTACH SALE + COMBO BADGES + FILTER
# ==========================================================

def attach_sales(products):
    """
    Merge Sale + Combo data from local DB, then apply the
    price filter (>= MIN_PRODUCT_PRICE) on the FINAL price.
    """
    if not products:
        return products

    try:
        from services.auto_sales import (
            get_active_sales_map,
            get_active_combos_map,
        )
    except Exception as e:
        print(f"[attach_sales] skipped: {e}")
        return _apply_price_filter(products)

    sales = get_active_sales_map()
    combos = get_active_combos_map()

    for p in products:

        barcode = str(p.get("id"))

        # ---------- SALE ----------
        sale = sales.get(barcode)

        if sale:
            p["on_sale"] = True
            p["sale_label"] = sale.label or "Sale"
            p["sale_discount"] = sale.discount_label or ""
            p["sale_days_left"] = sale.days_left
            p["sale_ends_on"] = sale.ends_on.isoformat()
            p["sale_original_price"] = sale.original_price

            if sale.sale_price is not None:
                if "original_price" not in p:
                    p["original_price"] = p.get("price")
                p["price"] = float(sale.sale_price)
        else:
            p["on_sale"] = False

        # ---------- COMBO ----------
        in_combos = combos.get(barcode, [])

        if in_combos:
            p["in_combo"] = True
            p["combo_titles"] = [c.title for c in in_combos]
        else:
            p["in_combo"] = False

    # ---------- FINAL FILTER ----------
    products = _apply_price_filter(products)

    return products