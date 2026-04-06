from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class EvidenceHash(Base):
    __tablename__ = "evidence_hashes"
    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    artifact_id = Column(String, nullable=False)
    hash_value = Column(String, nullable=False)
    algorithm = Column(String, default="SHA-256")

    # Relationships
    case = relationship("Case", back_populates="evidence_hashes")
