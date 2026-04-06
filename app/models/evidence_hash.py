from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from uuid import uuid4


class EvidenceHash(Base):
    __tablename__ = "evidence_hashes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    artifact_id = Column(String(200), nullable=False)
    hash_value = Column(String(64), nullable=False)  # SHA-256
    computed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    case = relationship("Case", back_populates="evidence_hashes")
