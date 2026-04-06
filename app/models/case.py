from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from uuid import uuid4


class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_number = Column(String(50), unique=True, nullable=False)
    investigator_id = Column(String(100), nullable=False)
    device_serial = Column(String(100), nullable=True)
    device_imei = Column(String(20), nullable=True)
    os_version = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, default="[]")

    # Relationships
    messages = relationship("MessageRecord", back_populates="case", cascade="all, delete-orphan")
    notifications = relationship("NotificationRecord", back_populates="case", cascade="all, delete-orphan")
    contacts = relationship("ContactRecord", back_populates="case", cascade="all, delete-orphan")
    media_references = relationship("MediaReference", back_populates="case", cascade="all, delete-orphan")
    recovered_media = relationship("RecoveredMedia", back_populates="case", cascade="all, delete-orphan")
    custody_entries = relationship("ChainOfCustodyEntry", back_populates="case", cascade="all, delete-orphan")
    evidence_hashes = relationship("EvidenceHash", back_populates="case", cascade="all, delete-orphan")
    reports = relationship("ForensicReport", back_populates="case", cascade="all, delete-orphan")
    encryption_keys = relationship("EncryptionKey", back_populates="case", cascade="all, delete-orphan")
