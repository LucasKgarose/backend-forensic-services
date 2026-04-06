import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.errors import CorruptedDatabaseError, NotificationSourceUnavailableError
from app.models.notification_record import NotificationRecord
from app.services.adb_bridge_service import (
    ADBBridgeService,
    FilePullResult,
    FileNotFoundOnDeviceError,
)
from app.services.legal_lock_service import LegalLockService
from app.services.notification_log_service import (
    NotificationExtractionResult,
    NotificationLogService,
    NOTIFICATION_DB_REMOTE_PATH,
)


@pytest.fixture()
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _create_notification_db(path: str, rows: list[tuple]) -> None:
    """Helper: create a SQLite notification DB with given rows."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE notifications ("
        "  sender TEXT, content TEXT, timestamp INTEGER, app_package TEXT"
        ")"
    )
    conn.executemany(
        "INSERT INTO notifications (sender, content, timestamp, app_package) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def tmp_notification_db(tmp_path):
    """Create a temp notification DB with mixed app packages."""
    db_path = str(tmp_path / "notifications.db")
    rows = [
        ("Alice", "Hello from WhatsApp", 1700000000000, "com.whatsapp"),
        ("Bob", "Instagram DM", 1700000001000, "com.instagram"),
        ("Charlie", "WhatsApp msg 2", 1700000002000, "com.whatsapp"),
        ("Dave", "Twitter notif", 1700000003000, "com.twitter"),
    ]
    _create_notification_db(db_path, rows)
    return db_path


@pytest.fixture()
def mock_adb_bridge():
    return MagicMock(spec=ADBBridgeService)


@pytest.fixture()
def mock_legal_lock():
    mock = MagicMock(spec=LegalLockService)
    # Return a fake EvidenceHash object with a hash_value attribute
    fake_hash = MagicMock()
    fake_hash.hash_value = "abc123fakehash"
    mock.compute_and_store_hash.return_value = fake_hash
    return mock


@pytest.fixture()
def service(db_session, mock_adb_bridge, mock_legal_lock):
    return NotificationLogService(
        db=db_session,
        adb_bridge=mock_adb_bridge,
        legal_lock=mock_legal_lock,
    )


class TestExtractNotifications:
    def test_extracts_whatsapp_only(
        self, service, db_session, mock_adb_bridge, mock_legal_lock, tmp_notification_db
    ):
        """Only WhatsApp notifications should be persisted."""
        # Make pull_file copy our test DB to the temp location
        def fake_pull(serial, remote_path, local_path, investigator_id):
            import shutil
            shutil.copy2(tmp_notification_db, local_path)
            return FilePullResult(
                remote_path=remote_path,
                local_path=local_path,
                evidence_hash="fakehash",
                success=True,
            )

        mock_adb_bridge.pull_file.side_effect = fake_pull

        result = service.extract_notifications(
            serial="ABC123",
            case_id="case-001",
            investigator_id="inv-001",
        )

        assert isinstance(result, NotificationExtractionResult)
        assert result.case_id == "case-001"
        assert result.record_count == 2  # Only WhatsApp records
        assert result.evidence_hash == "abc123fakehash"

        # Verify persisted records
        records = db_session.query(NotificationRecord).filter_by(case_id="case-001").all()
        assert len(records) == 2
        assert all(r.app_package == "com.whatsapp" for r in records)

    def test_raises_notification_source_unavailable_when_db_missing(
        self, service, mock_adb_bridge
    ):
        """Should raise NotificationSourceUnavailableError when DB not found."""
        mock_adb_bridge.pull_file.side_effect = FileNotFoundOnDeviceError(
            "File not found", file_path=NOTIFICATION_DB_REMOTE_PATH
        )

        with pytest.raises(NotificationSourceUnavailableError):
            service.extract_notifications(
                serial="ABC123",
                case_id="case-001",
                investigator_id="inv-001",
            )

    def test_raises_corrupted_database_on_bad_sqlite(
        self, service, mock_adb_bridge, tmp_path
    ):
        """Should raise CorruptedDatabaseError when DB is not valid SQLite."""
        bad_db = str(tmp_path / "bad.db")
        with open(bad_db, "w") as f:
            f.write("this is not a sqlite database")

        def fake_pull(serial, remote_path, local_path, investigator_id):
            import shutil
            shutil.copy2(bad_db, local_path)
            return FilePullResult(
                remote_path=remote_path,
                local_path=local_path,
                evidence_hash="fakehash",
                success=True,
            )

        mock_adb_bridge.pull_file.side_effect = fake_pull

        with pytest.raises(CorruptedDatabaseError):
            service.extract_notifications(
                serial="ABC123",
                case_id="case-001",
                investigator_id="inv-001",
            )

    def test_computes_evidence_hash(
        self, service, mock_adb_bridge, mock_legal_lock, tmp_notification_db
    ):
        """Should call legal_lock.compute_and_store_hash with raw DB bytes."""
        def fake_pull(serial, remote_path, local_path, investigator_id):
            import shutil
            shutil.copy2(tmp_notification_db, local_path)
            return FilePullResult(
                remote_path=remote_path,
                local_path=local_path,
                evidence_hash="fakehash",
                success=True,
            )

        mock_adb_bridge.pull_file.side_effect = fake_pull

        service.extract_notifications(
            serial="DEV001",
            case_id="case-002",
            investigator_id="inv-002",
        )

        mock_legal_lock.compute_and_store_hash.assert_called_once()
        call_kwargs = mock_legal_lock.compute_and_store_hash.call_args
        assert call_kwargs.kwargs["case_id"] == "case-002"
        assert call_kwargs.kwargs["investigator_id"] == "inv-002"
        assert call_kwargs.kwargs["action_type"] == "NOTIFICATION_EXTRACTION"
        assert isinstance(call_kwargs.kwargs["artifact_data"], bytes)
        assert len(call_kwargs.kwargs["artifact_data"]) > 0

    def test_empty_whatsapp_records(
        self, service, db_session, mock_adb_bridge, tmp_path
    ):
        """Should return 0 records when no WhatsApp notifications exist."""
        db_path = str(tmp_path / "empty_wa.db")
        _create_notification_db(db_path, [
            ("Alice", "Instagram msg", 1700000000000, "com.instagram"),
        ])

        def fake_pull(serial, remote_path, local_path, investigator_id):
            import shutil
            shutil.copy2(db_path, local_path)
            return FilePullResult(
                remote_path=remote_path,
                local_path=local_path,
                evidence_hash="fakehash",
                success=True,
            )

        mock_adb_bridge.pull_file.side_effect = fake_pull

        result = service.extract_notifications(
            serial="ABC123",
            case_id="case-003",
            investigator_id="inv-001",
        )

        assert result.record_count == 0
        records = db_session.query(NotificationRecord).filter_by(case_id="case-003").all()
        assert len(records) == 0


class TestGetNotifications:
    def test_returns_records_for_case(self, service, db_session):
        """Should return all notification records for a given case."""
        for i in range(3):
            db_session.add(NotificationRecord(
                id=str(uuid4()),
                case_id="case-100",
                sender=f"Sender{i}",
                content=f"Content {i}",
                timestamp=1700000000000 + i * 1000,
                app_package="com.whatsapp",
            ))
        db_session.commit()

        results = service.get_notifications("case-100")
        assert len(results) == 3
        # Should be ordered by timestamp
        assert results[0].timestamp <= results[1].timestamp <= results[2].timestamp

    def test_returns_empty_for_unknown_case(self, service):
        """Should return empty list for a case with no notifications."""
        results = service.get_notifications("nonexistent-case")
        assert results == []

    def test_does_not_return_other_case_records(self, service, db_session):
        """Should only return records for the requested case."""
        db_session.add(NotificationRecord(
            id=str(uuid4()),
            case_id="case-A",
            sender="Alice",
            content="Hello",
            timestamp=1700000000000,
            app_package="com.whatsapp",
        ))
        db_session.add(NotificationRecord(
            id=str(uuid4()),
            case_id="case-B",
            sender="Bob",
            content="World",
            timestamp=1700000001000,
            app_package="com.whatsapp",
        ))
        db_session.commit()

        results = service.get_notifications("case-A")
        assert len(results) == 1
        assert results[0].sender == "Alice"
