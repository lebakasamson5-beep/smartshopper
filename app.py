# ==========================================
# app.py — SmartShop AI
# ==========================================

import os

from flask import Flask, render_template
from flask_login import LoginManager

from config import Config
from models import db
from models.user import User
from models.product import Product
from models.budget import Budget, BudgetItem
from models.reservation import Reservation
from models.deal import Deal


# ==========================================
# CREATE APPLICATION
# ==========================================

def create_app():

    app = Flask(__name__)

    # ==========================================
    # LOAD CONFIGURATION
    # ==========================================

    app.config.from_object(Config)


    # ==========================================
    # INITIALIZE DATABASE
    # ==========================================

    db.init_app(app)


    # ==========================================
    # INITIALIZE LOGIN MANAGER
    # ==========================================

    login_manager = LoginManager()

    login_manager.init_app(app)

    login_manager.login_view = "auth.login"


    @login_manager.user_loader
    def load_user(user_id):

        return db.session.get(
            User,
            int(user_id)
        )


    # ==========================================
    # REGISTER ROUTES
    # ==========================================

    from routes.auth import auth
    from routes.student import student
    from routes.company import company
    from routes.admin import admin
    from routes.location import location

    app.register_blueprint(auth)
    app.register_blueprint(student)
    app.register_blueprint(company)
    app.register_blueprint(admin)
    app.register_blueprint(location)


    # ==========================================
    # CREATE DATABASE TABLES
    # ==========================================

    with app.app_context():

        db.create_all()


    # ==========================================
    # HOME PAGE
    # ==========================================

    @app.route("/")
    def home():

        return render_template("index.html")


    return app


# ==========================================
# CREATE APPLICATION INSTANCE
# ==========================================

app = create_app()


# ==========================================
# RUN APPLICATION (LOCAL ONLY)
# ==========================================
# This block only runs when you start the app
# locally with `py app.py`. On Railway, gunicorn
# imports `app` directly and starts its own server.

if __name__ == "__main__":

    # ------------------------------------------
    # OPTIONAL: TEST THE GROCERY API ON STARTUP
    # ------------------------------------------

    try:

        from services.grocery_api import search_grocery_products

        print("=" * 50)
        print("TESTING GROCERY API...")
        print("=" * 50)

        test_results = search_grocery_products("milk")

        print("=" * 50)
        print(f"API TEST RETURNED {len(test_results)} PRODUCTS")
        print("=" * 50)

    except Exception as e:

        print("=" * 50)
        print("API TEST FAILED:")
        print(e)
        print("=" * 50)

    # ------------------------------------------
    # START FLASK
    # ------------------------------------------

    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
    )