import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.case import Case
from app.models.encryption_key import EncryptionKey
from app.models.chain_of_custody_entry import ChainOfCustodyEntry
from app.models.evidence_hash import EvidenceHash
import app.models  # noqa: F401 — registers event listeners
from app.errors import APKDowngradeError
from app.services.adb_bridge_service import ADBBridgeService, FilePullResult, ShellResult
from app.services.legal_lock_service import LegalLockService
from app.services.apk_downgrade_service import (
    APKDowngradeService,
    DowngradeResult,
    DowngradeStep,
    DowngradeStatus,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def case(db_session):
    c = Case(
        id=str(uuid4()),
        case_number="CASE-APK-001",
        investigator_id="inv-1",
    )
    db_session.add(c)
    db_session.commit()
    return c


@pytest.fixture
def legal_lock(db_session):
    return LegalLockService(db_session)


def _make_adb_mock(
    shell_side_effect=None,
    pull_side_effect=None,
):
    """Create a mock ADBBridgeService with configurable behavior."""
    adb = MagicMock(spec=ADBBridgeService)

    # Default: shell returns a valid APK path
    if shell_side_effect is None:
        adb.execute_shell.return_value = ShellResult(
            output="package:/data/app/com.whatsapp-abc/base.apk",
            exit_code=0,
        )
    else:
        adb.execute_shell.side_effect = shell_side_effect

    # Default: pull_file writes a dummy file and returns a result
    if pull_side_effect is None:
        def _pull(serial, remote_path, local_path, investigator_id):
            # Write a dummy file so _extract_key can read it
            os.makedirs(os.path.dirname(local_path) if os.path.dirname(local_path) else ".", exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(b"fake-key-data")
            return FilePullResult(
                remote_path=remote_path,
                local_path=local_path,
                evidence_hash="abc123hash",
                success=True,
            )
        adb.pull_file.side_effect = _pull
    else:
        adb.pull_file.side_effect = pull_side_effect

    return adb


class TestExecuteDowngradeSuccess:
    def test_returns_successful_result_with_all_steps(self, db_session, case, legal_lock):
        adb = _make_adb_mock()
        service = APKDowngradeService(db=db_session, adb_bridge=adb, legal_lock=legal_lock)

        result = service.execute_downgrade(
            serial="device-001",
            case_id=case.id,
            investigator_id="inv-1",
            old_apk_path="/tmp/old_whatsapp.apk",
        )

        assert result.success is True
        assert len(result.steps) == 4
        step_names = [s.step_name for s in result.steps]
        assert step_names == ["backup", "install", "extraction", "restore"]
        assert all(s.outcome == "success" for s in result.steps)
        assert result.key_id is not None

    def test_persists_encryption_key_to_db(self, db_session, case, legal_lock):
        adb = _make_adb_mock()
        service = APKDowngradeService(db=db_session, adb_bridge=adb, legal_lock=legal_lock)

        result = service.execute_downgrade(
            serial="device-001",
            case_id=case.id,
            investigator_id="inv-1",
            old_apk_path="/tmp/old_whatsapp.apk",
        )

        key = db_session.query(EncryptionKey).filter_by(case_id=case.id).first()
        assert key is not None
        assert key.id == result.key_id
        assert key.device_serial == "device-001"
        assert key.case_id == case.id

    def test_logs_chain_of_custody_for_each_step(self, db_session, case, legal_lock):
        adb = _make_adb_mock()
        service = APKDowngradeService(db=db_session, adb_bridge=adb, legal_lock=legal_lock)

        service.execute_downgrade(
            serial="device-001",
            case_id=case.id,
            investigator_id="inv-1",
            old_apk_path="/tmp/old_whatsapp.apk",
        )

        entries = db_session.query(ChainOfCustodyEntry).filter_by(case_id=case.id).all()
        action_types = [e.action_type for e in entries]
        # Should have: APK_BACKUP, shell commands, file pulls, APK_INSTALL_OLD, KEY_EXTRACTION, APK_RESTORE
        assert "APK_BACKUP" in action_types
        assert "APK_INSTALL_OLD" in action_types
        assert "KEY_EXTRACTION" in action_types
        assert "APK_RESTORE" in action_types


class TestExecuteDowngradeBackupFailure:
    def test_raises_apk_downgrade_error_on_backup_failure(self, db_session, case, legal_lock):
        adb = _make_adb_mock(
            shell_side_effect=RuntimeError("ADB not responding"),
        )
        service = APKDowngradeService(db=db_session, adb_bridge=adb, legal_lock=legal_lock)

        with pytest.raises(APKDowngradeError) as exc_info:
            service.execute_downgrade(
                serial="device-001",
                case_id=case.id,
                investigator_id="inv-1",
                old_apk_path="/tmp/old.apk",
            )

        assert exc_info.value.failed_step == "backup"
        assert len(exc_info.value.steps_completed) == 1
        assert exc_info.value.steps_completed[0]["outcome"] == "failed"

    def test_no_encryption_key_persisted_on_backup_failure(self, db_session, case, legal_lock):
        adb = _make_adb_mock(
            shell_side_effect=RuntimeError("ADB not responding"),
        )
        service = APKDowngradeService(db=db_session, adb_bridge=adb, legal_lock=legal_lock)

        with pytest.raises(APKDowngradeError):
            service.execute_downgrade(
                serial="device-001",
                case_id=case.id,
                investigator_id="inv-1",
                old_apk_path="/tmp/old.apk",
            )

        keys = db_session.query(EncryptionKey).filter_by(case_id=case.id).all()
        assert len(keys) == 0


class TestExecuteDowngradeInstallFailure:
    def test_raises_and_rolls_back_on_install_failure(self, db_session, case, legal_lock):
        call_count = [0]

        def shell_side_effect(serial, command, investigator_id):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: pm path (backup step)
                return ShellResult(output="package:/data/app/com.whatsapp/base.apk", exit_code=0)
            elif "install -r -d" in command:
                # Second call: install old APK — fail
                raise RuntimeError("Installation failed")
            else:
                # Rollback restore
                return ShellResult(output="Success", exit_code=0)

        adb = _make_adb_mock(shell_side_effect=shell_side_effect)
        service = APKDowngradeService(db=db_session, adb_bridge=adb, legal_lock=legal_lock)

        with pytest.raises(APKDowngradeError) as exc_info:
            service.execute_downgrade(
                serial="device-001",
                case_id=case.id,
                investigator_id="inv-1",
                old_apk_path="/tmp/old.apk",
            )

        assert exc_info.value.failed_step == "install"
        # Should have backup(success), install(failed), rollback(success)
        step_outcomes = [(s["step_name"], s["outcome"]) for s in exc_info.value.steps_completed]
        assert ("backup", "success") in step_outcomes
        assert ("install", "failed") in step_outcomes


class TestExecuteDowngradeExtractionFailure:
    def test_raises_and_rolls_back_on_extraction_failure(self, db_session, case, legal_lock):
        call_count = [0]

        def shell_side_effect(serial, command, investigator_id):
            call_count[0] += 1
            if call_count[0] == 1:
                return ShellResult(output="package:/data/app/com.whatsapp/base.apk", exit_code=0)
            elif "install -r -d" in command:
                return ShellResult(output="Success", exit_code=0)
            elif "install -r " in command:
                # Rollback restore
                return ShellResult(output="Success", exit_code=0)
            return ShellResult(output="", exit_code=0)

        pull_count = [0]

        def pull_side_effect(serial, remote_path, local_path, investigator_id):
            pull_count[0] += 1
            if pull_count[0] == 1:
                # First pull: backup APK — success
                with open(local_path, "wb") as f:
                    f.write(b"apk-data")
                return FilePullResult(remote_path=remote_path, local_path=local_path, evidence_hash="hash1", success=True)
            else:
                # Second pull: key extraction — fail
                raise RuntimeError("Key file not found")

        adb = _make_adb_mock(
            shell_side_effect=shell_side_effect,
            pull_side_effect=pull_side_effect,
        )
        service = APKDowngradeService(db=db_session, adb_bridge=adb, legal_lock=legal_lock)

        with pytest.raises(APKDowngradeError) as exc_info:
            service.execute_downgrade(
                serial="device-001",
                case_id=case.id,
                investigator_id="inv-1",
                old_apk_path="/tmp/old.apk",
            )

        assert exc_info.value.failed_step == "extraction"


class TestGetDowngradeStatus:
    def test_returns_status_with_no_key(self, db_session, case, legal_lock):
        adb = _make_adb_mock()
        service = APKDowngradeService(db=db_session, adb_bridge=adb, legal_lock=legal_lock)

        status = service.get_downgrade_status(case.id)

        assert isinstance(status, DowngradeStatus)
        assert status.case_id == case.id
        assert status.has_key is False
        assert status.steps_completed == []

    def test_returns_status_with_key_after_successful_downgrade(self, db_session, case, legal_lock):
        adb = _make_adb_mock()
        service = APKDowngradeService(db=db_session, adb_bridge=adb, legal_lock=legal_lock)

        service.execute_downgrade(
            serial="device-001",
            case_id=case.id,
            investigator_id="inv-1",
            old_apk_path="/tmp/old.apk",
        )

        status = service.get_downgrade_status(case.id)
        assert status.has_key is True
        assert "APK_BACKUP" in status.steps_completed
        assert "APK_INSTALL_OLD" in status.steps_completed
        assert "KEY_EXTRACTION" in status.steps_completed
        assert "APK_RESTORE" in status.steps_completed
