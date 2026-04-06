import os
import sqlite3
import tempfile
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import CorruptedDatabaseError, NotificationSourceUnavailableError
from app.models.notification_record import NotificationRecord
from app.services.adb_bridge_service import ADBBridgeService, FileNotFoundOnDeviceError
from app.services.legal_lock_service import LegalLockService


NOTIFICATION_DB_REMOTE_PATH = (
    "/data/data/com.notification.scraper/databases/notifications.db"
)


@dataclass
class NotificationExtractionResult:
    case_id: str
    record_count: int
    evidence_hash: str


class NotificationLogService:
    """Service for extracting and querying WhatsApp notification logs."""

    def __init__(
        self,
        db: Session,
        adb_bridge: ADBBridgeService,
        legal_lock: LegalLockService,
    ):
        self.db = db
        self.adb_bridge = adb_bridge
        self.legal_lock = legal_lock

    def extract_notifications(
        self,
        serial: str,
        case_id: str,
        investigator_id: str,
    ) -> NotificationExtractionResult:
        """Pull notification DB from device, parse, filter WhatsApp, persist."""
        local_path = os.path.join(
            tempfile.gettempdir(),
            f"notifications_{case_id}_{uuid4().hex[:8]}.db",
        )

        # Pull the notification scraper DB from the device
        try:
            self.adb_bridge.pull_file(
                serial=serial,
                remote_path=NOTIFICATION_DB_REMOTE_PATH,
                local_path=local_path,
                investigator_id=investigator_id,
            )
        except FileNotFoundOnDeviceError:
            raise NotificationSourceUnavailableError(
                "Notification scraper database not found on device. "
                "Please ensure a notification logging app is installed.",
                details={"serial": serial, "remote_path": NOTIFICATION_DB_REMOTE_PATH},
            )

        # Read raw file bytes for evidence hashing
        try:
            with open(local_path, "rb") as f:
                raw_data = f.read()
        except OSError as exc:
            raise CorruptedDatabaseError(
                f"Unable to read pulled notification database: {exc}",
            )

        # Parse the SQLite DB
        try:
            records = self._parse_notification_db(local_path)
        except Exception as exc:
            raise CorruptedDatabaseError(
                f"Notification database is corrupted or unreadable: {exc}",
            )
        finally:
            # Clean up temp file
            if os.path.exists(local_path):
                os.remove(local_path)

        # Filter for WhatsApp notifications only
        whatsapp_records = [
            r for r in records if r.get("app_package") == "com.whatsapp"
        ]

        # Compute evidence hash via LegalLockService
        artifact_id = f"notification_db_{case_id}_{serial}"
        evidence_hash_obj = self.legal_lock.compute_and_store_hash(
            artifact_id=artifact_id,
            artifact_data=raw_data,
            case_id=case_id,
            investigator_id=investigator_id,
            action_type="NOTIFICATION_EXTRACTION",
        )

        # Persist NotificationRecords to the database
        for rec in whatsapp_records:
            notification = NotificationRecord(
                id=str(uuid4()),
                case_id=case_id,
                sender=rec["sender"],
                content=rec["content"],
                timestamp=rec["timestamp"],
                app_package=rec["app_package"],
            )
            self.db.add(notification)
        self.db.commit()

        return NotificationExtractionResult(
            case_id=case_id,
            record_count=len(whatsapp_records),
            evidence_hash=evidence_hash_obj.hash_value,
        )

    def get_notifications(self, case_id: str) -> list[NotificationRecord]:
        """Query NotificationRecords for the given case_id."""
        return (
            self.db.query(NotificationRecord)
            .filter_by(case_id=case_id)
            .order_by(NotificationRecord.timestamp)
            .all()
        )

    @staticmethod
    def _parse_notification_db(db_path: str) -> list[dict]:
        """Parse the notification scraper SQLite DB and return raw records."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT sender, content, timestamp, app_package FROM notifications"
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.DatabaseError as exc:
            raise CorruptedDatabaseError(
                f"Failed to query notification database: {exc}",
            )
        finally:
            conn.close()
