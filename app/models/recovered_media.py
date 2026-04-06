from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class RecoveredMedia(Base):
    __tablename__ = "recovered_media"
    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    file_path = Column(String, nullable=False)
    media_type = Column(String, nullable=False)

    # Relationships
    case = relationship("Case", back_populates="recovered_media")
