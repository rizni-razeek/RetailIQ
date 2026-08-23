from app.extensions import db


class SalesRecord(db.Model):
    __tablename__ = "sales_records"

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
    date = db.Column(db.Date, nullable=False, index=True)
    family = db.Column(db.String(150), nullable=False, index=True)
    sales = db.Column(db.Float, nullable=False)
    onpromotion = db.Column(db.Float, nullable=False, default=0)

    business = db.relationship("Business", back_populates="sales_records")
    upload = db.relationship("Upload", back_populates="sales_records")
