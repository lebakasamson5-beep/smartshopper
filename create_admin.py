from app import app
from models import db
from models.user import User

with app.app_context():

    admin = User.query.filter_by(
        email="admin@smartshop.com"
    ).first()

    if admin:
        admin.role = "admin"
        admin.name = "SmartShop Administrator"
        admin.set_password("admin123")
        db.session.commit()
        print("Admin account updated successfully.")

    else:
        admin = User(
            name="SmartShop Administrator",
            email="admin@smartshop.com",
            role="admin"
        )

        admin.set_password("admin123")

        db.session.add(admin)
        db.session.commit()

        print("Admin account created successfully.")
