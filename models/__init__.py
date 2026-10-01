from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# --------------------------------------------------
# Import every model here so SQLAlchemy knows about
# all tables BEFORE create_all() runs.
# ORDER MATTERS: User first, then the rest.
# --------------------------------------------------

from models.user import User
from models.product import Product
from models.budget import Budget, BudgetItem, BudgetCategory
from models.reservation import Reservation
from models.deal import Deal
from models.sale import Sale
from models.combo import Combo