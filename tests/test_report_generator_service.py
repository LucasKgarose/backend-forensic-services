import hashlib
import os
import shutil
import pytest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.case import Case
from app.models.message_record import MessageRecord
from app.models.notification_record import NotificationRecord
from app.models.chain_of_custody_entry import ChainOfCustodyEntry
from app.models.evidence_hash import EvidenceHash
from app.models.forensic_report import ForensicReport
import app.models  # noqa: F401 — registers event listeners
from app.errors import CaseNotFoundError, ReportGenerationError
from app.services.legal_lock_service import LegalLockService
from app.services.report_generator_service import ReportGeneratorService, ReportResult


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
        case_number="CASE-TEST-001",
        investigator_id="inv-1",
        device_serial="ABC123",
        device_imei="123456789012345",
        os_version="Android 13",
    )
    db_session.add(c)
    db_session.commit()
    return c


@pytest.fixture
def case_with_data(db_session, case):
    """Case with messages, notifications, custody entries, and evidence hashes."""
    for i in range(3):
        db_session.add(MessageRecord(
            id=str(uuid4()),
            case_id=case.id,
            sender=f"sender-{i}",
            content=f"Message content {i}",
            timestamp=1700000000000 + i * 60000,
            status="READ",
        ))
    for i in range(2):
        db_session.add(NotificationRecord(
            id=str(uuid4()),
            case_id=case.id,
            sender=f"notif-sender-{i}",
            content=f"Notification {i}",
            timestamp=1700000000000 + i * 30000,
            app_package="com.whatsapp",
        ))
    db_session.add(ChainOfCustodyEntry(
        id=str(uuid4()),
        case_id=case.id,
        investigator_id="inv-1",
        action_type="FILE_PULL",
        artifact_id="art-1",
        evidence_hash="a" * 64,
    ))
    db_session.add(EvidenceHash(
        id=str(uuid4()),
        case_id=case.id,
        artifact_id="art-1",
        hash_value="b" * 64,
    ))
    db_session.commit()
    return case


@pytest.fixture
def legal_lock(db_session):
    return LegalLockService(db_session)


@pytest.fixture
def service(db_session, legal_lock):
    return ReportGeneratorService(db_session, legal_lock)


@pytest.fixture(autouse=True)
def cleanup_reports():
    yield
    if os.path.exists("reports"):
        shutil.rmtree("reports")


class TestGenerateReport:
    def test_returns_report_result(self, service, case_with_data):
        result = service.generate_report(case_with_data.id, "inv-1")
        assert isinstance(result, ReportResult)
        assert result.case_id == case_with_data.id
        assert len(result.report_id) == 36
        assert len(result.evidence_hash) == 64

    def test_creates_valid_pdf_file(self, service, case_with_data):
        result = service.generate_report(case_with_data.id, "inv-1")
        pdf_path = os.path.join("reports", case_with_data.id, f"{result.report_id}.pdf")
        assert os.path.exists(pdf_path)
        with open(pdf_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_evidence_hash_matches_pdf_content(self, service, case_with_data):
        result = service.generate_report(case_with_data.id, "inv-1")
        pdf_path = os.path.join("reports", case_with_data.id, f"{result.report_id}.pdf")
        with open(pdf_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        assert result.evidence_hash == actual_hash

    def test_persists_forensic_report_to_db(self, service, case_with_data, db_session):
        result = service.generate_report(case_with_data.id, "inv-1")
        report = db_session.query(ForensicReport).filter_by(id=result.report_id).first()
        assert report is not None
        assert report.case_id == case_with_data.id
        assert report.evidence_hash == result.evidence_hash
        assert report.investigator_id == "inv-1"

    def test_logs_chain_of_custody_entry(self, service, case_with_data, db_session):
        result = service.generate_report(case_with_data.id, "inv-1")
        entries = (
            db_session.query(ChainOfCustodyEntry)
            .filter_by(case_id=case_with_data.id, action_type="REPORT_GENERATION")
            .all()
        )
        assert len(entries) == 1
        assert entries[0].artifact_id == result.report_id
        assert entries[0].evidence_hash == result.evidence_hash

    def test_raises_case_not_found_for_missing_case(self, service):
        with pytest.raises(CaseNotFoundError):
            service.generate_report("nonexistent-id", "inv-1")

    def test_works_with_empty_case(self, service, case):
        """Case with no messages, notifications, etc. should still produce a valid PDF."""
        result = service.generate_report(case.id, "inv-1")
        assert isinstance(result, ReportResult)
        pdf_path = os.path.join("reports", case.id, f"{result.report_id}.pdf")
        with open(pdf_path, "rb") as f:
            assert f.read(5) == b"%PDF-"


class TestGetReport:
    def test_returns_pdf_bytes(self, service, case_with_data):
        result = service.generate_report(case_with_data.id, "inv-1")
        pdf_bytes = service.get_report(case_with_data.id, result.report_id)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_returned_bytes_match_file(self, service, case_with_data):
        result = service.generate_report(case_with_data.id, "inv-1")
        pdf_bytes = service.get_report(case_with_data.id, result.report_id)
        pdf_path = os.path.join("reports", case_with_data.id, f"{result.report_id}.pdf")
        with open(pdf_path, "rb") as f:
            assert f.read() == pdf_bytes

    def test_raises_case_not_found_for_missing_report(self, service, case):
        with pytest.raises(CaseNotFoundError):
            service.get_report(case.id, "nonexistent-report-id")

    def test_raises_case_not_found_for_missing_case(self, service):
        with pytest.raises(CaseNotFoundError):
            service.get_report("nonexistent-case", "nonexistent-report")
