import bcrypt
from flask import flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import auth_bp
from app.auth.forms import LoginForm, RegistrationForm
from app.models import AppSettings, User, db


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        settings = db.session.get(AppSettings, 1)
        expected_code = settings.invite_code if settings else "wc2026"

        if form.invite_code.data.strip() != expected_code:
            flash(_("Invalid invite code."), "danger")
            return render_template("auth/register.html", form=form)

        if User.query.filter_by(email=form.email.data.lower()).first():
            flash(_("An account with this email already exists."), "danger")
            return render_template("auth/register.html", form=form)

        if User.query.filter_by(username=form.username.data).first():
            flash(_("Username already taken."), "danger")
            return render_template("auth/register.html", form=form)

        password_hash = bcrypt.hashpw(
            form.password.data.encode(), bcrypt.gensalt()
        ).decode()

        # First registered user becomes admin
        is_first_user = User.query.count() == 0

        user = User(
            username=form.username.data,
            email=form.email.data.lower(),
            password_hash=password_hash,
            is_admin=is_first_user,
        )
        db.session.add(user)
        db.session.commit()

        flash(_("Account created successfully. Please log in."), "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()

        if user is None or not bcrypt.checkpw(
            form.password.data.encode(), user.password_hash.encode()
        ):
            flash(_("Invalid email or password."), "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("main.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash(_("You have been logged out."), "info")
    return redirect(url_for("main.index"))
