"""Devices router for ADB device operations."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.requests import (
    ConnectRequest,
    DisconnectRequest,
    PullFileRequest,
    ShellCommandRequest,
    ExtractNotificationsRequest,
    APKDowngradeRequest,
    RecoverMediaRequest,
)
from app.schemas.device import (
    ConnectionResponse,
    DeviceInfoResponse,
    DowngradeResponse,
    FilePullResponse,
    MediaRecoveryResponse,
    NotificationExtractionResponse,
    ShellResponse,
    StatusResponse,
)
from app.services.adb_bridge_service import ADBBridgeService
from app.services.legal_lock_service import LegalLockService
from app.services.notification_log_service import NotificationLogService
from app.services.apk_downgrade_service import APKDowngradeService
from app.services.media_recovery_service import MediaRecoveryService

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


@router.get("/", response_model=list[DeviceInfoResponse])
def discover_devices(db: Session = Depends(get_db)):
    legal_lock = LegalLockService(db)
    adb = ADBBridgeService(db, legal_lock)
    devices = adb.discover_devices()
    return [
        DeviceInfoResponse(serial=d.serial, model=d.model, state=d.state)
        for d in devices
    ]


@router.post("/{serial}/connect", response_model=ConnectionResponse)
def connect_device(serial: str, req: ConnectRequest, db: Session = Depends(get_db)):
    legal_lock = LegalLockService(db)
    adb = ADBBridgeService(db, legal_lock)
    result = adb.connect(serial, req.investigatorId)
    return ConnectionResponse(
        serial=result.serial, status=result.status, message=result.message
    )


@router.post("/{serial}/disconnect", response_model=StatusResponse)
def disconnect_device(
    serial: str, req: DisconnectRequest, db: Session = Depends(get_db)
):
    legal_lock = LegalLockService(db)
    adb = ADBBridgeService(db, legal_lock)
    success = adb.disconnect(serial, req.investigatorId)
    return StatusResponse(success=success, message=f"Disconnected from device {serial}")


@router.post("/{serial}/pull-file", response_model=FilePullResponse)
def pull_file(serial: str, req: PullFileRequest, db: Session = Depends(get_db)):
    legal_lock = LegalLockService(db)
    adb = ADBBridgeService(db, legal_lock)
    result = adb.pull_file(serial, req.remotePath, req.localPath, req.investigatorId)
    return FilePullResponse(
        remotePath=result.remote_path,
        localPath=result.local_path,
        evidenceHash=result.evidence_hash,
        success=result.success,
    )


@router.post("/{serial}/shell", response_model=ShellResponse)
def execute_shell(serial: str, req: ShellCommandRequest, db: Session = Depends(get_db)):
    legal_lock = LegalLockService(db)
    adb = ADBBridgeService(db, legal_lock)
    result = adb.execute_shell(serial, req.command, req.investigatorId)
    return ShellResponse(output=result.output, exitCode=result.exit_code)


@router.post(
    "/{serial}/extract-notifications", response_model=NotificationExtractionResponse
)
def extract_notifications(
    serial: str, req: ExtractNotificationsRequest, db: Session = Depends(get_db)
):
    legal_lock = LegalLockService(db)
    adb = ADBBridgeService(db, legal_lock)
    notif_service = NotificationLogService(db, adb, legal_lock)
    result = notif_service.extract_notifications(serial, req.caseId, req.investigatorId)
    return NotificationExtractionResponse(
        caseId=result.case_id,
        recordCount=result.record_count,
        evidenceHash=result.evidence_hash,
    )


@router.post("/{serial}/apk-downgrade", response_model=DowngradeResponse)
def apk_downgrade(
    serial: str, req: APKDowngradeRequest, db: Session = Depends(get_db)
):
    legal_lock = LegalLockService(db)
    adb = ADBBridgeService(db, legal_lock)
    downgrade_service = APKDowngradeService(db, adb, legal_lock)
    result = downgrade_service.execute_downgrade(
        serial, req.caseId, req.investigatorId, req.oldApkPath
    )
    return DowngradeResponse(
        success=result.success,
        steps=[
            {"step_name": s.step_name, "outcome": s.outcome, "message": s.message}
            for s in result.steps
        ],
        keyId=result.key_id,
        message=result.message,
    )


@router.post("/{serial}/recover-media", response_model=MediaRecoveryResponse)
def recover_media(
    serial: str, req: RecoverMediaRequest, db: Session = Depends(get_db)
):
    legal_lock = LegalLockService(db)
    adb = ADBBridgeService(db, legal_lock)
    media_service = MediaRecoveryService(db, adb, legal_lock)
    result = media_service.scan_and_recover(serial, req.caseId, req.investigatorId)
    return MediaRecoveryResponse(
        caseId=result.case_id,
        recoveredCount=result.recovered_count,
        message=result.message,
    )
