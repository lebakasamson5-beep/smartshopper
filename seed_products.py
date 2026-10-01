from app import app
from models import db
from models.product import Product


with app.app_context():

    # Prevent duplicate sample products
    if Product.query.count() > 0:

        print("Products already exist.")

    else:

        products = [

            Product(
                name="Student Hoodie",
                description="Comfortable hoodie suitable for campus.",
                category="Clothing",
                price=299.99,
                stock_quantity=15,
                shop_name="Student Fashion",
                location="Durban"
            ),

            Product(
                name="Basic T-Shirt",
                description="Affordable everyday student T-shirt.",
                category="Clothing",
                price=149.99,
                stock_quantity=30,
                shop_name="Student Fashion",
                location="Durban"
            ),

            Product(
                name="Campus Backpack",
                description="Durable backpack for books and laptops.",
                category="Accessories",
                price=249.99,
                stock_quantity=20,
                shop_name="Campus Store",
                location="Durban"
            ),

            Product(
                name="Wireless Earphones",
                description="Wireless earphones for studying and entertainment.",
                category="Electronics",
                price=349.99,
                stock_quantity=10,
                shop_name="Tech Zone",
                location="Durban"
            ),

            Product(
                name="Running Sneakers",
                description="Comfortable sneakers for everyday use.",
                category="Footwear",
                price=599.99,
                stock_quantity=8,
                shop_name="Urban Steps",
                location="Durban"
            ),

            Product(
                name="Student Watch",
                description="Affordable everyday wrist watch.",
                category="Accessories",
                price=399.99,
                stock_quantity=12,
                shop_name="Style Hub",
                location="Durban"
            )

        ]


        db.session.add_all(products)

        db.session.commit()


        print("Sample products successfully added!")
