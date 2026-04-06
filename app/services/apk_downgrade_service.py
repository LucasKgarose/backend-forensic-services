import os
import tempfile
from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import APKDowngradeError
from app.models.encryption_key import EncryptionKey
from app.models.chain_of_custody_entry import ChainOfCustodyEntry
from app.services.adb_bridge_service import ADBBridgeService
from app.services.legal_lock_service import LegalLockService


WHATSAPP_PACKAGE = "com.whatsapp"
WHATSAPP_KEY_PATH = "/data/data/com.whatsapp/files/key"


@dataclass
class DowngradeStep:
    step_name: str
    outcome: str  # "success" or "failed"
    message: str = ""


@dataclass
class DowngradeResult:
    success: bool
    steps: list[DowngradeStep] = field(default_factory=list)
    key_id: str | None = None
    message: str = ""


@dataclass
class DowngradeStatus:
    case_id: str
    has_key: bool
    steps_completed: list[str] = field(default_factory=list)


class APKDowngradeService:
    """Service for performing WhatsApp APK downgrade to extract encryption keys."""

    def __init__(
        self,
        db: Session,
        adb_bridge: ADBBridgeService,
        legal_lock: LegalLockService,
    ):
        self.db = db
        self.adb_bridge = adb_bridge
        self.legal_lock = legal_lock

    def execute_downgrade(
        self,
        serial: str,
        case_id: str,
        investigator_id: str,
        old_apk_path: str,
    ) -> DowngradeResult:
        """Execute the full APK downgrade process to extract the encryption key.

        Steps:
        1. Backup current WhatsApp APK
        2. Install old APK version
        3. Extract encryption key
        4. Restore original APK

        On any step failure, rollback (restore from backup if exists) and raise APKDowngradeError.
        """
        steps: list[DowngradeStep] = []
        backup_path: str | None = None

        # --- Step 1: Backup current WhatsApp APK ---
        try:
            backup_path = self._backup_current_apk(serial, case_id, investigator_id)
            steps.append(DowngradeStep(step_name="backup", outcome="success", message=f"Backed up to {backup_path}"))
        except Exception as exc:
            steps.append(DowngradeStep(step_name="backup", outcome="failed", message=str(exc)))
            self._log_step(case_id, investigator_id, "APK_BACKUP_FAILED", serial, "")
            raise APKDowngradeError(
                message=f"APK backup failed: {exc}",
                failed_step="backup",
                steps_completed=[s.__dict__ for s in steps],
            )

        # --- Step 2: Install old APK ---
        try:
            self._install_old_apk(serial, case_id, investigator_id, old_apk_path)
            steps.append(DowngradeStep(step_name="install", outcome="success", message=f"Installed {old_apk_path}"))
        except Exception as exc:
            steps.append(DowngradeStep(step_name="install", outcome="failed", message=str(exc)))
            self._log_step(case_id, investigator_id, "APK_INSTALL_FAILED", serial, "")
            self._rollback(serial, case_id, investigator_id, backup_path, steps)
            raise APKDowngradeError(
                message=f"Old APK installation failed: {exc}",
                failed_step="install",
                steps_completed=[s.__dict__ for s in steps],
            )

        # --- Step 3: Extract encryption key ---
        key_id: str | None = None
        try:
            key_id = self._extract_key(serial, case_id, investigator_id)
            steps.append(DowngradeStep(step_name="extraction", outcome="success", message=f"Key extracted: {key_id}"))
        except Exception as exc:
            steps.append(DowngradeStep(step_name="extraction", outcome="failed", message=str(exc)))
            self._log_step(case_id, investigator_id, "KEY_EXTRACTION_FAILED", serial, "")
            self._rollback(serial, case_id, investigator_id, backup_path, steps)
            raise APKDowngradeError(
                message=f"Encryption key extraction failed: {exc}",
                failed_step="extraction",
                steps_completed=[s.__dict__ for s in steps],
            )

        # --- Step 4: Restore original APK ---
        try:
            self._restore_apk(serial, case_id, investigator_id, backup_path)
            steps.append(DowngradeStep(step_name="restore", outcome="success", message="Original APK restored"))
        except Exception as exc:
            steps.append(DowngradeStep(step_name="restore", outcome="failed", message=str(exc)))
            self._log_step(case_id, investigator_id, "APK_RESTORE_FAILED", serial, "")
            # Key was already extracted, so we report partial success but still raise
            raise APKDowngradeError(
                message=f"APK restoration failed: {exc}",
                failed_step="restore",
                steps_completed=[s.__dict__ for s in steps],
            )

        return DowngradeResult(
            success=True,
            steps=steps,
            key_id=key_id,
            message="APK downgrade completed successfully",
        )

    def get_downgrade_status(self, case_id: str) -> DowngradeStatus:
        """Query the case's encryption keys and downgrade-related custody entries."""
        keys = (
            self.db.query(EncryptionKey)
            .filter_by(case_id=case_id)
            .all()
        )
        has_key = len(keys) > 0

        downgrade_action_types = {
            "APK_BACKUP", "APK_INSTALL_OLD", "KEY_EXTRACTION",
            "APK_RESTORE", "APK_BACKUP_FAILED", "APK_INSTALL_FAILED",
            "KEY_EXTRACTION_FAILED", "APK_RESTORE_FAILED", "APK_ROLLBACK",
        }
        entries = (
            self.db.query(ChainOfCustodyEntry)
            .filter_by(case_id=case_id)
            .order_by(ChainOfCustodyEntry.timestamp)
            .all()
        )
        steps_completed = [
            e.action_type for e in entries if e.action_type in downgrade_action_types
        ]

        return DowngradeStatus(
            case_id=case_id,
            has_key=has_key,
            steps_completed=steps_completed,
        )

    # ---- Private helpers ----

    def _log_step(
        self,
        case_id: str,
        investigator_id: str,
        action_type: str,
        artifact_id: str,
        evidence_hash: str,
    ) -> None:
        """Log a chain of custody entry for a downgrade step."""
        self.legal_lock.log_custody_entry(
            case_id=case_id,
            investigator_id=investigator_id,
            action_type=action_type,
            artifact_id=artifact_id,
            evidence_hash=evidence_hash,
        )

    def _backup_current_apk(
        self, serial: str, case_id: str, investigator_id: str
    ) -> str:
        """Get the current WhatsApp APK path and pull it to a local backup."""
        # Get the APK path on device
        result = self.adb_bridge.execute_shell(
            serial=serial,
            command=f"pm path {WHATSAPP_PACKAGE}",
            investigator_id=investigator_id,
        )
        # Output is like "package:/data/app/com.whatsapp-xxx/base.apk"
        apk_device_path = result.output.strip().replace("package:", "")
        if not apk_device_path:
            raise RuntimeError("Could not determine current WhatsApp APK path")

        # Pull the APK to a temp location
        backup_path = os.path.join(
            tempfile.gettempdir(),
            f"whatsapp_backup_{case_id}_{uuid4().hex[:8]}.apk",
        )
        pull_result = self.adb_bridge.pull_file(
            serial=serial,
            remote_path=apk_device_path,
            local_path=backup_path,
            investigator_id=investigator_id,
        )

        self._log_step(case_id, investigator_id, "APK_BACKUP", serial, pull_result.evidence_hash)
        return backup_path

    def _install_old_apk(
        self, serial: str, case_id: str, investigator_id: str, old_apk_path: str
    ) -> None:
        """Install the old WhatsApp APK with downgrade flag."""
        result = self.adb_bridge.execute_shell(
            serial=serial,
            command=f"pm install -r -d {old_apk_path}",
            investigator_id=investigator_id,
        )
        self._log_step(case_id, investigator_id, "APK_INSTALL_OLD", serial, "")

    def _extract_key(
        self, serial: str, case_id: str, investigator_id: str
    ) -> str:
        """Extract the encryption key from the device and persist it."""
        key_local_path = os.path.join(
            tempfile.gettempdir(),
            f"whatsapp_key_{case_id}_{uuid4().hex[:8]}",
        )
        pull_result = self.adb_bridge.pull_file(
            serial=serial,
            remote_path=WHATSAPP_KEY_PATH,
            local_path=key_local_path,
            investigator_id=investigator_id,
        )

        # Read key data for evidence hashing
        with open(key_local_path, "rb") as f:
            key_data = f.read()

        # Compute and store evidence hash for the key
        key_id = str(uuid4())
        self.legal_lock.compute_and_store_hash(
            artifact_id=f"encryption_key_{key_id}",
            artifact_data=key_data,
            case_id=case_id,
            investigator_id=investigator_id,
            action_type="KEY_EXTRACTION",
        )

        # Persist EncryptionKey record
        encryption_key = EncryptionKey(
            id=key_id,
            case_id=case_id,
            key_data_path=key_local_path,
            device_serial=serial,
        )
        self.db.add(encryption_key)
        self.db.commit()

        return key_id

    def _restore_apk(
        self, serial: str, case_id: str, investigator_id: str, backup_path: str
    ) -> None:
        """Restore the original WhatsApp APK from backup."""
        result = self.adb_bridge.execute_shell(
            serial=serial,
            command=f"pm install -r {backup_path}",
            investigator_id=investigator_id,
        )
        self._log_step(case_id, investigator_id, "APK_RESTORE", serial, "")

    def _rollback(
        self,
        serial: str,
        case_id: str,
        investigator_id: str,
        backup_path: str | None,
        steps: list[DowngradeStep],
    ) -> None:
        """Attempt to restore the original APK from backup during failure recovery."""
        if backup_path is None:
            return
        try:
            self._restore_apk(serial, case_id, investigator_id, backup_path)
            steps.append(DowngradeStep(step_name="rollback", outcome="success", message="Rolled back to original APK"))
            self._log_step(case_id, investigator_id, "APK_ROLLBACK", serial, "")
        except Exception as rollback_exc:
            steps.append(DowngradeStep(step_name="rollback", outcome="failed", message=str(rollback_exc)))
