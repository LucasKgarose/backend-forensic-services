from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from uuid import uuid4


class MediaReference(Base):
    __tablename__ = "media_references"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    message_id = Column(String(36), ForeignKey("message_records.id"), nullable=True)
    media_type = Column(String(20), nullable=False)  # image, video, audio, document
    file_name = Column(String(500), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="media_references")
    message = relationship("MessageRecord", back_populates="media_references")
