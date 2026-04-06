from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship, Mapped
from app.database import Base
from datetime import datetime

class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True, index=True)
    case_number = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    investigator_id = Column(String, nullable=False)
    device_serial = Column(String, nullable=False)

    # Relationships
    message_records = relationship("MessageRecord", back_populates="case", cascade="all, delete-orphan")
    notifications = relationship("NotificationRecord", back_populates="case", cascade="all, delete-orphan")
    contacts = relationship("ContactRecord", back_populates="case", cascade="all, delete-orphan")
    media_references = relationship("MediaReference", back_populates="case", cascade="all, delete-orphan")
    recovered_media = relationship("RecoveredMedia", back_populates="case", cascade="all, delete-orphan")
    custody_entries = relationship("ChainOfCustodyEntry", back_populates="case", cascade="all, delete-orphan")
    evidence_hashes = relationship("EvidenceHash", back_populates="case", cascade="all, delete-orphan")
    encryption_keys = relationship("EncryptionKey", back_populates="case", cascade="all, delete-orphan")
    reports = relationship("ForensicReport", back_populates="case", cascade="all, delete-orphan")
