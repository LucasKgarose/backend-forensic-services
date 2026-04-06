import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.errors import CaseNotFoundError
from app.models.media_reference import MediaReference
from app.models.recovered_media import RecoveredMedia
from app.services.adb_bridge_service import ADBBridgeService, FilePullResult, ShellResult
from app.services.legal_lock_service import LegalLockService
from app.services.media_recovery_service import (
    MediaRecoveryResult,
    MediaRecoveryService,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def mock_adb_bridge():
    return MagicMock(spec=ADBBridgeService)


@pytest.fixture()
def mock_legal_lock():
    mock = MagicMock(spec=LegalLockService)
    mock.log_custody_entry.return_value = MagicMock()
    return mock


@pytest.fixture()
def service(db_session, mock_adb_bridge, mock_legal_lock):
    return MediaRecoveryService(
        db=db_session,
        adb_bridge=mock_adb_bridge,
        legal_lock=mock_legal_lock,
    )


class TestClassifyMediaType:
    def test_image_extensions(self):
        for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
            assert MediaRecoveryService._classify_media_type(f"photo{ext}") == "image"

    def test_video_extensions(self):
        for ext in [".mp4", ".3gp", ".mkv", ".avi"]:
            assert MediaRecoveryService._classify_media_type(f"video{ext}") == "video"

    def test_audio_extensions(self):
        for ext in [".opus", ".mp3", ".aac", ".ogg"]:
            assert MediaRecoveryService._classify_media_type(f"audio{ext}") == "audio"

    def test_document_extensions(self):
        for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx"]:
            assert MediaRecoveryService._classify_media_type(f"file{ext}") == "document"

    def test_unknown_extension_returns_none(self):
        assert MediaRecoveryService._classify_media_type("file.txt") is None
        assert MediaRecoveryService._classify_media_type("file.zip") is None

    def test_case_insensitive(self):
        assert MediaRecoveryService._classify_media_type("photo.JPG") == "image"
        assert MediaRecoveryService._classify_media_type("video.MP4") == "video"


class TestScanAndRecover:
    def _setup_adb_mocks(self, mock_adb_bridge, file_map, tmp_path):
        """Configure ADB mocks to simulate files on device.

        file_map: dict mapping subdir name -> list of file names
        """
        def fake_shell(serial, command, investigator_id):
            for subdir, files in file_map.items():
                if subdir in command:
                    return ShellResult(output="\n".join(files), exit_code=0)
            raise Exception("Directory not found")

        def fake_pull(serial, remote_path, local_path, investigator_id):
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(b"fake file content for " + remote_path.encode())
            return FilePullResult(
                remote_path=remote_path,
                local_path=local_path,
                evidence_hash="fakehash",
                success=True,
            )

        mock_adb_bridge.execute_shell.side_effect = fake_shell
        mock_adb_bridge.pull_file.side_effect = fake_pull

    def test_recovers_files_from_multiple_subdirs(
        self, service, db_session, mock_adb_bridge, mock_legal_lock, tmp_path
    ):
        file_map = {
            "WhatsApp Images": ["photo1.jpg", "photo2.png"],
            "WhatsApp Video": ["clip.mp4"],
            "WhatsApp Audio": ["voice.opus"],
            "WhatsApp Documents": ["report.pdf"],
        }
        self._setup_adb_mocks(mock_adb_bridge, file_map, tmp_path)

        result = service.scan_and_recover(
            serial="DEV001", case_id="case-001", investigator_id="inv-001"
        )

        assert isinstance(result, MediaRecoveryResult)
        assert result.case_id == "case-001"
        assert result.recovered_count == 5
        assert "5" in result.message

        records = db_session.query(RecoveredMedia).filter_by(case_id="case-001").all()
        assert len(records) == 5

    def test_skips_unrecognized_extensions(
        self, service, db_session, mock_adb_bridge, tmp_path
    ):
        file_map = {
            "WhatsApp Images": ["photo.jpg", "readme.txt", "data.bin"],
        }
        self._setup_adb_mocks(mock_adb_bridge, file_map, tmp_path)

        result = service.scan_and_recover(
            serial="DEV001", case_id="case-002", investigator_id="inv-001"
        )

        assert result.recovered_count == 1
        records = db_session.query(RecoveredMedia).filter_by(case_id="case-002").all()
        assert len(records) == 1
        assert records[0].file_name == "photo.jpg"

    def test_empty_scan_returns_zero(
        self, service, mock_adb_bridge
    ):
        # All shell commands fail (no directories)
        mock_adb_bridge.execute_shell.side_effect = Exception("not found")

        result = service.scan_and_recover(
            serial="DEV001", case_id="case-003", investigator_id="inv-001"
        )

        assert result.recovered_count == 0
        assert "No recoverable media" in result.message

    def test_logs_chain_of_custody_per_file(
        self, service, mock_adb_bridge, mock_legal_lock, tmp_path
    ):
        file_map = {"WhatsApp Images": ["a.jpg", "b.png"]}
        self._setup_adb_mocks(mock_adb_bridge, file_map, tmp_path)

        service.scan_and_recover(
            serial="DEV001", case_id="case-004", investigator_id="inv-001"
        )

        assert mock_legal_lock.log_custody_entry.call_count == 2
        for call in mock_legal_lock.log_custody_entry.call_args_list:
            assert call.kwargs["action_type"] == "MEDIA_RECOVERED"
            assert call.kwargs["case_id"] == "case-004"

    def test_cross_references_media_references(
        self, service, db_session, mock_adb_bridge, tmp_path
    ):
        # Create a MediaReference that matches a file name
        db_session.add(MediaReference(
            id=str(uuid4()),
            case_id="case-005",
            message_id="msg-001",
            media_type="image",
            file_name="photo.jpg",
        ))
        db_session.commit()

        file_map = {"WhatsApp Images": ["photo.jpg", "other.png"]}
        self._setup_adb_mocks(mock_adb_bridge, file_map, tmp_path)

        service.scan_and_recover(
            serial="DEV001", case_id="case-005", investigator_id="inv-001"
        )

        records = db_session.query(RecoveredMedia).filter_by(case_id="case-005").all()
        by_name = {r.file_name: r for r in records}
        assert by_name["photo.jpg"].message_id == "msg-001"
        assert by_name["other.png"].message_id is None

    def test_continues_on_pull_failure(
        self, service, db_session, mock_adb_bridge
    ):
        """If pulling one file fails, other files should still be recovered."""
        pull_count = 0

        def fake_shell(serial, command, investigator_id):
            if "WhatsApp Images" in command:
                return ShellResult(output="a.jpg\nb.jpg", exit_code=0)
            raise Exception("not found")

        def fake_pull(serial, remote_path, local_path, investigator_id):
            nonlocal pull_count
            pull_count += 1
            if pull_count == 1:
                raise Exception("pull failed")
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(b"content")
            return FilePullResult(
                remote_path=remote_path,
                local_path=local_path,
                evidence_hash="h",
                success=True,
            )

        mock_adb_bridge.execute_shell.side_effect = fake_shell
        mock_adb_bridge.pull_file.side_effect = fake_pull

        result = service.scan_and_recover(
            serial="DEV001", case_id="case-006", investigator_id="inv-001"
        )

        # Only the second file should be recovered (first pull failed)
        assert result.recovered_count == 1


class TestGetRecoveredMedia:
    def test_returns_records_for_case(self, service, db_session):
        for i in range(3):
            db_session.add(RecoveredMedia(
                id=str(uuid4()),
                case_id="case-100",
                media_type="image",
                file_name=f"img{i}.jpg",
                device_path=f"/sdcard/WhatsApp/Media/WhatsApp Images/img{i}.jpg",
                local_path=f"recovered_media/case-100/img{i}.jpg",
                evidence_hash="abc123",
            ))
        db_session.commit()

        results = service.get_recovered_media("case-100")
        assert len(results) == 3

    def test_returns_empty_for_unknown_case(self, service):
        results = service.get_recovered_media("nonexistent")
        assert results == []

    def test_does_not_return_other_case_records(self, service, db_session):
        db_session.add(RecoveredMedia(
            id=str(uuid4()),
            case_id="case-A",
            media_type="image",
            file_name="a.jpg",
            device_path="/path/a.jpg",
            local_path="local/a.jpg",
            evidence_hash="h1",
        ))
        db_session.add(RecoveredMedia(
            id=str(uuid4()),
            case_id="case-B",
            media_type="video",
            file_name="b.mp4",
            device_path="/path/b.mp4",
            local_path="local/b.mp4",
            evidence_hash="h2",
        ))
        db_session.commit()

        results = service.get_recovered_media("case-A")
        assert len(results) == 1
        assert results[0].file_name == "a.jpg"


class TestGetMediaFile:
    def test_returns_file_bytes(self, service, db_session, tmp_path):
        file_path = str(tmp_path / "test.jpg")
        content = b"binary image data here"
        with open(file_path, "wb") as f:
            f.write(content)

        media_id = str(uuid4())
        db_session.add(RecoveredMedia(
            id=media_id,
            case_id="case-200",
            media_type="image",
            file_name="test.jpg",
            device_path="/sdcard/WhatsApp/Media/WhatsApp Images/test.jpg",
            local_path=file_path,
            evidence_hash="abc",
        ))
        db_session.commit()

        result = service.get_media_file("case-200", media_id)
        assert result == content

    def test_raises_case_not_found_for_missing_media(self, service):
        with pytest.raises(CaseNotFoundError):
            service.get_media_file("case-999", "nonexistent-id")
