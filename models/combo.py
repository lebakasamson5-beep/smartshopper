import json
from datetime import datetime

from models import db


class Combo(db.Model):

    __tablename__ = "combos"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # JSON-encoded list of barcodes
    barcodes_json = db.Column(db.Text, nullable=False, default="[]")

    # JSON-encoded list of product snapshots (so we don't hit the API)
    snapshot_json = db.Column(db.Text, nullable=False, default="[]")

    original_price = db.Column(db.Float, default=0)
    combo_price = db.Column(db.Float, default=0)
    discount_label = db.Column(db.String(20), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)

    starts_on = db.Column(db.Date, default=datetime.utcnow)
    ends_on = db.Column(db.Date, nullable=False)

    is_auto = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    # ==========================================
    # BARCODES
    # ==========================================

    @property
    def barcodes(self):
        try:
            return json.loads(self.barcodes_json or "[]")
        except (ValueError, TypeError):
            return []

    @barcodes.setter
    def barcodes(self, values):
        self.barcodes_json = json.dumps(list(values or []))


    # ==========================================
    # PRODUCTS (cached snapshots)
    # ==========================================

    @property
    def products(self):
        try:
            return json.loads(self.snapshot_json or "[]")
        except (ValueError, TypeError):
            return []

    @products.setter
    def products(self, values):
        self.snapshot_json = json.dumps(list(values or []))


    # ==========================================
    # STORE NAMES
    # ==========================================

    @property
    def shop_names(self):
        """Unique list of store names across items in this combo."""
        seen = []
        for p in self.products:
            shop = (p.get("shop_name") or "").strip()
            if shop and shop not in seen:
                seen.append(shop)
        return seen

    @property
    def shop_names_display(self):
        """'Checkers · Shoprite · Pick n Pay' — or fallback text."""
        names = self.shop_names
        if not names:
            return "Various stores"
        return " · ".join(names)


    # ==========================================
    # STATUS
    # ==========================================

    @property
    def is_active(self):
        today = datetime.utcnow().date()
        if self.starts_on and self.starts_on > today:
            return False
        return self.ends_on >= today

    @property
    def days_left(self):
        delta = (self.ends_on - datetime.utcnow().date()).days
        return max(delta, 0)

    @property
    def savings(self):
        return max((self.original_price or 0) - (self.combo_price or 0), 0)


    def __repr__(self):
        return f"<Combo {self.title} R{self.combo_price}>"