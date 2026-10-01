from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash
)

from flask_login import login_required, current_user

from models import db
from models.user import User
from models.product import Product
from models.deal import Deal
from models.reservation import Reservation


admin = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


# ==========================================================
# ADMIN ACCESS CONTROL
# ==========================================================

def admin_required():

    if not current_user.is_authenticated:
        return False

    return current_user.role == "admin"


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@admin.route("/dashboard")
@login_required
def dashboard():

    if not admin_required():
        return "Access denied", 403

    total_users = User.query.count()

    total_students = User.query.filter_by(
        role="student"
    ).count()

    total_companies = User.query.filter_by(
        role="company"
    ).count()

    total_products = Product.query.count()

    total_reservations = Reservation.query.count()

    total_deals = Deal.query.count()

    pending_deals = Deal.query.filter_by(
        status="pending"
    ).count()

    approved_deals = Deal.query.filter_by(
        status="approved"
    ).count()

    rejected_deals = Deal.query.filter_by(
        status="rejected"
    ).count()

    return render_template(
        "admin/dashboard.html",

        total_users=total_users,
        total_students=total_students,
        total_companies=total_companies,
        total_products=total_products,
        total_reservations=total_reservations,

        total_deals=total_deals,
        pending_deals=pending_deals,
        approved_deals=approved_deals,
        rejected_deals=rejected_deals
    )


# ==========================================================
# USERS
# ==========================================================

@admin.route("/users")
@login_required
def users():

    if not admin_required():
        return "Access denied", 403

    users = User.query.order_by(
        User.id.desc()
    ).all()

    return render_template(
        "admin/users.html",
        users=users
    )


# ==========================================================
# COMPANIES
# ==========================================================

@admin.route("/companies")
@login_required
def companies():

    if not admin_required():
        return "Access denied", 403

    companies = User.query.filter_by(
        role="company"
    ).order_by(
        User.id.desc()
    ).all()

    return render_template(
        "admin/companies.html",
        companies=companies
    )


# ==========================================================
# PRODUCTS
# ==========================================================

@admin.route("/products")
@login_required
def products():

    if not admin_required():
        return "Access denied", 403

    products = Product.query.order_by(
        Product.created_at.desc()
    ).all()

    return render_template(
        "admin/products.html",
        products=products
    )


# ==========================================================
# DEALS
# ==========================================================

@admin.route("/deals")
@login_required
def deals():

    if not admin_required():
        return "Access denied", 403

    deals = Deal.query.order_by(
        Deal.created_at.desc()
    ).all()

    total_deals = Deal.query.count()

    pending_deals = Deal.query.filter_by(
        status="pending"
    ).count()

    approved_deals = Deal.query.filter_by(
        status="approved"
    ).count()

    rejected_deals = Deal.query.filter_by(
        status="rejected"
    ).count()

    return render_template(
        "admin/deals.html",

        deals=deals,

        total_deals=total_deals,
        pending_deals=pending_deals,
        approved_deals=approved_deals,
        rejected_deals=rejected_deals
    )


# ==========================================================
# APPROVE DEAL
# ==========================================================

@admin.route(
    "/deals/approve/<int:deal_id>",
    methods=["POST"]
)
@login_required
def approve_deal(deal_id):

    if not admin_required():
        return "Access denied", 403

    deal = db.session.get(
        Deal,
        deal_id
    )

    if not deal:

        flash(
            "Deal not found.",
            "error"
        )

        return redirect(
            url_for("admin.deals")
        )

    if deal.status != "pending":

        flash(
            "This deal is not waiting for approval.",
            "error"
        )

        return redirect(
            url_for("admin.deals")
        )

    deal.status = "approved"

    db.session.commit()

    flash(
        "Deal approved successfully.",
        "success"
    )

    return redirect(
        url_for("admin.deals")
    )


# ==========================================================
# REJECT DEAL
# ==========================================================

@admin.route(
    "/deals/reject/<int:deal_id>",
    methods=["POST"]
)
@login_required
def reject_deal(deal_id):

    if not admin_required():
        return "Access denied", 403

    deal = db.session.get(
        Deal,
        deal_id
    )

    if not deal:

        flash(
            "Deal not found.",
            "error"
        )

        return redirect(
            url_for("admin.deals")
        )

    if deal.status != "pending":

        flash(
            "This deal is not waiting for approval.",
            "error"
        )

        return redirect(
            url_for("admin.deals")
        )

    deal.status = "rejected"

    db.session.commit()

    flash(
        "Deal rejected successfully.",
        "success"
    )

    return redirect(
        url_for("admin.deals")
    )