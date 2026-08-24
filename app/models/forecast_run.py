from datetime import datetime, timezone

from app.extensions import db


class ForecastRun(db.Model):
    __tablename__ = "forecast_runs"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("businesses.id"),
        nullable=False,
        index=True,
    )
    upload_id = db.Column(
        db.Integer,
        db.ForeignKey("uploads.id"),
        nullable=False,
        index=True,
    )
    horizon_days = db.Column(db.Integer, nullable=False)
    forecast_start_date = db.Column(db.Date, nullable=False)
    forecast_end_date = db.Column(db.Date, nullable=False)
    family_count = db.Column(db.Integer, nullable=False)
    future_onpromotion = db.Column(db.Float, nullable=False, default=0)
    excluded_families = db.Column(db.JSON, nullable=False, default=list)
    generated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    business = db.relationship("Business", back_populates="forecast_runs")
    upload = db.relationship("Upload", back_populates="forecast_runs")
    forecasts = db.relationship(
        "Forecast",
        back_populates="forecast_run",
        cascade="all, delete-orphan",
        order_by="Forecast.forecast_date",
    )
