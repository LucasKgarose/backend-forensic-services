"""Cases router for forensic case management."""

import json
import time
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import CaseNotFoundError
from app.models.case import Case
from app.models.message_record import MessageRecord
from app.models.notification_record import NotificationRecord
from app.models.contact_record import ContactRecord
from app.models.media_reference import MediaReference
from app.services.legal_lock_service import LegalLockService
from app.schemas.case import (
    CreateCaseRequest,
    CaseResponse,
    CaseSummary,
    DataSourceSummaryResponse,
)
from app.schemas.message import DecryptedDatabaseEnvelope, DecryptedDbEntryResponse
from app.schemas.notification import NotificationLogEnvelope, NotificationEntryResponse
from app.schemas.contact import ContactResponse
from app.schemas.media import MediaReferenceResponse
from app.schemas.chain_of_custody import ChainOfCustodyResponse

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


def _get_case_or_404(case_id: str, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise CaseNotFoundError(f"Case {case_id} not found")
    return case


def _datetime_to_epoch_ms(dt) -> int:
    """Convert a datetime object to Unix epoch milliseconds."""
    return int(dt.timestamp() * 1000)


@router.post("/", response_model=CaseResponse)
def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)):
    case = Case(
        id=str(uuid4()),
        case_number=req.caseNumber,
        investigator_id=req.investigatorId,
        device_serial=req.deviceSerial,
        device_imei=req.deviceIMEI,
        os_version=req.osVersion,
        notes=json.dumps(req.notes),
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return _build_case_response(case, db)


@router.get("/", response_model=list[CaseSummary])
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).all()
    return [
        CaseSummary(
            caseNumber=c.case_number,
            createdAt=_datetime_to_epoch_ms(c.created_at),
            investigatorId=c.investigator_id,
            deviceIMEI=c.device_imei or "",
        )
        for c in cases
    ]


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = _get_case_or_404(case_id, db)
    return _build_case_response(case, db)


@router.get("/{case_id}/messages", response_model=DecryptedDatabaseEnvelope)
def get_messages(case_id: str, db: Session = Depends(get_db)):
    case = _get_case_or_404(case_id, db)
    messages = db.query(MessageRecord).filter(MessageRecord.case_id == case_id).all()
    entries = [
        DecryptedDbEntryResponse(
            id=m.id,
            sender=m.sender,
            content=m.content,
            timestamp=m.timestamp,
            status=m.status,
            isDeleted=m.is_deleted,
            readTimestamp=m.read_timestamp,
            deliveredTimestamp=m.delivered_timestamp,
        )
        for m in messages
    ]
    return DecryptedDatabaseEnvelope(
        deviceIMEI=case.device_imei or "",
        exportDate=int(time.time() * 1000),
        entries=entries,
    )


@router.get("/{case_id}/notifications", response_model=NotificationLogEnvelope)
def get_notifications(case_id: str, db: Session = Depends(get_db)):
    case = _get_case_or_404(case_id, db)
    notifications = (
        db.query(NotificationRecord)
        .filter(NotificationRecord.case_id == case_id)
        .all()
    )
    entries = [
        NotificationEntryResponse(
            id=n.id,
            sender=n.sender,
            content=n.content,
            timestamp=n.timestamp,
            appPackage=n.app_package,
        )
        for n in notifications
    ]
    return NotificationLogEnvelope(
        deviceIMEI=case.device_imei or "",
        exportDate=int(time.time() * 1000),
        entries=entries,
    )


@router.get("/{case_id}/contacts", response_model=list[ContactResponse])
def get_contacts(case_id: str, db: Session = Depends(get_db)):
    _get_case_or_404(case_id, db)
    contacts = db.query(ContactRecord).filter(ContactRecord.case_id == case_id).all()
    return [
        ContactResponse(
            id=c.id,
            phoneNumber=c.phone_number,
            displayName=c.display_name,
        )
        for c in contacts
    ]


@router.get("/{case_id}/media-references", response_model=list[MediaReferenceResponse])
def get_media_references(case_id: str, db: Session = Depends(get_db)):
    _get_case_or_404(case_id, db)
    refs = db.query(MediaReference).filter(MediaReference.case_id == case_id).all()
    return [
        MediaReferenceResponse(
            id=r.id,
            mediaType=r.media_type,
            fileName=r.file_name,
            messageId=r.message_id,
        )
        for r in refs
    ]


@router.get("/{case_id}/chain-of-custody", response_model=list[ChainOfCustodyResponse])
def get_chain_of_custody(case_id: str, db: Session = Depends(get_db)):
    _get_case_or_404(case_id, db)
    service = LegalLockService(db)
    entries = service.get_chain_of_custody(case_id)
    return [
        ChainOfCustodyResponse(
            id=e.id,
            timestamp=_datetime_to_epoch_ms(e.timestamp),
            investigatorId=e.investigator_id,
            actionType=e.action_type,
            artifactId=e.artifact_id,
            evidenceHash=e.evidence_hash,
            description=e.description,
        )
        for e in entries
    ]


def _build_case_response(case: Case, db: Session) -> CaseResponse:
    """Build a CaseResponse from a Case ORM model."""
    msg_count = db.query(MessageRecord).filter(MessageRecord.case_id == case.id).count()
    notif_count = (
        db.query(NotificationRecord)
        .filter(NotificationRecord.case_id == case.id)
        .count()
    )

    data_sources: list[DataSourceSummaryResponse] = []
    if msg_count > 0:
        data_sources.append(
            DataSourceSummaryResponse(
                type="DECRYPTED_DATABASE",
                fileName="msgstore.db",
                loadedAt=_datetime_to_epoch_ms(case.created_at),
                recordCount=msg_count,
            )
        )
    if notif_count > 0:
        data_sources.append(
            DataSourceSummaryResponse(
                type="NOTIFICATION_LOG",
                fileName="notifications.db",
                loadedAt=_datetime_to_epoch_ms(case.created_at),
                recordCount=notif_count,
            )
        )

    notes = json.loads(case.notes) if case.notes else []

    return CaseResponse(
        caseNumber=case.case_number,
        createdAt=_datetime_to_epoch_ms(case.created_at),
        investigatorId=case.investigator_id,
        deviceIMEI=case.device_imei or "",
        osVersion=case.os_version or "",
        notes=notes,
        dataSources=data_sources,
    )
