from app import app
from models.user import User

with app.app_context():

    print("\n========== USERS ==========")

    users = User.query.all()

    for user in users:

        print(
            "ID:",
            user.id,
            "| Name:",
            user.name,
            "| Email:",
            user.email,
            "| Role:",
            user.role
        )
