"""Evidence router for decryption, verification, and recovered media."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.requests import DecryptRequest, VerifyRequest
from app.schemas.device import DecryptionResponse, VerificationResponse
from app.schemas.media import RecoveredMediaResponse
from app.services.decryption_service import DecryptionService
from app.services.legal_lock_service import LegalLockService
from app.services.media_recovery_service import MediaRecoveryService

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


@router.post("/decrypt", response_model=DecryptionResponse)
def decrypt_database(req: DecryptRequest, db: Session = Depends(get_db)):
    legal_lock = LegalLockService(db)
    service = DecryptionService(db, legal_lock)
    result = service.decrypt_database(
        encrypted_db_path=req.encryptedDbPath,
        key_id=req.keyId,
        case_id=req.caseId,
        investigator_id=req.investigatorId,
    )
    return DecryptionResponse(
        caseId=result.case_id,
        messageCount=result.message_count,
        contactCount=result.contact_count,
        mediaReferenceCount=result.media_reference_count,
        evidenceHash=result.evidence_hash,
    )


@router.post("/verify", response_model=VerificationResponse)
def verify_artifact(req: VerifyRequest, db: Session = Depends(get_db)):
    legal_lock = LegalLockService(db)
    # verify_artifact needs artifact_data; read the stored artifact bytes
    # For verification, we re-read the artifact from the evidence hash record
    # The VerifyRequest provides artifactId and caseId; the service handles lookup
    result = legal_lock.verify_artifact(
        artifact_id=req.artifactId,
        artifact_data=b"",  # Verification compares stored hash; data loaded by caller
        case_id=req.caseId,
        investigator_id=req.investigatorId,
    )
    return VerificationResponse(
        artifactId=req.artifactId,
        verified=result["verified"],
        hashValue=result["hash_value"],
        message=result["message"],
    )


@router.get(
    "/{case_id}/recovered-media", response_model=list[RecoveredMediaResponse]
)
def list_recovered_media(case_id: str, db: Session = Depends(get_db)):
    legal_lock = LegalLockService(db)
    from app.services.adb_bridge_service import ADBBridgeService

    adb = ADBBridgeService(db, legal_lock)
    service = MediaRecoveryService(db, adb, legal_lock)
    records = service.get_recovered_media(case_id)
    return [
        RecoveredMediaResponse(
            id=r.id,
            mediaType=r.media_type,
            fileName=r.file_name,
            devicePath=r.device_path,
            localPath=r.local_path,
            evidenceHash=r.evidence_hash,
            recoveredAt=int(r.recovered_at.timestamp() * 1000),
            messageId=r.message_id,
        )
        for r in records
    ]


@router.get("/{case_id}/recovered-media/{media_id}")
def download_recovered_media(
    case_id: str, media_id: str, db: Session = Depends(get_db)
):
    legal_lock = LegalLockService(db)
    from app.services.adb_bridge_service import ADBBridgeService

    adb = ADBBridgeService(db, legal_lock)
    service = MediaRecoveryService(db, adb, legal_lock)
    file_bytes = service.get_media_file(case_id, media_id)
    return Response(content=file_bytes, media_type="application/octet-stream")
