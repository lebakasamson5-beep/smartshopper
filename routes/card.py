import json, os, uuid
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DATA = os.path.join(os.path.dirname(__file__), "cards.json")

# Shop presets: name, background, text colour
PRESETS = [
    {"shop": "Checkers Xtra Savings", "bg": "#e2231a", "fg": "#ffffff"},
    {"shop": "Woolworths WRewards",   "bg": "#1d1d1b", "fg": "#ffffff"},
    {"shop": "SPAR Rewards",          "bg": "#007a3d", "fg": "#ffffff"},
    {"shop": "Pick n Pay Smart Shopper", "bg": "#0a4ea3", "fg": "#ffffff"},
    {"shop": "Clicks ClubCard",       "bg": "#00a0dd", "fg": "#ffffff"},
    {"shop": "Dis-Chem Benefit",      "bg": "#78be20", "fg": "#10230a"},
]
FORMATS = ["CODE128", "EAN13", "EAN8", "UPC", "CODE39", "ITF"]


def load():
    try:
        with open(DATA) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(cards):
    with open(DATA, "w") as f:
        json.dump(cards, f, indent=2)


@app.get("/")
def index():
    return render_template("index.html", presets=PRESETS, formats=FORMATS)


@app.get("/api/cards")
def list_cards():
    return jsonify(load())


@app.post("/api/cards")
def add_card():
    d = request.get_json(force=True)
    shop = (d.get("shop") or "").strip()
    number = "".join((d.get("number") or "").split())
    if not shop or not number:
        return jsonify(error="Shop name and card number are required."), 400
    card = {
        "id": uuid.uuid4().hex[:8],
        "shop": shop[:60],
        "number": number[:40],
        "format": d.get("format") if d.get("format") in FORMATS else "CODE128",
        "bg": d.get("bg") or "#333333",
        "fg": d.get("fg") or "#ffffff",
    }
    cards = load()
    cards.append(card)
    save(cards)
    return jsonify(card), 201


@app.delete("/api/cards/<cid>")
def delete_card(cid):
    save([c for c in load() if c["id"] != cid])
    return "", 204


if __name__ == "__main__":
    # host 0.0.0.0 lets your phone open it on the same Wi-Fi: http://<pc-ip>:5000
    app.run(host="0.0.0.0", port=5000, debug=True)