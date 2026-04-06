import hashlib
import os
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import CaseNotFoundError
from app.models.media_reference import MediaReference
from app.models.recovered_media import RecoveredMedia
from app.services.adb_bridge_service import ADBBridgeService
from app.services.legal_lock_service import LegalLockService


WHATSAPP_MEDIA_BASE = "/sdcard/WhatsApp/Media/"
MEDIA_SUBDIRS = [
    "WhatsApp Images",
    "WhatsApp Video",
    "WhatsApp Audio",
    "WhatsApp Documents",
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".3gp", ".mkv", ".avi"}
AUDIO_EXTENSIONS = {".opus", ".mp3", ".aac", ".ogg"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}


@dataclass
class MediaRecoveryResult:
    case_id: str
    recovered_count: int
    message: str


class MediaRecoveryService:
    """Service for recovering deleted media files from WhatsApp media storage."""

    def __init__(
        self,
        db: Session,
        adb_bridge: ADBBridgeService,
        legal_lock: LegalLockService,
    ):
        self.db = db
        self.adb_bridge = adb_bridge
        self.legal_lock = legal_lock

    def scan_and_recover(
        self,
        serial: str,
        case_id: str,
        investigator_id: str,
    ) -> MediaRecoveryResult:
        """Scan WhatsApp media directories on device, pull and persist files."""
        storage_dir = os.path.join("recovered_media", case_id)
        os.makedirs(storage_dir, exist_ok=True)

        recovered_count = 0

        for subdir in MEDIA_SUBDIRS:
            remote_dir = WHATSAPP_MEDIA_BASE + subdir
            try:
                shell_result = self.adb_bridge.execute_shell(
                    serial=serial,
                    command=f"ls {remote_dir}",
                    investigator_id=investigator_id,
                )
            except Exception:
                # Directory may not exist on device; skip it
                continue

            file_names = [
                name.strip()
                for name in shell_result.output.strip().split("\n")
                if name.strip()
            ]

            for file_name in file_names:
                media_type = self._classify_media_type(file_name)
                if media_type is None:
                    continue

                remote_path = f"{remote_dir}/{file_name}"
                local_path = os.path.join(storage_dir, file_name)

                try:
                    self.adb_bridge.pull_file(
                        serial=serial,
                        remote_path=remote_path,
                        local_path=local_path,
                        investigator_id=investigator_id,
                    )
                except Exception:
                    continue

                # Compute evidence hash
                with open(local_path, "rb") as f:
                    file_data = f.read()
                evidence_hash = hashlib.sha256(file_data).hexdigest()

                # Cross-reference with existing MediaReferences by file_name
                media_ref = (
                    self.db.query(MediaReference)
                    .filter_by(case_id=case_id, file_name=file_name)
                    .first()
                )
                message_id = media_ref.message_id if media_ref else None

                # Log chain of custody entry
                self.legal_lock.log_custody_entry(
                    case_id=case_id,
                    investigator_id=investigator_id,
                    action_type="MEDIA_RECOVERED",
                    artifact_id=file_name,
                    evidence_hash=evidence_hash,
                )

                # Persist RecoveredMedia record
                recovered = RecoveredMedia(
                    id=str(uuid4()),
                    case_id=case_id,
                    message_id=message_id,
                    media_type=media_type,
                    file_name=file_name,
                    device_path=remote_path,
                    local_path=local_path,
                    evidence_hash=evidence_hash,
                )
                self.db.add(recovered)
                recovered_count += 1

        self.db.commit()

        message = (
            f"Recovered {recovered_count} media files from device {serial}"
            if recovered_count > 0
            else f"Scan completed on device {serial}. No recoverable media files found."
        )

        return MediaRecoveryResult(
            case_id=case_id,
            recovered_count=recovered_count,
            message=message,
        )

    def get_recovered_media(self, case_id: str) -> list[RecoveredMedia]:
        """Query RecoveredMedia for the given case_id."""
        return (
            self.db.query(RecoveredMedia)
            .filter_by(case_id=case_id)
            .all()
        )

    def get_media_file(self, case_id: str, media_id: str) -> bytes:
        """Load and return the binary content of a recovered media file."""
        record = (
            self.db.query(RecoveredMedia)
            .filter_by(case_id=case_id, id=media_id)
            .first()
        )
        if record is None:
            raise CaseNotFoundError(
                f"Recovered media {media_id} not found for case {case_id}",
                details={"case_id": case_id, "media_id": media_id},
            )
        with open(record.local_path, "rb") as f:
            return f.read()

    @staticmethod
    def _classify_media_type(file_name: str) -> str | None:
        """Classify a file by its extension. Returns None if unrecognized."""
        ext = os.path.splitext(file_name)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            return "image"
        if ext in VIDEO_EXTENSIONS:
            return "video"
        if ext in AUDIO_EXTENSIONS:
            return "audio"
        if ext in DOCUMENT_EXTENSIONS:
            return "document"
        return None
