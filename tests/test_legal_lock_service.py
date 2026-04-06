import hashlib
import os
import tempfile
import pytest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.case import Case
from app.models.evidence_hash import EvidenceHash
from app.models.chain_of_custody_entry import ChainOfCustodyEntry
import app.models  # noqa: F401 — registers event listeners
from app.errors import TamperDetectedError
from app.services.legal_lock_service import LegalLockService


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
        case_number="CASE-001",
        investigator_id="inv-1",
    )
    db_session.add(c)
    db_session.commit()
    return c


@pytest.fixture
def service(db_session):
    return LegalLockService(db_session)


class TestComputeAndStoreHash:
    def test_returns_evidence_hash_with_correct_sha256(self, service, case, db_session):
        data = b"hello world"
        expected_hash = hashlib.sha256(data).hexdigest()

        result = service.compute_and_store_hash(
            artifact_id="art-1",
            artifact_data=data,
            case_id=case.id,
            investigator_id="inv-1",
            action_type="INGEST",
        )

        assert isinstance(result, EvidenceHash)
        assert result.hash_value == expected_hash
        assert result.artifact_id == "art-1"
        assert result.case_id == case.id

    def test_persists_evidence_hash_to_db(self, service, case, db_session):
        service.compute_and_store_hash(
            artifact_id="art-2",
            artifact_data=b"test data",
            case_id=case.id,
            investigator_id="inv-1",
            action_type="INGEST",
        )
        stored = db_session.query(EvidenceHash).filter_by(artifact_id="art-2").first()
        assert stored is not None
        assert stored.hash_value == hashlib.sha256(b"test data").hexdigest()

    def test_logs_chain_of_custody_entry(self, service, case, db_session):
        service.compute_and_store_hash(
            artifact_id="art-3",
            artifact_data=b"data",
            case_id=case.id,
            investigator_id="inv-1",
            action_type="INGEST",
        )
        entries = db_session.query(ChainOfCustodyEntry).filter_by(case_id=case.id).all()
        assert len(entries) == 1
        assert entries[0].action_type == "INGEST"
        assert entries[0].artifact_id == "art-3"
        assert entries[0].investigator_id == "inv-1"

    def test_uses_uuid4_for_id(self, service, case, db_session):
        result = service.compute_and_store_hash(
            artifact_id="art-4",
            artifact_data=b"bytes",
            case_id=case.id,
            investigator_id="inv-1",
            action_type="INGEST",
        )
        # uuid4 produces 36-char strings with dashes
        assert len(result.id) == 36
        assert "-" in result.id


class TestVerifyArtifact:
    def test_verify_matching_data_returns_verified(self, service, case, db_session):
        data = b"original data"
        service.compute_and_store_hash(
            artifact_id="art-v1",
            artifact_data=data,
            case_id=case.id,
            investigator_id="inv-1",
            action_type="INGEST",
        )

        result = service.verify_artifact(
            artifact_id="art-v1",
            artifact_data=data,
            case_id=case.id,
            investigator_id="inv-1",
        )

        assert result["verified"] is True
        assert result["hash_value"] == hashlib.sha256(data).hexdigest()
        assert "message" in result

    def test_verify_tampered_data_raises_error(self, service, case, db_session):
        service.compute_and_store_hash(
            artifact_id="art-v2",
            artifact_data=b"original",
            case_id=case.id,
            investigator_id="inv-1",
            action_type="INGEST",
        )

        with pytest.raises(TamperDetectedError) as exc_info:
            service.verify_artifact(
                artifact_id="art-v2",
                artifact_data=b"tampered",
                case_id=case.id,
                investigator_id="inv-1",
            )

        assert exc_info.value.expected_hash == hashlib.sha256(b"original").hexdigest()
        assert exc_info.value.actual_hash == hashlib.sha256(b"tampered").hexdigest()

    def test_verify_logs_custody_entry(self, service, case, db_session):
        data = b"verify me"
        service.compute_and_store_hash(
            artifact_id="art-v3",
            artifact_data=data,
            case_id=case.id,
            investigator_id="inv-1",
            action_type="INGEST",
        )

        service.verify_artifact(
            artifact_id="art-v3",
            artifact_data=data,
            case_id=case.id,
            investigator_id="inv-1",
        )

        entries = db_session.query(ChainOfCustodyEntry).filter_by(
            case_id=case.id, action_type="VERIFICATION"
        ).all()
        assert len(entries) == 1


class TestGetChainOfCustody:
    def test_returns_entries_ordered_by_timestamp(self, service, case, db_session):
        service.log_custody_entry(case.id, "inv-1", "ACTION_A", "art-a")
        service.log_custody_entry(case.id, "inv-1", "ACTION_B", "art-b")

        entries = service.get_chain_of_custody(case.id)
        assert len(entries) == 2
        assert entries[0].timestamp <= entries[1].timestamp

    def test_returns_empty_for_unknown_case(self, service):
        entries = service.get_chain_of_custody("nonexistent-case")
        assert entries == []


class TestLogCustodyEntry:
    def test_creates_entry_with_all_fields(self, service, case, db_session):
        entry = service.log_custody_entry(
            case_id=case.id,
            investigator_id="inv-1",
            action_type="FILE_PULL",
            artifact_id="art-log",
            evidence_hash="abc123",
        )

        assert entry.case_id == case.id
        assert entry.investigator_id == "inv-1"
        assert entry.action_type == "FILE_PULL"
        assert entry.artifact_id == "art-log"
        assert entry.evidence_hash == "abc123"
        assert entry.timestamp is not None
        assert len(entry.id) == 36

    def test_defaults_evidence_hash_to_empty(self, service, case, db_session):
        entry = service.log_custody_entry(
            case_id=case.id,
            investigator_id="inv-1",
            action_type="ACTION",
            artifact_id="art-x",
        )
        assert entry.evidence_hash == ""


class TestSignReport:
    def test_sign_and_verify_round_trip(self, service):
        from Crypto.PublicKey import RSA
        from Crypto.Signature import pkcs1_15
        from Crypto.Hash import SHA256

        key = RSA.generate(2048)
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
            f.write(key.export_key())
            key_path = f.name

        try:
            report_data = b"This is a forensic report."
            signature = service.sign_report(report_data, key_path)

            # Verify with public key
            digest = SHA256.new(report_data)
            pkcs1_15.new(key.publickey()).verify(digest, signature)
        finally:
            os.unlink(key_path)

    def test_sign_with_different_data_fails_verification(self, service):
        from Crypto.PublicKey import RSA
        from Crypto.Signature import pkcs1_15
        from Crypto.Hash import SHA256

        key = RSA.generate(2048)
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
            f.write(key.export_key())
            key_path = f.name

        try:
            signature = service.sign_report(b"original report", key_path)

            digest = SHA256.new(b"tampered report")
            with pytest.raises(ValueError):
                pkcs1_15.new(key.publickey()).verify(digest, signature)
        finally:
            os.unlink(key_path)
