from datetime import datetime, timezone

from app.extensions import db


class Business(db.Model):
    __tablename__ = "businesses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    users = db.relationship(
        "User",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    uploads = db.relationship(
        "Upload",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    sales_records = db.relationship(
        "SalesRecord",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    forecast_runs = db.relationship(
        "ForecastRun",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    forecasts = db.relationship(
        "Forecast",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    inventory = db.relationship(
        "Inventory",
        back_populates="business",
        cascade="all, delete-orphan",
    )
