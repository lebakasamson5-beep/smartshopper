from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user

from models import db
from models.user import User


auth = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


# ==========================================
# REGISTER
# ==========================================

@auth.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "").strip().lower()

        # ------------------------------------------
        # VALIDATE REQUIRED FIELDS
        # ------------------------------------------

        if not name or not email or not password or not confirm_password or not role:

            flash(
                "Please complete all fields.",
                "error"
            )

            return redirect(url_for("auth.register"))


        # ------------------------------------------
        # VALIDATE ROLE
        # ------------------------------------------

        if role not in ["student", "company"]:

            flash(
                "Please select a valid account type.",
                "error"
            )

            return redirect(url_for("auth.register"))


        # ------------------------------------------
        # VALIDATE PASSWORD
        # ------------------------------------------

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "error"
            )

            return redirect(url_for("auth.register"))


        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return redirect(url_for("auth.register"))


        # ------------------------------------------
        # CHECK EXISTING USER
        # ------------------------------------------

        existing_user = User.query.filter_by(
            email=email
        ).first()


        if existing_user:

            flash(
                "An account with this email already exists.",
                "error"
            )

            return redirect(url_for("auth.register"))


        # ------------------------------------------
        # CREATE USER
        # ------------------------------------------

        user = User(
            name=name,
            email=email,
            role=role
        )

        user.set_password(password)


        db.session.add(user)
        db.session.commit()


        flash(
            "Registration successful. You can now login.",
            "success"
        )


        return redirect(
            url_for("auth.login")
        )


    return render_template(
        "auth/register.html"
    )


# ==========================================
# LOGIN
# ==========================================

@auth.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("home"))


    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        # ------------------------------------------
        # FIND USER
        # ------------------------------------------

        user = User.query.filter_by(
            email=email
        ).first()


        # ------------------------------------------
        # CHECK LOGIN
        # ------------------------------------------

        if user and user.check_password(password):

            login_user(user)


            # --------------------------------------
            # STUDENT
            # --------------------------------------

            if user.role == "student":

                return redirect(
                    url_for("student.dashboard")
                )


            # --------------------------------------
            # COMPANY
            # --------------------------------------

            if user.role == "company":

                return redirect(
                    url_for("company.dashboard")
                )


            # --------------------------------------
            # ADMIN
            # --------------------------------------

            if user.role == "admin":

                return redirect(
                    url_for("admin.dashboard")
                )


        flash(
            "Invalid email or password.",
            "error"
        )


    return render_template(
        "auth/login.html"
    )


# ==========================================
# LOGOUT
# ==========================================

@auth.route("/logout")
def logout():

    logout_user()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(
        url_for("home")
    )
