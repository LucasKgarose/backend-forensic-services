from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class MessageRecord(Base):
    __tablename__ = "message_records"
    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    sender = Column(String, nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    read_status = Column(Boolean, default=False)
    delivery_status = Column(String)
    deleted = Column(Boolean, default=False)

    # Relationships
    case = relationship("Case", back_populates="message_records")
    media_references = relationship("MediaReference", back_populates="message")
