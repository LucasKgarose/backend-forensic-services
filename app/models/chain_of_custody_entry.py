from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from uuid import uuid4


class ChainOfCustodyEntry(Base):
    __tablename__ = "chain_of_custody_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    investigator_id = Column(String(100), nullable=False)
    action_type = Column(String(50), nullable=False)
    artifact_id = Column(String(200), nullable=False)
    evidence_hash = Column(String(64), default="")
    description = Column(Text, default="")

    # Relationships
    case = relationship("Case", back_populates="custody_entries")
