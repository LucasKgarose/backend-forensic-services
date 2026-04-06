from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from uuid import uuid4


class ForensicReport(Base):
    __tablename__ = "forensic_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    file_path = Column(String(1000), nullable=False)
    evidence_hash = Column(String(64), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    investigator_id = Column(String(100), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="reports")
