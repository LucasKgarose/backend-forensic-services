from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class EncryptionKey(Base):
    __tablename__ = "encryption_keys"
    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    key_data = Column(String, nullable=False)

    # Relationships
    case = relationship("Case", back_populates="encryption_keys")
