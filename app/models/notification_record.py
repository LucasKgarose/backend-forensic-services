from sqlalchemy import Column, String, Text, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from uuid import uuid4


class NotificationRecord(Base):
    __tablename__ = "notification_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    sender = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)  # Unix epoch ms
    app_package = Column(String(200), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="notifications")
