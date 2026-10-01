from datetime import datetime

from models import db


# ==========================================================
# CATEGORY DEFINITIONS (used by the wizard)
# ==========================================================

CATEGORY_DEFS = [
    {"key": "groceries",     "label": "Groceries",     "icon": "🛒", "compare": True},
    {"key": "transport",     "label": "Transport",     "icon": "🚌", "compare": False},
    {"key": "entertainment", "label": "Entertainment", "icon": "🎬", "compare": False},
    {"key": "cosmetics",     "label": "Cosmetics",     "icon": "💄", "compare": True},
    {"key": "electronics",   "label": "Electronics",   "icon": "🔌", "compare": True},
    {"key": "clothing",      "label": "Clothing",      "icon": "👕", "compare": False},
    {"key": "stationery",    "label": "Stationery",    "icon": "📚", "compare": True},
    {"key": "airtime",       "label": "Airtime/Data",  "icon": "📱", "compare": False},
    {"key": "other",         "label": "Other",         "icon": "✏️",  "compare": False},
]


def get_category_def(key):
    for c in CATEGORY_DEFS:
        if c["key"] == key:
            return c
    return None


# ==========================================================
# BUDGET
# ==========================================================

class Budget(db.Model):

    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    month = db.Column(
        db.String(7),
        nullable=False
    )

    monthly_limit = db.Column(
        db.Float,
        default=0
    )

    # ------------------------------------------
    # WIZARD STATE
    # ------------------------------------------

    current_step = db.Column(
        db.Integer,
        default=1
    )

    is_complete = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # ------------------------------------------
    # RELATIONSHIPS
    # ------------------------------------------

    items = db.relationship(
        "BudgetItem",
        backref="budget",
        cascade="all, delete-orphan",
        lazy=True
    )

    categories = db.relationship(
        "BudgetCategory",
        backref="budget",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Budget {self.month} user={self.user_id}>"


# ==========================================================
# BUDGET CATEGORY (Step 2 + Step 3)
# ==========================================================

class BudgetCategory(db.Model):

    __tablename__ = "budget_categories"

    id = db.Column(db.Integer, primary_key=True)

    budget_id = db.Column(
        db.Integer,
        db.ForeignKey("budgets.id"),
        nullable=False
    )

    key = db.Column(
        db.String(40),
        nullable=False
    )

    label = db.Column(
        db.String(80),
        nullable=False
    )

    estimated = db.Column(
        db.Float,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # ------------------------------------------
    # HELPERS
    # ------------------------------------------

    @property
    def icon(self):
        c = get_category_def(self.key)
        return c["icon"] if c else "•"

    @property
    def has_compare(self):
        c = get_category_def(self.key)
        return bool(c and c["compare"])

    def __repr__(self):
        return f"<BudgetCategory {self.key} R{self.estimated}>"


# ==========================================================
# BUDGET ITEM (kept for the Compare Prices page)
# ==========================================================

class BudgetItem(db.Model):

    __tablename__ = "budget_items"

    id = db.Column(db.Integer, primary_key=True)

    budget_id = db.Column(
        db.Integer,
        db.ForeignKey("budgets.id"),
        nullable=False
    )

    name = db.Column(
        db.String(200),
        nullable=False
    )

    estimated_price = db.Column(
        db.Float,
        default=0
    )

    quantity = db.Column(
        db.Integer,
        default=1
    )

    real_price = db.Column(db.Float, nullable=True)
    real_shop = db.Column(db.String(100), nullable=True)
    real_product_name = db.Column(db.String(300), nullable=True)
    real_image = db.Column(db.String(500), nullable=True)

    price_status = db.Column(
        db.String(20),
        default="unknown"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def estimated_subtotal(self):
        return (self.estimated_price or 0) * (self.quantity or 1)

    def real_subtotal(self):
        if self.real_price is None:
            return None
        return self.real_price * (self.quantity or 1)

    def subtotal(self):
        return self.estimated_subtotal()

    def __repr__(self):
        return f"<BudgetItem {self.name} x{self.quantity}>"