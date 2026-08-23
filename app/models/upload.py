from datetime import datetime, timezone

from app.extensions import db


class Upload(db.Model):
    __tablename__ = "uploads"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("businesses.id"),
        nullable=False,
        index=True,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    row_count = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    status = db.Column(db.String(30), nullable=False, default="completed")

    business = db.relationship("Business", back_populates="uploads")
    sales_records = db.relationship(
        "SalesRecord",
        back_populates="upload",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "row_count": self.row_count,
            "uploaded_at": self.uploaded_at.isoformat(),
            "status": self.status,
        }
