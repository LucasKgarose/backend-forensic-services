from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class MediaReference(Base):
    __tablename__ = "media_references"
    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    message_id = Column(String, ForeignKey("message_records.id"), nullable=True)
    media_type = Column(String, nullable=False)
    file_name = Column(String, nullable=False)

    # Relationships
    case = relationship("Case", back_populates="media_references")
    message = relationship("MessageRecord", back_populates="media_references")
