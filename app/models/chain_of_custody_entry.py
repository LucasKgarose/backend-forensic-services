from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship, validates
from app.database import Base
from datetime import datetime

class ChainOfCustodyEntry(Base):
    __tablename__ = "chain_of_custody_entries"
    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    investigator_id = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    artifact_id = Column(String, nullable=False)
    description = Column(String, nullable=False)

    # Relationships
    case = relationship("Case", back_populates="custody_entries")

    # Append-only enforcement (handled in event listeners, to be added in app wiring)
