import json
import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify
)


from flask_login import login_required, current_user

from models import db
from models.product import Product
from models.budget import (
    Budget,
    BudgetItem,
    BudgetCategory,
    CATEGORY_DEFS,
    get_category_def,
)
from models.reservation import Reservation
from models.sale import Sale
from models.combo import Combo

from services.grocery_api import (
    search_grocery_products,
    get_product_by_barcode,
    get_related_products,
    find_best_price,
    attach_sales,
)
from services.auto_sales import auto_generate_sales
from services import shopping_list
from services.ai_advisor import analyse_basket
from services.store_locator import find_stores_near


student = Blueprint(
    "student",
    __name__,
    url_prefix="/student"
)


# ==========================================================
# HELPERS
# ==========================================================

def _require_student():
    if current_user.role != "student":
        return False
    return True


def get_current_budget():

    month = datetime.now().strftime("%Y-%m")

    budget = Budget.query.filter_by(
        user_id=current_user.id,
        month=month
    ).first()

    if not budget:

        budget = Budget(
            user_id=current_user.id,
            month=month,
            monthly_limit=0,
            current_step=1,
            is_complete=False
        )

        db.session.add(budget)
        db.session.commit()

    return budget


# ==========================================================
# STUDENT DASHBOARD
# ==========================================================

@student.route("/dashboard")
@login_required
def dashboard():

    if not _require_student():
        return "Access denied", 403

    today = datetime.utcnow().date()

    # ------------------------------------------
    # FEATURED DEALS
    # ------------------------------------------
    featured_sales = (
        Sale.query
        .filter(Sale.ends_on >= today)
        .filter(Sale.is_featured == True)
        .order_by(Sale.ends_on.asc())
        .limit(3)
        .all()
    )

    featured_deals = []
    for s in featured_sales:
        prod = get_product_by_barcode(s.barcode)
        if not prod:
            continue

        prod["on_sale"] = True
        prod["sale_label"] = s.label or "Sale"
        prod["sale_discount"] = s.discount_label or ""
        prod["sale_days_left"] = s.days_left
        prod["sale_original_price"] = s.original_price

        if s.sale_price is not None:
            prod["original_price"] = prod.get("price")
            prod["price"] = float(s.sale_price)

        featured_deals.append(prod)

    # ------------------------------------------
    # COMBOS (exactly 5)
    # ------------------------------------------
    combos = (
        Combo.query
        .filter(Combo.ends_on >= today)
        .order_by(Combo.ends_on.asc())
        .limit(5)
        .all()
    )

    return render_template(
        "student/dashboard.html",
        featured_deals=featured_deals,
        combos=combos,
    )


# ==========================================================
# STUDENT PROFILE
# ==========================================================

@student.route("/profile")
@login_required
def profile():

    if not _require_student():
        return "Access denied", 403

    return render_template("student/profile.html")


# ==========================================================
# PRODUCTS (marketplace — browse only)
# ==========================================================

@student.route("/products")
@login_required
def products():

    if not _require_student():
        return "Access denied", 403

    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "")

    products = []

    if search:

        products = search_grocery_products(search)

        # attach_sales returns the FILTERED list (≥ R10 post-sale)
        products = attach_sales(products)

        if sort == "high":
            products.sort(key=lambda p: p["price"], reverse=True)
        elif sort == "low":
            products.sort(key=lambda p: p["price"])

        for p in products:
            p["is_api"] = True

    else:

        query = Product.query

        if sort == "low":
            query = query.order_by(Product.price.asc())
        elif sort == "high":
            query = query.order_by(Product.price.desc())
        else:
            query = query.order_by(Product.created_at.desc())

        db_products = query.all()

        products = [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "shop_name": p.shop_name,
                "image": p.image,
                "category": p.category,
                "description": p.description,
                "stock_quantity": p.stock_quantity,
                "location": p.location,
                "is_api": False,
                "on_sale": False,
                "in_combo": False,
            }
            for p in db_products
        ]

    return render_template(
        "student/products.html",
        products=products,
        search=search,
        sort=sort
    )


# ==========================================================
# PRODUCT DETAIL
# ==========================================================

@student.route("/product/<barcode>")
@login_required
def product_detail(barcode):

    if not _require_student():
        return "Access denied", 403

    product = get_product_by_barcode(barcode)

    if not product:
        try:
            db_product = db.session.get(Product, int(barcode))
        except (ValueError, TypeError):
            db_product = None

        if db_product:
            product = {
                "id": db_product.id,
                "name": db_product.name,
                "price": db_product.price,
                "shop_name": db_product.shop_name,
                "image": db_product.image,
                "category": db_product.category,
                "description": db_product.description,
                "stock_quantity": db_product.stock_quantity,
                "location": db_product.location,
                "is_api": False,
            }

    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("student.products"))

    if "is_api" not in product:
        product["is_api"] = True

    # attach_sales now returns the FILTERED list
    result = attach_sales([product])

    if not result:
        flash(
            "This product is currently unavailable (priced under R10).",
            "error"
        )
        return redirect(url_for("student.products"))

    product = result[0]

    related = get_related_products(
        category=product.get("category", ""),
        exclude_barcode=barcode,
        limit=4,
    )

    for r in related:
        r["is_api"] = True

    related = attach_sales(related)

    return render_template(
        "student/product_detail.html",
        product=product,
        related=related,
    )


# ==========================================================
# COMBO DETAIL
# ==========================================================

@student.route("/combo/<int:combo_id>")
@login_required
def combo_detail(combo_id):

    if not _require_student():
        return "Access denied", 403

    combo = db.session.get(Combo, combo_id)

    if not combo:
        flash("Combo not found.", "error")
        return redirect(url_for("student.dashboard"))

    products = []
    for barcode in combo.barcodes:
        p = get_product_by_barcode(barcode)
        if p:
            p["is_api"] = True
            products.append(p)

    return render_template(
        "student/combo_detail.html",
        combo=combo,
        products=products,
    )


# ==========================================================
# SHOPPING LIST (session)
# ==========================================================

@student.route("/list/add/<barcode>", methods=["POST"])
@login_required
def add_to_list(barcode):

    if not _require_student():
        return "Access denied", 403

    quantity = request.form.get("quantity", "1").strip()

    try:
        quantity = int(quantity)
    except ValueError:
        quantity = 1

    if quantity < 1:
        quantity = 1

    cat_id = request.form.get("cat_id", "").strip()

    try:
        cat_id = int(cat_id) if cat_id else None
    except ValueError:
        cat_id = None

    product = get_product_by_barcode(barcode)

    if not product:
        try:
            db_product = db.session.get(Product, int(barcode))
        except (ValueError, TypeError):
            db_product = None

        if db_product:
            product = {
                "id": db_product.id,
                "name": db_product.name,
                "price": db_product.price,
                "shop_name": db_product.shop_name,
                "image": db_product.image,
                "category": db_product.category,
            }

    if not product:
        flash("Product not found.", "error")

        referrer = request.referrer
        if referrer and request.host_url in referrer:
            return redirect(referrer)
        return redirect(url_for("student.products"))

    # ------------------------------------------
    # CATEGORY BUDGET CHECK
    # ------------------------------------------

    if cat_id is not None:

        budget = get_current_budget()

        cat = BudgetCategory.query.filter_by(
            id=cat_id,
            budget_id=budget.id
        ).first()

        if cat:

            current_total = shopping_list.total_for_category(cat_id)
            new_total = current_total + (float(product["price"]) * quantity)
            limit = float(cat.estimated or 0)

            if limit > 0 and new_total > limit + 0.001:

                over_by = new_total - limit

                flash(
                    f"❌ Adding {quantity} × {product['name']} would take "
                    f"{cat.label} over its estimate by R {over_by:.2f}. "
                    f"Current: R {current_total:.2f} / R {limit:.2f}.",
                    "error"
                )

                referrer = request.referrer
                if referrer and request.host_url in referrer:
                    return redirect(referrer.split("#")[0] + "#shopping-list")
                return redirect(url_for("student.budget_compare", cat_id=cat_id))

    # ------------------------------------------
    # ADD
    # ------------------------------------------

    shopping_list.add_item(product, quantity, cat_id=cat_id)

    flash(
        f"{product['name']} added to your shopping list.",
        "success"
    )

    referrer = request.referrer

    if referrer and request.host_url in referrer:
        return redirect(referrer.split("#")[0] + "#shopping-list")

    return redirect(url_for("student.reservations"))


@student.route("/list/remove/<barcode>", methods=["POST"])
@login_required
def remove_from_list(barcode):

    if not _require_student():
        return "Access denied", 403

    shopping_list.remove_item(barcode)

    flash("Item removed from your list.", "success")

    referrer = request.referrer

    if referrer and request.host_url in referrer:
        return redirect(referrer.split("#")[0] + "#shopping-list")

    return redirect(url_for("student.reservations"))


# ==========================================================
# BUDGET — STEP ROUTER
# ==========================================================

@student.route("/budget")
@login_required
def budget():

    if not _require_student():
        return "Access denied", 403

    b = get_current_budget()

    if b.is_complete:
        return redirect(url_for("student.budget_dashboard"))

    if b.current_step == 1:
        return redirect(url_for("student.budget_step1"))
    if b.current_step == 2:
        return redirect(url_for("student.budget_step2"))
    if b.current_step == 3:
        return redirect(url_for("student.budget_step3"))

    return redirect(url_for("student.budget_step1"))


# ==========================================================
# STEP 1 — SET MONTHLY BUDGET
# ==========================================================

@student.route("/budget/step-1", methods=["GET", "POST"])
@login_required
def budget_step1():

    if not _require_student():
        return "Access denied", 403

    b = get_current_budget()

    if request.method == "POST":

        raw = request.form.get("monthly_limit", "").strip()

        try:
            amount = float(raw)
        except ValueError:
            flash("Please enter a valid amount.", "error")
            return redirect(url_for("student.budget_step1"))

        if amount <= 0:
            flash("Budget must be greater than 0.", "error")
            return redirect(url_for("student.budget_step1"))

        b.monthly_limit = amount
        b.current_step = 2
        b.is_complete = False
        db.session.commit()

        return redirect(url_for("student.budget_step2"))

    return render_template(
        "student/budget_step1.html",
        budget=b,
    )


# ==========================================================
# STEP 2 — PICK CATEGORIES
# ==========================================================

@student.route("/budget/step-2", methods=["GET", "POST"])
@login_required
def budget_step2():

    if not _require_student():
        return "Access denied", 403

    b = get_current_budget()

    if b.monthly_limit <= 0:
        return redirect(url_for("student.budget_step1"))

    if request.method == "POST":

        selected = request.form.getlist("categories")

        if not selected:
            flash("Please select at least one category.", "error")
            return redirect(url_for("student.budget_step2"))

        BudgetCategory.query.filter_by(budget_id=b.id).delete()

        for key in selected:
            cdef = get_category_def(key)
            if not cdef:
                continue

            cat = BudgetCategory(
                budget_id=b.id,
                key=cdef["key"],
                label=cdef["label"],
                estimated=0,
            )
            db.session.add(cat)

        b.current_step = 3
        db.session.commit()

        return redirect(url_for("student.budget_step3"))

    chosen = {c.key for c in b.categories}

    return render_template(
        "student/budget_step2.html",
        budget=b,
        categories=CATEGORY_DEFS,
        chosen=chosen,
    )


# ==========================================================
# STEP 3 — ESTIMATE EACH CATEGORY
# ==========================================================

@student.route("/budget/step-3", methods=["GET", "POST"])
@login_required
def budget_step3():

    if not _require_student():
        return "Access denied", 403

    b = get_current_budget()

    if b.monthly_limit <= 0:
        return redirect(url_for("student.budget_step1"))

    cats = BudgetCategory.query.filter_by(budget_id=b.id).all()

    if not cats:
        return redirect(url_for("student.budget_step2"))

    if request.method == "POST":

        total = 0.0

        for cat in cats:
            raw = request.form.get(f"amount_{cat.id}", "0").strip()

            try:
                value = float(raw)
            except ValueError:
                value = 0.0

            if value < 0:
                value = 0.0

            cat.estimated = value
            total += value

        if total > b.monthly_limit:
            flash(
                f"Total R {total:.2f} exceeds your budget of "
                f"R {b.monthly_limit:.2f}. Please adjust.",
                "error"
            )
            db.session.rollback()
            return redirect(url_for("student.budget_step3"))

        b.current_step = 4
        b.is_complete = True
        db.session.commit()

        flash("Your budget plan is ready!", "success")
        return redirect(url_for("student.budget_dashboard"))

    return render_template(
        "student/budget_step3.html",
        budget=b,
        categories=cats,
    )


# ==========================================================
# BUDGET DASHBOARD — FINAL SCREEN
# ==========================================================

@student.route("/budget/dashboard")
@login_required
def budget_dashboard():

    if not _require_student():
        return "Access denied", 403

    b = get_current_budget()

    if not b.is_complete:
        return redirect(url_for("student.budget"))

    cats = BudgetCategory.query.filter_by(budget_id=b.id).all()

    planned_total = sum((c.estimated or 0) for c in cats)
    remaining = (b.monthly_limit or 0) - planned_total

    percentage_used = 0.0
    if b.monthly_limit and b.monthly_limit > 0:
        percentage_used = (planned_total / b.monthly_limit) * 100.0

    bar_width = min(max(percentage_used, 0.0), 100.0)

    return render_template(
        "student/budget_dashboard.html",
        budget=b,
        categories=cats,
        planned_total=planned_total,
        remaining=remaining,
        percentage_used=percentage_used,
        bar_width=bar_width,
    )


# ==========================================================
# ADJUST CATEGORY (+/− R50)
# ==========================================================

@student.route("/budget/category/<int:cat_id>/adjust", methods=["POST"])
@login_required
def budget_category_adjust(cat_id):

    if not _require_student():
        return "Access denied", 403

    b = get_current_budget()

    cat = BudgetCategory.query.filter_by(
        id=cat_id,
        budget_id=b.id
    ).first()

    if not cat:
        flash("Category not found.", "error")
        return redirect(url_for("student.budget_dashboard"))

    direction = request.form.get("direction", "add")
    step = 50.0

    if direction == "add":
        new_value = (cat.estimated or 0) + step
    else:
        new_value = max(0.0, (cat.estimated or 0) - step)

    others = sum(
        (c.estimated or 0)
        for c in b.categories
        if c.id != cat.id
    )

    if others + new_value > b.monthly_limit:
        flash("This change would exceed your monthly budget.", "error")
        return redirect(url_for("student.budget_dashboard"))

    cat.estimated = new_value
    db.session.commit()

    return redirect(url_for("student.budget_dashboard"))


@student.route("/budget/category/<int:cat_id>/edit", methods=["POST"])
@login_required
def budget_category_edit(cat_id):

    if not _require_student():
        return "Access denied", 403

    b = get_current_budget()

    cat = BudgetCategory.query.filter_by(
        id=cat_id,
        budget_id=b.id
    ).first()

    if not cat:
        flash("Category not found.", "error")
        return redirect(url_for("student.budget_dashboard"))

    raw = request.form.get("amount", "").strip()

    try:
        value = float(raw)
    except ValueError:
        flash("Enter a valid amount.", "error")
        return redirect(url_for("student.budget_dashboard"))

    if value < 0:
        value = 0.0

    others = sum(
        (c.estimated or 0)
        for c in b.categories
        if c.id != cat.id
    )

    if others + value > b.monthly_limit:
        flash("This change would exceed your monthly budget.", "error")
        return redirect(url_for("student.budget_dashboard"))

    cat.estimated = value
    db.session.commit()

    return redirect(url_for("student.budget_dashboard"))


# ==========================================================
# RESET PLAN
# ==========================================================

@student.route("/budget/reset", methods=["POST"])
@login_required
def budget_reset():

    if not _require_student():
        return "Access denied", 403

    b = get_current_budget()

    BudgetCategory.query.filter_by(budget_id=b.id).delete()
    BudgetItem.query.filter_by(budget_id=b.id).delete()

    b.monthly_limit = 0
    b.current_step = 1
    b.is_complete = False

    db.session.commit()

    flash("Plan reset. You can start a new one.", "success")
    return redirect(url_for("student.budget_step1"))


# ==========================================================
# COMPARE PRICES PAGE (per category)
# ==========================================================

DEFAULT_SEARCHES = {
    "groceries":   "food",
    "cosmetics":   "cosmetics",
    "stationery":  "stationery",
    "electronics": "electronics",
}


@student.route("/budget/compare/<int:cat_id>")
@login_required
def budget_compare(cat_id):

    if not _require_student():
        return "Access denied", 403

    b = get_current_budget()

    cat = BudgetCategory.query.filter_by(
        id=cat_id,
        budget_id=b.id
    ).first()

    if not cat:
        flash("Category not found.", "error")
        return redirect(url_for("student.budget_dashboard"))

    if not cat.has_compare:
        flash(
            "Price comparison is not available for this category.",
            "error"
        )
        return redirect(url_for("student.budget_dashboard"))

    search = request.args.get("search", "").strip()

    if not search:
        search = DEFAULT_SEARCHES.get(cat.key, cat.label)

    results = search_grocery_products(search)
    results = attach_sales(results)

    for r in results:
        r["is_api"] = True

    list_items = list(shopping_list.get_list().values())

    return render_template(
        "student/budget_compare.html",
        budget=b,
        category=cat,
        products=results,
        search=search,
        list_items=list_items,
    )


# ==========================================================
# SALE MANAGEMENT (student-facing)
# ==========================================================

@student.route("/sales", methods=["GET", "POST"])
@login_required
def product_sales():

    if not _require_student():
        return "Access denied", 403

    if request.method == "POST":

        action = request.form.get("action", "create")

        if action == "delete":
            sale_id = request.form.get("sale_id", "").strip()

            sale = Sale.query.get(int(sale_id)) if sale_id.isdigit() else None

            if sale:
                db.session.delete(sale)
                db.session.commit()
                flash("Sale removed.", "success")
            else:
                flash("Sale not found.", "error")

            return redirect(url_for("student.product_sales"))

        barcode = request.form.get("barcode", "").strip()
        ends_on_raw = request.form.get("ends_on", "").strip()
        original_price = request.form.get("original_price", "").strip()
        sale_price = request.form.get("sale_price", "").strip()
        discount_label = request.form.get("discount_label", "").strip()
        label = request.form.get("label", "").strip()

        if not barcode:
            flash("Barcode is required.", "error")
            return redirect(url_for("student.product_sales"))

        try:
            ends_on = datetime.strptime(ends_on_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("Please pick a valid end date.", "error")
            return redirect(url_for("student.product_sales"))

        if ends_on < datetime.utcnow().date():
            flash("End date must be in the future.", "error")
            return redirect(url_for("student.product_sales"))

        try:
            original_price = float(original_price) if original_price else None
        except ValueError:
            original_price = None

        try:
            sale_price = float(sale_price) if sale_price else None
        except ValueError:
            sale_price = None

        if original_price is not None and sale_price is not None:
            if sale_price >= original_price:
                flash("Sale price must be lower than the original price.", "error")
                return redirect(url_for("student.product_sales"))

        if not discount_label and original_price and sale_price:
            pct = round((1 - sale_price / original_price) * 100)
            discount_label = f"{pct}% OFF"

        existing = Sale.query.filter_by(barcode=barcode).first()

        if existing:
            existing.ends_on = ends_on
            existing.original_price = original_price
            existing.sale_price = sale_price
            existing.discount_label = discount_label
            existing.label = label or existing.label
            existing.is_auto = False
        else:
            db.session.add(Sale(
                barcode=barcode,
                label=label or None,
                original_price=original_price,
                sale_price=sale_price,
                discount_label=discount_label or None,
                ends_on=ends_on,
                is_auto=False,
            ))

        db.session.commit()
        flash("Sale saved.", "success")
        return redirect(url_for("student.product_sales"))

    today = datetime.utcnow().date()
    sales = Sale.query.order_by(Sale.ends_on.asc()).all()

    return render_template(
        "student/product_sales.html",
        sales=sales,
        today=today,
    )


# ==========================================================
# MANUAL REGENERATE (for demos)
# ==========================================================

@student.route("/admin/regenerate-sales", methods=["POST"])
@login_required
def regenerate_sales():

    if not _require_student():
        return "Access denied", 403

    auto_generate_sales(force=True)
    flash("Sales and combos regenerated.", "success")
    return redirect(url_for("student.dashboard"))


# ==========================================================
# STUDENT RESERVATIONS
# ==========================================================

@student.route("/reservations")
@login_required
def reservations():

    if not _require_student():
        return "Access denied", 403

    reservations = Reservation.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Reservation.start_date.desc()
    ).all()

    list_items = list(shopping_list.get_list().values())
    list_total = shopping_list.total_price()

    return render_template(
        "student/reservations.html",
        reservations=reservations,
        list_items=list_items,
        list_total=list_total,
    )


# ==========================================================
# RESERVE PRODUCT (local DB only)
# ==========================================================

@student.route("/reserve/<int:product_id>", methods=["GET", "POST"])
@login_required
def reserve_product(product_id):

    if not _require_student():
        return "Access denied", 403

    product = db.session.get(Product, product_id)

    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("student.products"))

    if product.stock_quantity <= 0:
        flash("This product is currently out of stock.", "error")
        return redirect(url_for("student.products"))

    if request.method == "POST":

        start_date_text = request.form.get("start_date", "").strip()
        end_date_text = request.form.get("end_date", "").strip()
        quantity_text = request.form.get("quantity", "1").strip()

        try:
            start_date = datetime.strptime(start_date_text, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_text, "%Y-%m-%d").date()
            quantity = int(quantity_text)
        except ValueError:
            flash("Please enter valid reservation details.", "error")
            return redirect(url_for("student.reserve_product", product_id=product.id))

        today = datetime.now().date()

        if start_date < today:
            flash("The reservation cannot start in the past.", "error")
            return redirect(url_for("student.reserve_product", product_id=product.id))

        if end_date < start_date:
            flash("The end date cannot be before the start date.", "error")
            return redirect(url_for("student.reserve_product", product_id=product.id))

        if (end_date - start_date).days + 1 > 3:
            flash("Maximum reservation is 3 days.", "error")
            return redirect(url_for("student.reserve_product", product_id=product.id))

        if quantity < 1 or quantity > product.stock_quantity:
            flash("Invalid quantity.", "error")
            return redirect(url_for("student.reserve_product", product_id=product.id))

        overlapping = Reservation.query.filter(
            Reservation.product_id == product.id,
            Reservation.status == "active",
            Reservation.start_date <= end_date,
            Reservation.end_date >= start_date
        ).all()

        reserved = sum(r.quantity for r in overlapping)
        available = product.stock_quantity - reserved

        if quantity > available:
            flash(f"Only {available} unit(s) available.", "error")
            return redirect(url_for("student.reserve_product", product_id=product.id))

        new_reservation = Reservation(
            user_id=current_user.id,
            product_id=product.id,
            quantity=quantity,
            start_date=start_date,
            end_date=end_date,
            status="active"
        )

        db.session.add(new_reservation)
        db.session.commit()

        flash(f"{product.name} reserved successfully.", "success")
        return redirect(url_for("student.reservations"))

    today = datetime.now().date()

    return render_template(
        "student/reserve_product.html",
        product=product,
        today=today
    )


@student.route("/reservations/cancel/<int:reservation_id>", methods=["POST"])
@login_required
def cancel_reservation(reservation_id):

    if not _require_student():
        return "Access denied", 403

    reservation = Reservation.query.filter_by(
        id=reservation_id,
        user_id=current_user.id
    ).first()

    if not reservation:
        flash("Reservation not found.", "error")
        return redirect(url_for("student.reservations"))

    if reservation.status != "active":
        flash("Already inactive.", "error")
        return redirect(url_for("student.reservations"))

    reservation.status = "cancelled"
    db.session.commit()

    flash("Reservation cancelled.", "success")
    return redirect(url_for("student.reservations"))


# ==========================================================
# AI ASSISTANT — CHEAPEST BASKET ADVISOR
# ==========================================================

@student.route("/ai-assistant")
@login_required
def ai_assistant():

    if not _require_student():
        return "Access denied", 403

    list_items = list(shopping_list.get_list().values())

    b = get_current_budget()
    cats = BudgetCategory.query.filter_by(budget_id=b.id).all()
    category_lookup = {c.id: c for c in cats}

    analysis = analyse_basket(
        list_items=list_items,
        category_lookup=category_lookup,
    )

    return render_template(
        "student/ai_assistant.html",
        analysis=analysis,
        list_items=list_items,
    )


# ==========================================================
# LOYALTY WALLET
# ==========================================================

WALLET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data"
)
os.makedirs(WALLET_DIR, exist_ok=True)


def _wallet_path():
    return os.path.join(
        WALLET_DIR,
        f"loyalty_cards_{current_user.id}.json"
    )


def _wallet_load():
    path = _wallet_path()

    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _wallet_save(cards):
    with open(_wallet_path(), "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2)


WALLET_PRESETS = [
    {"shop": "Checkers Xtra Savings",    "bg": "#e2231a", "fg": "#ffffff"},
    {"shop": "Woolworths WRewards",      "bg": "#1d1d1b", "fg": "#ffffff"},
    {"shop": "SPAR Rewards",             "bg": "#007a3d", "fg": "#ffffff"},
    {"shop": "Pick n Pay Smart Shopper", "bg": "#0a4ea3", "fg": "#ffffff"},
    {"shop": "Clicks ClubCard",          "bg": "#00a0dd", "fg": "#ffffff"},
    {"shop": "Dis-Chem Benefit",         "bg": "#78be20", "fg": "#10230a"},
]

WALLET_FORMATS = ["CODE128", "EAN13", "EAN8", "UPC", "CODE39", "ITF"]


@student.route("/loyalty-wallet")
@login_required
def loyalty_wallet():

    if not _require_student():
        return "Access denied", 403

    cards = _wallet_load()

    return render_template(
        "student/loyalty_wallet.html",
        cards=cards,
        presets=WALLET_PRESETS,
        formats=WALLET_FORMATS,
    )


@student.route("/loyalty-wallet/add", methods=["POST"])
@login_required
def loyalty_wallet_add():

    if not _require_student():
        return jsonify(error="Access denied"), 403

    d = request.get_json(force=True) or {}

    shop = (d.get("shop") or "").strip()
    number = "".join((d.get("number") or "").split())

    if not shop or not number:
        return jsonify(error="Shop name and card number are required."), 400

    card_format = d.get("format")

    if card_format not in WALLET_FORMATS:
        card_format = "CODE128"

    card = {
        "id": uuid.uuid4().hex[:8],
        "shop": shop[:60],
        "number": number[:40],
        "format": card_format,
        "bg": d.get("bg") or "#333333",
        "fg": d.get("fg") or "#ffffff",
    }

    cards = _wallet_load()
    cards.append(card)
    _wallet_save(cards)

    return jsonify(card), 201


@student.route("/loyalty-wallet/delete/<cid>", methods=["POST"])
@login_required
def loyalty_wallet_delete(cid):

    if not _require_student():
        return jsonify(error="Access denied"), 403

    cards = [c for c in _wallet_load() if c["id"] != cid]
    _wallet_save(cards)

    return jsonify(ok=True), 200


# ==========================================================
# STORE MAP PAGE + API
# ==========================================================
# ==========================================================
# STORE MAP PAGE + API
# ==========================================================

@student.route("/stores")
@login_required
def stores():

    if not _require_student():
        return "Access denied", 403

    return render_template("student/stores.html")


@student.route("/api/stores")
@login_required
def api_stores():

    if not _require_student():
        return jsonify(error="Access denied"), 403

    try:
        lat = float(request.args.get("lat", -29.8587))
        lon = float(request.args.get("lon", 31.0218))
        radius = int(request.args.get("radius", 5000))
    except (TypeError, ValueError):
        return jsonify(error="Invalid coordinates"), 400

    stores = find_stores_near(lat, lon, radius)

    # If nothing at 5 km, try 15 km
    if not stores and radius <= 5000:
        stores = find_stores_near(lat, lon, 15000)

    return jsonify(stores=stores, count=len(stores))