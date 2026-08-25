from datetime import datetime, timezone

from app.extensions import db


class Inventory(db.Model):
    __tablename__ = "inventory"
    __table_args__ = (
        db.UniqueConstraint(
            "business_id",
            "family",
            name="uq_inventory_business_family",
        ),
        db.CheckConstraint(
            "current_stock >= 0",
            name="ck_inventory_current_stock_nonnegative",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("businesses.id"),
        nullable=False,
        index=True,
    )
    family = db.Column(db.String(150), nullable=False)
    current_stock = db.Column(db.Float, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    business = db.relationship("Business", back_populates="inventory")

    def to_dict(self):
        return {
            "id": self.id,
            "family": self.family,
            "current_stock": self.current_stock,
            "updated_at": self.updated_at.isoformat(),
        }
