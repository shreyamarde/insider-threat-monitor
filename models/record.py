"""
Business records: the "normal work" employees do inside the application.
Access to them is what the monitoring system watches.
"""
from extensions import db
from utils.helpers import iso, now

SENSITIVITY_LEVELS = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED")
RECORD_CATEGORIES = ("Report", "Contract", "Customer", "Invoice", "Policy", "Personnel", "Technical", "Other")
SHARED_DEPARTMENT = "General"  # company-wide records


class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.Integer, primary_key=True)
    record_code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(30), nullable=False, default="Other")
    department = db.Column(db.String(60), nullable=False, index=True)
    sensitivity = db.Column(db.Enum(*SENSITIVITY_LEVELS, name="record_sensitivity"), nullable=False, default="INTERNAL")
    content = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    creator = db.relationship("User", foreign_keys=[created_by])
    updater = db.relationship("User", foreign_keys=[updated_by])

    @property
    def is_sensitive(self):
        return self.sensitivity == "CONFIDENTIAL"

    def to_dict(self):
        return {
            "id": self.id,
            "record_code": self.record_code,
            "title": self.title,
            "category": self.category,
            "department": self.department,
            "sensitivity": self.sensitivity,
            "content": self.content,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
