from app.extensions import db


class Forecast(db.Model):
    __tablename__ = "forecasts"
    __table_args__ = (
        db.UniqueConstraint(
            "forecast_run_id",
            "family",
            "forecast_date",
            name="uq_forecast_run_family_date",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("businesses.id"),
        nullable=False,
        index=True,
    )
    forecast_run_id = db.Column(
        db.Integer,
        db.ForeignKey("forecast_runs.id"),
        nullable=False,
        index=True,
    )
    family = db.Column(db.String(150), nullable=False, index=True)
    forecast_date = db.Column(db.Date, nullable=False, index=True)
    predicted_sales = db.Column(db.Float, nullable=False)

    business = db.relationship("Business", back_populates="forecasts")
    forecast_run = db.relationship("ForecastRun", back_populates="forecasts")
