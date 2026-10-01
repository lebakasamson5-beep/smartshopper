from datetime import datetime

from models import db


class Product(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    category = db.Column(
        db.String(100),
        nullable=False
    )

    price = db.Column(
        db.Float,
        nullable=False
    )

    stock_quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    shop_name = db.Column(
        db.String(150),
        nullable=False
    )

    location = db.Column(
        db.String(200),
        nullable=True
    )

    image = db.Column(
        db.String(255),
        nullable=True
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def __repr__(self):

        return f"<Product {self.name}>"
