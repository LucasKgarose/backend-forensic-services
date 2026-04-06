from sqlalchemy import Column, String, Text, BigInteger, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from uuid import uuid4


class MessageRecord(Base):
    __tablename__ = "message_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    sender = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)  # Unix epoch ms
    status = Column(String(20), nullable=False)  # READ, DELIVERED, DELETED
    is_deleted = Column(Boolean, default=False)
    read_timestamp = Column(BigInteger, nullable=True)
    delivered_timestamp = Column(BigInteger, nullable=True)

    # Relationships
    case = relationship("Case", back_populates="messages")
    media_references = relationship("MediaReference", back_populates="message")
