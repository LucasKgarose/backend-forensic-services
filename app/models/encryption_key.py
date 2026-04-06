from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from uuid import uuid4


class EncryptionKey(Base):
    __tablename__ = "encryption_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    key_data_path = Column(String(1000), nullable=False)  # Path to key file on disk
    extracted_at = Column(DateTime, default=datetime.utcnow)
    device_serial = Column(String(100), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="encryption_keys")
