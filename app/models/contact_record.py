from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from uuid import uuid4


class ContactRecord(Base):
    __tablename__ = "contact_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    phone_number = Column(String(30), nullable=False)
    display_name = Column(String(200), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="contacts")
