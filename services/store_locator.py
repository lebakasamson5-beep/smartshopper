"""
Server-side store locator.

Tries Overpass first, falls back to a bundled static list
if Overpass is unavailable (which happens often with the
free public endpoints).
"""

import os
import json
import time
import requests


# ==========================================================
# CONFIG
# ==========================================================

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

USER_AGENT = "SmartShopAI/1.0 (student project)"

BRANDS = ["Shoprite", "Pick n Pay", "SPAR", "Checkers", "Boxer"]

# Per-endpoint timeout (short so we don't hang for minutes)
TIMEOUT_SECONDS = 8

# Only one try per endpoint now (retries made it worse)
MAX_ATTEMPTS_PER_ENDPOINT = 1

# Static fallback file
FALLBACK_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "stores_fallback.json"
)


# ==========================================================
# MAIN API
# ==========================================================

def find_stores_near(latitude, longitude, radius_meters=5000):
    """
    Try Overpass. If that fails, fall back to the bundled list.
    Always returns a list (possibly empty).
    """

    print(f"[store_locator] looking for stores near {latitude},{longitude} "
          f"within {radius_meters}m")

    # -------- Try Overpass --------
    stores = _query_overpass_stores(latitude, longitude, radius_meters)

    if stores:
        print(f"[store_locator] Overpass OK: {len(stores)} stores")
        return stores

    # -------- Fall back to bundled list --------
    print("[store_locator] Overpass unavailable — using fallback list")
    return _get_fallback_stores(latitude, longitude, radius_meters)


# ==========================================================
# OVERPASS
# ==========================================================

def _query_overpass_stores(latitude, longitude, radius_meters):

    regex = "|".join(BRANDS)

    query = f"""
        [out:json][timeout:8];

        (
            node(around:{radius_meters},{latitude},{longitude})
            ["name"~"{regex}",i];

            way(around:{radius_meters},{latitude},{longitude})
            ["name"~"{regex}",i];
        );

        out center tags;
    """

    data = _query_overpass(query)

    if not data:
        return []

    elements = data.get("elements", [])

    stores = []
    seen = set()

    for element in elements:

        tags = element.get("tags", {}) or {}

        lat = element.get("lat")
        lon = element.get("lon")

        if lat is None and element.get("center"):
            lat = element["center"].get("lat")
            lon = element["center"].get("lon")

        if lat is None or lon is None:
            continue

        name = (
            tags.get("name")
            or tags.get("brand")
            or tags.get("operator")
            or "Store"
        )

        brand = _identify_brand(
            name,
            tags.get("brand", ""),
            tags.get("operator", ""),
        )

        if not brand:
            continue

        key = (brand, round(lat, 4), round(lon, 4))
        if key in seen:
            continue
        seen.add(key)

        stores.append({
            "name": name,
            "brand": brand,
            "brand_name": _brand_display(brand),
            "latitude": lat,
            "longitude": lon,
            "address": _build_address(tags),
        })

    return stores


def _query_overpass(query):

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    for endpoint in OVERPASS_ENDPOINTS:

        for attempt in range(MAX_ATTEMPTS_PER_ENDPOINT):

            try:

                print(f"[store_locator] {endpoint} (attempt {attempt+1})")

                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers=headers,
                    timeout=TIMEOUT_SECONDS,
                )

                if response.status_code == 200:
                    print(f"[store_locator] OK {endpoint}")
                    return response.json()

                print(f"[store_locator] {endpoint} -> {response.status_code}")

            except requests.exceptions.RequestException as e:
                print(f"[store_locator] {endpoint} failed: {e}")

    return None


# ==========================================================
# FALLBACK: BUNDLED STORES
# ==========================================================

def _get_fallback_stores(latitude, longitude, radius_meters):

    if not os.path.exists(FALLBACK_FILE):
        print(f"[store_locator] fallback file missing: {FALLBACK_FILE}")
        return []

    try:
        with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
            all_stores = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[store_locator] fallback parse error: {e}")
        return []

    # Filter by distance
    nearby = []

    for store in all_stores:

        d = _haversine_meters(
            latitude, longitude,
            store["latitude"], store["longitude"]
        )

        if d <= radius_meters:
            store["distance_m"] = int(d)
            nearby.append(store)

    nearby.sort(key=lambda s: s.get("distance_m", 9999999))

    return nearby


def _haversine_meters(lat1, lon1, lat2, lon2):

    from math import radians, sin, cos, atan2, sqrt

    R = 6371000

    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)

    a = (
        sin(dLat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2))
        * sin(dLon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


# ==========================================================
# HELPERS
# ==========================================================

def _identify_brand(name, brand, operator):

    text = f"{name} {brand} {operator}".lower()

    if "shoprite" in text: return "shoprite"
    if "pick n pay" in text or "picknpay" in text: return "pnp"
    if "superspar" in text or "kwikspar" in text or "spar" in text: return "spar"
    if "checkers" in text: return "checkers"
    if "boxer" in text: return "boxer"

    return None


def _brand_display(brand):

    return {
        "shoprite": "Shoprite",
        "pnp": "Pick n Pay",
        "spar": "SPAR",
        "checkers": "Checkers",
        "boxer": "Boxer",
    }.get(brand, brand.title())


def _build_address(tags):

    parts = []

    for key in ("addr:housenumber", "addr:street",
                "addr:suburb", "addr:city", "addr:postcode"):
        value = tags.get(key)
        if value:
            parts.append(str(value))

    return ", ".join(parts) if parts else "Address not available"