from sqlalchemy import func

from app.extensions import db
from app.models import Forecast, Inventory


UNDERSTOCK = "UNDERSTOCK"
SUFFICIENT = "SUFFICIENT"
OVERSTOCK = "OVERSTOCK"
INVENTORY_REQUIRED = "INVENTORY_REQUIRED"


def _classify_stock(current_stock, forecasted_demand, overstock_multiplier):
    if forecasted_demand == 0:
        return SUFFICIENT if current_stock == 0 else OVERSTOCK
    if current_stock < forecasted_demand:
        return UNDERSTOCK
    if current_stock <= forecasted_demand * overstock_multiplier:
        return SUFFICIENT
    return OVERSTOCK


def build_stock_intelligence(business_id, forecast_run, overstock_multiplier):
    forecast_totals = db.session.execute(
        db.select(Forecast.family, func.sum(Forecast.predicted_sales))
        .where(
            Forecast.business_id == business_id,
            Forecast.forecast_run_id == forecast_run.id,
        )
        .group_by(Forecast.family)
        .order_by(Forecast.family)
    ).all()

    families = [family for family, _total in forecast_totals]
    inventory_by_family = {
        inventory.family: inventory
        for inventory in db.session.scalars(
            db.select(Inventory).where(
                Inventory.business_id == business_id,
                Inventory.family.in_(families),
            )
        ).all()
    }

    results = []
    for family, total in forecast_totals:
        forecasted_demand = float(total or 0)
        inventory = inventory_by_family.get(family)
        if inventory is None:
            results.append(
                {
                    "family": family,
                    "current_stock": None,
                    "forecasted_demand": forecasted_demand,
                    "stock_difference": None,
                    "coverage_ratio": None,
                    "status": INVENTORY_REQUIRED,
                    "explanation": "Current inventory is required for this category.",
                }
            )
            continue

        current_stock = float(inventory.current_stock)
        results.append(
            {
                "family": family,
                "current_stock": current_stock,
                "forecasted_demand": forecasted_demand,
                "stock_difference": current_stock - forecasted_demand,
                "coverage_ratio": (
                    current_stock / forecasted_demand
                    if forecasted_demand > 0
                    else None
                ),
                "status": _classify_stock(
                    current_stock,
                    forecasted_demand,
                    overstock_multiplier,
                ),
            }
        )

    return {
        "forecast_run_id": forecast_run.id,
        "horizon": forecast_run.horizon_days,
        "overstock_multiplier": float(overstock_multiplier),
        "assumptions": {
            "decision_rule": "Configurable prototype stock classification rule.",
            "compatible_units_required": True,
        },
        "families": results,
    }
