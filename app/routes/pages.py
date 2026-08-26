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
    return render_template(
        "app/dashboard.html", active_page="dashboard", page_name="Dashboard"
    )


@pages_blueprint.get("/uploads")
def uploads():
    return render_template("app/uploads.html", active_page="uploads", page_name="Uploads")


@pages_blueprint.get("/forecasts")
def forecasts():
    return render_template(
        "app/forecasts.html", active_page="forecasts", page_name="Forecasts"
    )


@pages_blueprint.get("/inventory")
def inventory():
    return render_template(
        "app/inventory.html", active_page="inventory", page_name="Inventory"
    )


@pages_blueprint.get("/stock-intelligence")
def stock_intelligence():
    return render_template(
        "app/stock_intelligence.html",
        active_page="stock-intelligence",
        page_name="Stock Intelligence",
    )


@pages_blueprint.get("/anomalies")
def anomalies():
    return render_template(
        "app/anomalies.html", active_page="anomalies", page_name="Anomalies"
    )
