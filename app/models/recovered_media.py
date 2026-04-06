from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from uuid import uuid4


class RecoveredMedia(Base):
    __tablename__ = "recovered_media"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    message_id = Column(String(36), ForeignKey("message_records.id"), nullable=True)
    media_type = Column(String(20), nullable=False)  # image, video, audio, document
    file_name = Column(String(500), nullable=False)
    device_path = Column(String(1000), nullable=False)
    local_path = Column(String(1000), nullable=False)
    evidence_hash = Column(String(64), nullable=False)
    recovered_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    case = relationship("Case", back_populates="recovered_media")
