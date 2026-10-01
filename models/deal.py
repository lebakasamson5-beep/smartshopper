from datetime import datetime

from models import db


class Deal(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=True
    )

    title = db.Column(
        db.String(150),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    original_price = db.Column(
        db.Float,
        nullable=False
    )

    sale_price = db.Column(
        db.Float,
        nullable=False
    )

    start_date = db.Column(
        db.Date,
        nullable=False
    )

    end_date = db.Column(
        db.Date,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    company = db.relationship(
        "User",
        backref="deals"
    )

    product = db.relationship(
        "Product",
        backref="deals"
    )

    def discount_percentage(self):

        if self.original_price <= 0:
            return 0

        discount = (
            (self.original_price - self.sale_price)
            / self.original_price
        ) * 100

        return round(discount, 2)

    def __repr__(self):

        return f"<Deal {self.title}>"
