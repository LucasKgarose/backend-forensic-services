from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class NotificationRecord(Base):
    __tablename__ = "notification_records"
    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    sender = Column(String, nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    app_package = Column(String, nullable=False)

    # Relationships
    case = relationship("Case", back_populates="notifications")
