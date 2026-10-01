from datetime import datetime

from models import db


class Sale(db.Model):

    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)

    barcode = db.Column(db.String(100), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=True)

    original_price = db.Column(db.Float, nullable=True)
    sale_price = db.Column(db.Float, nullable=True)
    discount_label = db.Column(db.String(20), nullable=True)

    starts_on = db.Column(db.Date, nullable=True, default=datetime.utcnow)
    ends_on = db.Column(db.Date, nullable=False)

    is_featured = db.Column(db.Boolean, default=False)
    is_auto = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ------------------------------------------
    # HELPERS
    # ------------------------------------------

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

    def __repr__(self):
        return f"<Sale {self.barcode} ends {self.ends_on}>"