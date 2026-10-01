"""
Session-based shopping list for API products.
"""

from flask import session


SESSION_KEY = "shopping_list"


def get_list():
    """Return the current shopping list dict."""
    return session.get(SESSION_KEY, {})


def add_item(product, quantity=1, cat_id=None):
    """
    Add a product (dict) with a quantity to the list.
    Optionally remembers which budget category it belongs to.
    """
    items = session.get(SESSION_KEY, {})

    barcode = str(product["id"])

    if barcode in items:
        items[barcode]["quantity"] += quantity
        # keep the category if it wasn't set before
        if cat_id is not None and not items[barcode].get("cat_id"):
            items[barcode]["cat_id"] = cat_id
    else:
        items[barcode] = {
            "barcode": barcode,
            "name": product["name"],
            "price": float(product["price"]),
            "shop_name": product["shop_name"],
            "image": product.get("image", "") or "",
            "category": product.get("category", "General") or "General",
            "quantity": quantity,
            "cat_id": cat_id,
        }

    session[SESSION_KEY] = items
    session.modified = True


def remove_item(barcode):
    """Remove a product from the list by barcode."""
    items = session.get(SESSION_KEY, {})
    items.pop(str(barcode), None)
    session[SESSION_KEY] = items
    session.modified = True


def clear_list():
    """Clear the whole list."""
    session.pop(SESSION_KEY, None)
    session.modified = True


def total_price():
    """Total price of all items in the list."""
    return sum(
        item["price"] * item["quantity"]
        for item in get_list().values()
    )


def total_for_category(cat_id):
    """
    Total price of all items in the list that belong to a given category.
    Used to enforce the estimated-price cap per category.
    """
    if cat_id is None:
        return 0.0

    cat_id = int(cat_id)

    return sum(
        item["price"] * item["quantity"]
        for item in get_list().values()
        if item.get("cat_id") == cat_id
    )


def quantity_in_category(barcode, cat_id):
    """How many of this barcode are already in the list for this category."""
    items = session.get(SESSION_KEY, {})
    key = str(barcode)

    if key not in items:
        return 0

    item = items[key]

    if cat_id is not None and item.get("cat_id") not in (None, int(cat_id)):
        return 0

    return item.get("quantity", 0)