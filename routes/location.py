from flask import Blueprint, render_template, request, jsonify
from math import radians, sin, cos, sqrt, atan2

location = Blueprint("location", __name__)


def calculate_distance(lat1, lon1, lat2, lon2):

    R = 6371.0

    lat1 = radians(lat1)
    lat2 = radians(lat2)

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return R * c


@location.route("/locations")
def locations():

    return render_template(
        "location_search.html"
    )


@location.route("/locations/search", methods=["POST"])
def search_locations():

    data = request.get_json()

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    product = data.get("product", "").strip()

    if latitude is None or longitude is None:

        return jsonify({
            "success": False,
            "message": "Location is required."
        }), 400

    if not product:

        return jsonify({
            "success": False,
            "message": "Please enter a product."
        }), 400

    # ------------------------------------------------
    # STORE SEARCH WILL BE CONNECTED TO YOUR DATABASE
    # AFTER WE SEE YOUR STORE MODEL.
    # ------------------------------------------------

    stores = []

    return jsonify({
        "success": True,
        "product": product,
        "stores": stores
    })
