from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class ContactRecord(Base):
    __tablename__ = "contact_records"
    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    phone_number = Column(String, nullable=False)
    display_name = Column(String, nullable=False)

    # Relationships
    case = relationship("Case", back_populates="contacts")
