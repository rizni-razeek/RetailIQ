from flask import Blueprint, redirect, render_template, url_for


pages_blueprint = Blueprint("pages", __name__)


@pages_blueprint.get("/")
def index():
    return redirect(url_for("pages.login"))


@pages_blueprint.get("/login")
def login():
    return render_template("auth/login.html")


@pages_blueprint.get("/register")
def register():
    return render_template("auth/register.html")


@pages_blueprint.get("/dashboard")
def dashboard():
    return render_template("app/dashboard.html")
