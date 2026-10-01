from app import app
from models.product import Product
from models.user import User
from models.reservation import Reservation

with app.app_context():

    print("\n========== PRODUCTS ==========")

    products = Product.query.all()

    for product in products:

        company = None

        if product.company_id:
            company = User.query.get(product.company_id)

        print(
            "Product:",
            product.name,
            "| Company ID:",
            product.company_id,
            "| Company:",
            company.email if company else "NONE"
        )

    print("\n========== RESERVATIONS ==========")

    reservations = Reservation.query.all()

    for reservation in reservations:

        print(
            "Reservation:",
            reservation.id,
            "| Product:",
            reservation.product.name,
            "| Product Company ID:",
            reservation.product.company_id,
            "| Student:",
            reservation.user.email,
            "| Status:",
            reservation.status
        )
