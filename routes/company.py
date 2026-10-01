from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from flask_login import login_required, current_user

from models import db
from models.deal import Deal
from models.product import Product
from models.reservation import Reservation


company = Blueprint(
    "company",
    __name__,
    url_prefix="/company"
)


# ==========================================================
# COMPANY DASHBOARD
# ==========================================================

@company.route("/dashboard")
@login_required
def dashboard():

    if current_user.role != "company":
        return "Access denied", 403

    products = Product.query.filter_by(
        company_id=current_user.id
    ).order_by(
        Product.created_at.desc()
    ).all()

    total_products = len(products)

    total_stock = sum(
        product.stock_quantity
        for product in products
    )

    # Get reservations belonging to this company
    product_ids = [
        product.id
        for product in products
    ]

    total_reservations = 0

    if product_ids:

        total_reservations = Reservation.query.filter(
            Reservation.product_id.in_(product_ids)
        ).count()

    # Get company deals
    total_deals = Deal.query.filter_by(
        company_id=current_user.id
    ).count()

    pending_deals = Deal.query.filter_by(
        company_id=current_user.id,
        status="pending"
    ).count()

    approved_deals = Deal.query.filter_by(
        company_id=current_user.id,
        status="approved"
    ).count()

    return render_template(
        "company/dashboard.html",
        products=products,
        total_products=total_products,
        total_stock=total_stock,
        total_reservations=total_reservations,
        total_deals=total_deals,
        pending_deals=pending_deals,
        approved_deals=approved_deals
    )


# ==========================================================
# ADD PRODUCT
# ==========================================================

@company.route("/products/add", methods=["GET", "POST"])
@login_required
def add_product():

    if current_user.role != "company":
        return "Access denied", 403

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        price = request.form.get(
            "price",
            ""
        ).strip()

        stock_quantity = request.form.get(
            "stock_quantity",
            ""
        ).strip()

        shop_name = request.form.get(
            "shop_name",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        if (
            not name
            or not category
            or not price
            or not stock_quantity
            or not shop_name
        ):

            flash(
                "Please complete all required fields.",
                "error"
            )

            return redirect(
                url_for("company.add_product")
            )

        try:

            price = float(price)
            stock_quantity = int(stock_quantity)

        except ValueError:

            flash(
                "Price must be a number and stock must be a whole number.",
                "error"
            )

            return redirect(
                url_for("company.add_product")
            )

        if price < 0:

            flash(
                "Price cannot be negative.",
                "error"
            )

            return redirect(
                url_for("company.add_product")
            )

        if stock_quantity < 0:

            flash(
                "Stock quantity cannot be negative.",
                "error"
            )

            return redirect(
                url_for("company.add_product")
            )

        product = Product(
            name=name,
            description=description,
            category=category,
            price=price,
            stock_quantity=stock_quantity,
            shop_name=shop_name,
            location=location,
            company_id=current_user.id
        )

        db.session.add(product)

        db.session.commit()

        flash(
            "Product successfully added.",
            "success"
        )

        return redirect(
            url_for("company.dashboard")
        )

    return render_template(
        "company/products.html"
    )


# ==========================================================
# DELETE PRODUCT
# ==========================================================

@company.route(
    "/products/delete/<int:product_id>",
    methods=["POST"]
)
@login_required
def delete_product(product_id):

    if current_user.role != "company":
        return "Access denied", 403

    product = Product.query.filter_by(
        id=product_id,
        company_id=current_user.id
    ).first()

    if not product:

        flash(
            "Product not found.",
            "error"
        )

        return redirect(
            url_for("company.dashboard")
        )

    db.session.delete(product)

    db.session.commit()

    flash(
        "Product deleted successfully.",
        "success"
    )

    return redirect(
        url_for("company.dashboard")
    )


# ==========================================================
# UPDATE STOCK
# ==========================================================

@company.route(
    "/products/stock/<int:product_id>",
    methods=["POST"]
)
@login_required
def update_stock(product_id):

    if current_user.role != "company":
        return "Access denied", 403

    product = Product.query.filter_by(
        id=product_id,
        company_id=current_user.id
    ).first()

    if not product:

        flash(
            "Product not found.",
            "error"
        )

        return redirect(
            url_for("company.dashboard")
        )

    stock = request.form.get(
        "stock_quantity",
        ""
    ).strip()

    try:

        stock = int(stock)

    except ValueError:

        flash(
            "Stock must be a whole number.",
            "error"
        )

        return redirect(
            url_for("company.dashboard")
        )

    if stock < 0:

        flash(
            "Stock cannot be negative.",
            "error"
        )

        return redirect(
            url_for("company.dashboard")
        )

    product.stock_quantity = stock

    db.session.commit()

    flash(
        "Stock updated successfully.",
        "success"
    )

    return redirect(
        url_for("company.dashboard")
    )


# ==========================================================
# COMPANY RESERVATIONS
# ==========================================================

@company.route("/reservations")
@login_required
def reservations():

    if current_user.role != "company":
        return "Access denied", 403

    products = Product.query.filter_by(
        company_id=current_user.id
    ).all()

    product_ids = [
        product.id
        for product in products
    ]

    if product_ids:

        reservations = Reservation.query.filter(
            Reservation.product_id.in_(product_ids)
        ).order_by(
            Reservation.created_at.desc()
        ).all()

    else:

        reservations = []

    return render_template(
        "company/reservations.html",
        reservations=reservations
    )


# ==========================================================
# APPROVE RESERVATION
# ==========================================================

@company.route(
    "/reservations/approve/<int:reservation_id>",
    methods=["POST"]
)
@login_required
def approve_reservation(reservation_id):

    if current_user.role != "company":
        return "Access denied", 403

    reservation = db.session.get(
        Reservation,
        reservation_id
    )

    if not reservation:

        flash(
            "Reservation not found.",
            "error"
        )

        return redirect(
            url_for("company.reservations")
        )

    product = Product.query.filter_by(
        id=reservation.product_id,
        company_id=current_user.id
    ).first()

    if not product:
        return "Access denied", 403

    if reservation.status != "active":

        flash(
            "This reservation is no longer active.",
            "error"
        )

        return redirect(
            url_for("company.reservations")
        )

    reservation.status = "approved"

    db.session.commit()

    flash(
        "Reservation approved successfully.",
        "success"
    )

    return redirect(
        url_for("company.reservations")
    )


# ==========================================================
# REJECT RESERVATION
# ==========================================================

@company.route(
    "/reservations/reject/<int:reservation_id>",
    methods=["POST"]
)
@login_required
def reject_reservation(reservation_id):

    if current_user.role != "company":
        return "Access denied", 403

    reservation = db.session.get(
        Reservation,
        reservation_id
    )

    if not reservation:

        flash(
            "Reservation not found.",
            "error"
        )

        return redirect(
            url_for("company.reservations")
        )

    product = Product.query.filter_by(
        id=reservation.product_id,
        company_id=current_user.id
    ).first()

    if not product:
        return "Access denied", 403

    if reservation.status not in [
        "active",
        "approved"
    ]:

        flash(
            "This reservation cannot be rejected.",
            "error"
        )

        return redirect(
            url_for("company.reservations")
        )

    reservation.status = "rejected"

    db.session.commit()

    flash(
        "Reservation rejected.",
        "success"
    )

    return redirect(
        url_for("company.reservations")
    )


# ==========================================================
# COMPANY DEALS
# ==========================================================

@company.route("/deals")
@login_required
def deals():

    if current_user.role != "company":
        return "Access denied", 403

    deals = Deal.query.filter_by(
        company_id=current_user.id
    ).order_by(
        Deal.created_at.desc()
    ).all()

    products = Product.query.filter_by(
        company_id=current_user.id
    ).order_by(
        Product.name.asc()
    ).all()

    return render_template(
        "company/deals.html",
        deals=deals,
        products=products
    )


# ==========================================================
# ADD DEAL
# ==========================================================

@company.route(
    "/deals/add",
    methods=["POST"]
)
@login_required
def add_deal():

    if current_user.role != "company":
        return "Access denied", 403

    # ------------------------------------------------------
    # GET FORM DATA
    # ------------------------------------------------------

    title = request.form.get(
        "title",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    product_id = request.form.get(
        "product_id",
        ""
    ).strip()

    sale_price = request.form.get(
        "sale_price",
        ""
    ).strip()

    start_date = request.form.get(
        "start_date",
        ""
    ).strip()

    end_date = request.form.get(
        "end_date",
        ""
    ).strip()

    # ------------------------------------------------------
    # VALIDATE BASIC FIELDS
    # ------------------------------------------------------

    if not title:

        flash(
            "Please enter a deal title.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    if not product_id:

        flash(
            "Please select a product.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    if not sale_price:

        flash(
            "Please enter a sale price.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    if not start_date or not end_date:

        flash(
            "Please select the deal start and end dates.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    # ------------------------------------------------------
    # CONVERT PRODUCT ID
    # ------------------------------------------------------

    try:

        product_id = int(product_id)

    except ValueError:

        flash(
            "Invalid product selected.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    # ------------------------------------------------------
    # FIND PRODUCT
    #
    # IMPORTANT:
    # The product must belong to the logged-in company.
    # ------------------------------------------------------

    product = Product.query.filter_by(
        id=product_id,
        company_id=current_user.id
    ).first()

    if not product:

        flash(
            "Selected product was not found.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    # ------------------------------------------------------
    # GET ORIGINAL PRICE FROM DATABASE
    # ------------------------------------------------------

    original_price = product.price

    # ------------------------------------------------------
    # CONVERT SALE PRICE
    # ------------------------------------------------------

    try:

        sale_price = float(
            sale_price
        )

    except ValueError:

        flash(
            "Sale price must be a valid number.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    # ------------------------------------------------------
    # VALIDATE SALE PRICE
    # ------------------------------------------------------

    if sale_price < 0:

        flash(
            "Sale price cannot be negative.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    if sale_price >= original_price:

        flash(
            "Sale price must be lower than the original product price.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    # ------------------------------------------------------
    # CONVERT DATES
    # ------------------------------------------------------

    try:

        from datetime import datetime

        start_date_obj = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()

        end_date_obj = datetime.strptime(
            end_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        flash(
            "Please enter valid dates.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    # ------------------------------------------------------
    # VALIDATE DATE RANGE
    # ------------------------------------------------------

    if end_date_obj < start_date_obj:

        flash(
            "End date cannot be before the start date.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    # ------------------------------------------------------
    # CREATE DEAL
    #
    # New deals start as PENDING.
    # Admin must approve them before students can see them.
    # ------------------------------------------------------

    deal = Deal(
        company_id=current_user.id,
        product_id=product.id,
        title=title,
        description=description,
        original_price=original_price,
        sale_price=sale_price,
        start_date=start_date_obj,
        end_date=end_date_obj,
        status="pending"
    )

    db.session.add(deal)

    db.session.commit()

    flash(
        "Deal submitted successfully and is waiting for admin approval.",
        "success"
    )

    return redirect(
        url_for("company.deals")
    )


# ==========================================================
# DELETE DEAL
# ==========================================================

@company.route(
    "/deals/delete/<int:deal_id>",
    methods=["POST"]
)
@login_required
def delete_deal(deal_id):

    if current_user.role != "company":
        return "Access denied", 403

    deal = Deal.query.filter_by(
        id=deal_id,
        company_id=current_user.id
    ).first()

    if not deal:

        flash(
            "Deal not found.",
            "error"
        )

        return redirect(
            url_for("company.deals")
        )

    db.session.delete(deal)

    db.session.commit()

    flash(
        "Deal deleted successfully.",
        "success"
    )

    return redirect(
        url_for("company.deals")
    )


# ==========================================================
# EDIT PRODUCT
# ==========================================================

@company.route(
    "/products/edit/<int:product_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_product(product_id):

    if current_user.role != "company":
        return "Access denied", 403

    product = Product.query.filter_by(
        id=product_id,
        company_id=current_user.id
    ).first()

    if not product:

        flash(
            "Product not found.",
            "error"
        )

        return redirect(
            url_for("company.dashboard")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        price = request.form.get(
            "price",
            ""
        ).strip()

        stock_quantity = request.form.get(
            "stock_quantity",
            ""
        ).strip()

        shop_name = request.form.get(
            "shop_name",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        # --------------------------------------------------
        # VALIDATE REQUIRED FIELDS
        # --------------------------------------------------

        if (
            not name
            or not category
            or not price
            or not stock_quantity
            or not shop_name
        ):

            flash(
                "Please complete all required fields.",
                "error"
            )

            return redirect(
                url_for(
                    "company.edit_product",
                    product_id=product.id
                )
            )

        # --------------------------------------------------
        # CONVERT PRICE AND STOCK
        # --------------------------------------------------

        try:

            price = float(price)
            stock_quantity = int(stock_quantity)

        except ValueError:

            flash(
                "Price must be a number and stock must be a whole number.",
                "error"
            )

            return redirect(
                url_for(
                    "company.edit_product",
                    product_id=product.id
                )
            )

        # --------------------------------------------------
        # VALIDATE VALUES
        # --------------------------------------------------

        if price < 0:

            flash(
                "Price cannot be negative.",
                "error"
            )

            return redirect(
                url_for(
                    "company.edit_product",
                    product_id=product.id
                )
            )

        if stock_quantity < 0:

            flash(
                "Stock cannot be negative.",
                "error"
            )

            return redirect(
                url_for(
                    "company.edit_product",
                    product_id=product.id
                )
            )

        # --------------------------------------------------
        # UPDATE PRODUCT
        # --------------------------------------------------

        product.name = name
        product.description = description
        product.category = category
        product.price = price
        product.stock_quantity = stock_quantity
        product.shop_name = shop_name
        product.location = location

        db.session.commit()

        flash(
            "Product updated successfully.",
            "success"
        )

        return redirect(
            url_for("company.dashboard")
        )

    return render_template(
        "company/edit_product.html",
        product=product
    )