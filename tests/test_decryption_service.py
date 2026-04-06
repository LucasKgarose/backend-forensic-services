import os
import sqlite3
import tempfile
import pytest
from uuid import uuid4

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.case import Case
from app.models.contact_record import ContactRecord
from app.models.encryption_key import EncryptionKey
from app.models.media_reference import MediaReference
from app.models.message_record import MessageRecord
from app.models.evidence_hash import EvidenceHash
from app.models.chain_of_custody_entry import ChainOfCustodyEntry
import app.models  # noqa: F401 — registers event listeners
from app.errors import CorruptedDatabaseError, DecryptionError, KeyMismatchError
from app.services.decryption_service import DecryptionResult, DecryptionService
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
        case_number="CASE-DEC-001",
        investigator_id="inv-1",
    )
    db_session.add(c)
    db_session.commit()
    return c


@pytest.fixture
def legal_lock(db_session):
    return LegalLockService(db_session)


@pytest.fixture
def service(db_session, legal_lock):
    return DecryptionService(db_session, legal_lock)


def _create_whatsapp_sqlite(path: str, messages=None, contacts=None, media=None):
    """Create a minimal WhatsApp-style SQLite database for testing."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE messages ("
        "sender TEXT, content TEXT, timestamp INTEGER, status TEXT, "
        "is_deleted INTEGER, read_timestamp INTEGER, delivered_timestamp INTEGER)"
    )
    conn.execute(
        "CREATE TABLE contacts (phone_number TEXT, display_name TEXT)"
    )
    conn.execute(
        "CREATE TABLE media (media_type TEXT, file_name TEXT, message_id TEXT)"
    )
    if messages:
        for m in messages:
            conn.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    m["sender"],
                    m["content"],
                    m["timestamp"],
                    m["status"],
                    m.get("is_deleted", 0),
                    m.get("read_timestamp"),
                    m.get("delivered_timestamp"),
                ),
            )
    if contacts:
        for c in contacts:
            conn.execute(
                "INSERT INTO contacts VALUES (?, ?)",
                (c["phone_number"], c["display_name"]),
            )
    if media:
        for med in media:
            conn.execute(
                "INSERT INTO media VALUES (?, ?, ?)",
                (med["media_type"], med["file_name"], med.get("message_id")),
            )
    conn.commit()
    conn.close()


def _encrypt_crypt15(plaintext: bytes, aes_key: bytes) -> bytes:
    """Create a crypt15-formatted encrypted blob for testing."""
    header = b"\x00" * 67
    iv = get_random_bytes(12)
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return header + iv + ciphertext + tag


def _encrypt_crypt14(plaintext: bytes, aes_key: bytes) -> bytes:
    """Create a crypt14-formatted encrypted blob for testing."""
    header = b"\x00" * 67
    iv = get_random_bytes(16)
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return header + iv + ciphertext + tag


def _setup_encrypted_db(
    db_session, case, aes_key, db_format="crypt15", messages=None, contacts=None, media=None
):
    """Create encrypted DB file + key file on disk, return paths and EncryptionKey."""
    # Build the plaintext SQLite DB
    tmp_plain = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_plain.close()
    _create_whatsapp_sqlite(
        tmp_plain.name,
        messages=messages or [{"sender": "Alice", "content": "Hello", "timestamp": 1000, "status": "READ"}],
        contacts=contacts or [{"phone_number": "+1234567890", "display_name": "Alice"}],
        media=media or [],
    )
    with open(tmp_plain.name, "rb") as f:
        plaintext = f.read()
    os.unlink(tmp_plain.name)

    # Encrypt
    if db_format == "crypt15":
        encrypted = _encrypt_crypt15(plaintext, aes_key)
        ext = ".crypt15"
    else:
        encrypted = _encrypt_crypt14(plaintext, aes_key)
        ext = ".crypt14"

    # Write encrypted file
    enc_fd, enc_path = tempfile.mkstemp(suffix=ext)
    with os.fdopen(enc_fd, "wb") as f:
        f.write(encrypted)

    # Write key file (pad to 32+ bytes)
    key_fd, key_path = tempfile.mkstemp(suffix=".key")
    with os.fdopen(key_fd, "wb") as f:
        f.write(aes_key)

    # Create EncryptionKey record
    enc_key = EncryptionKey(
        id=str(uuid4()),
        case_id=case.id,
        key_data_path=key_path,
        device_serial="device-001",
    )
    db_session.add(enc_key)
    db_session.commit()

    return enc_path, key_path, enc_key


class TestDecryptDatabase:
    def test_successful_crypt15_decryption(self, service, case, db_session):
        aes_key = get_random_bytes(32)
        enc_path, key_path, enc_key = _setup_encrypted_db(
            db_session, case, aes_key, "crypt15",
            messages=[
                {"sender": "Alice", "content": "Hello", "timestamp": 1000, "status": "READ"},
                {"sender": "Bob", "content": "Hi", "timestamp": 2000, "status": "DELIVERED"},
            ],
            contacts=[{"phone_number": "+1111111111", "display_name": "Alice"}],
            media=[{"media_type": "image", "file_name": "photo.jpg", "message_id": "0"}],
        )
        try:
            result = service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")

            assert isinstance(result, DecryptionResult)
            assert result.case_id == case.id
            assert result.message_count == 2
            assert result.contact_count == 1
            assert result.media_reference_count == 1
            assert len(result.evidence_hash) == 64
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)

    def test_successful_crypt14_decryption(self, service, case, db_session):
        aes_key = get_random_bytes(32)
        enc_path, key_path, enc_key = _setup_encrypted_db(
            db_session, case, aes_key, "crypt14",
            messages=[{"sender": "Carol", "content": "Test", "timestamp": 3000, "status": "READ"}],
        )
        try:
            result = service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")
            assert result.message_count == 1
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)

    def test_persists_messages_to_db(self, service, case, db_session):
        aes_key = get_random_bytes(32)
        enc_path, key_path, enc_key = _setup_encrypted_db(
            db_session, case, aes_key, "crypt15",
            messages=[{"sender": "Alice", "content": "Persisted", "timestamp": 5000, "status": "READ"}],
        )
        try:
            service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")
            msgs = db_session.query(MessageRecord).filter_by(case_id=case.id).all()
            assert len(msgs) == 1
            assert msgs[0].sender == "Alice"
            assert msgs[0].content == "Persisted"
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)

    def test_persists_contacts_to_db(self, service, case, db_session):
        aes_key = get_random_bytes(32)
        enc_path, key_path, enc_key = _setup_encrypted_db(
            db_session, case, aes_key, "crypt15",
            contacts=[{"phone_number": "+9999999999", "display_name": "Dave"}],
        )
        try:
            service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")
            contacts = db_session.query(ContactRecord).filter_by(case_id=case.id).all()
            assert len(contacts) == 1
            assert contacts[0].display_name == "Dave"
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)

    def test_computes_evidence_hashes(self, service, case, db_session):
        aes_key = get_random_bytes(32)
        enc_path, key_path, enc_key = _setup_encrypted_db(
            db_session, case, aes_key, "crypt15",
        )
        try:
            service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")
            hashes = db_session.query(EvidenceHash).filter_by(case_id=case.id).all()
            # Should have at least 2: encrypted + decrypted
            assert len(hashes) >= 2
            for h in hashes:
                assert len(h.hash_value) == 64
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)

    def test_logs_chain_of_custody(self, service, case, db_session):
        aes_key = get_random_bytes(32)
        enc_path, key_path, enc_key = _setup_encrypted_db(
            db_session, case, aes_key, "crypt15",
        )
        try:
            service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")
            entries = (
                db_session.query(ChainOfCustodyEntry)
                .filter_by(case_id=case.id)
                .all()
            )
            # At least: ENCRYPTED_DB_INGEST, DECRYPTION, DATABASE_DECRYPTION
            assert len(entries) >= 3
            action_types = {e.action_type for e in entries}
            assert "DATABASE_DECRYPTION" in action_types
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)

    def test_key_mismatch_raises_error(self, service, case, db_session):
        correct_key = get_random_bytes(32)
        wrong_key = get_random_bytes(32)
        enc_path, key_path, enc_key = _setup_encrypted_db(
            db_session, case, correct_key, "crypt15",
        )
        # Overwrite key file with wrong key
        with open(key_path, "wb") as f:
            f.write(wrong_key)
        try:
            with pytest.raises(KeyMismatchError):
                service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)

    def test_missing_encrypted_file_raises_error(self, service, case, db_session):
        enc_key = EncryptionKey(
            id=str(uuid4()),
            case_id=case.id,
            key_data_path="/tmp/nonexistent.key",
            device_serial="dev-1",
        )
        db_session.add(enc_key)
        db_session.commit()

        with pytest.raises(DecryptionError, match="not found"):
            service.decrypt_database("/tmp/nonexistent.crypt15", enc_key.id, case.id, "inv-1")

    def test_missing_key_id_raises_error(self, service, case):
        with pytest.raises(DecryptionError, match="not found"):
            service.decrypt_database("/tmp/fake.crypt15", "nonexistent-key-id", case.id, "inv-1")

    def test_empty_encrypted_file_raises_corrupted(self, service, case, db_session):
        # Create empty encrypted file
        enc_fd, enc_path = tempfile.mkstemp(suffix=".crypt15")
        os.close(enc_fd)
        key_fd, key_path = tempfile.mkstemp(suffix=".key")
        with os.fdopen(key_fd, "wb") as f:
            f.write(get_random_bytes(32))
        enc_key = EncryptionKey(
            id=str(uuid4()),
            case_id=case.id,
            key_data_path=key_path,
            device_serial="dev-1",
        )
        db_session.add(enc_key)
        db_session.commit()
        try:
            with pytest.raises(CorruptedDatabaseError, match="empty"):
                service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)

    def test_short_key_raises_key_mismatch(self, service, case, db_session):
        short_key = get_random_bytes(16)  # Too short for AES-256
        # Create a dummy encrypted file with enough bytes
        enc_fd, enc_path = tempfile.mkstemp(suffix=".crypt15")
        with os.fdopen(enc_fd, "wb") as f:
            f.write(get_random_bytes(200))
        key_fd, key_path = tempfile.mkstemp(suffix=".key")
        with os.fdopen(key_fd, "wb") as f:
            f.write(short_key)
        enc_key = EncryptionKey(
            id=str(uuid4()),
            case_id=case.id,
            key_data_path=key_path,
            device_serial="dev-1",
        )
        db_session.add(enc_key)
        db_session.commit()
        try:
            with pytest.raises(KeyMismatchError, match="too short"):
                service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)

    def test_media_references_linked_to_messages(self, service, case, db_session):
        aes_key = get_random_bytes(32)
        enc_path, key_path, enc_key = _setup_encrypted_db(
            db_session, case, aes_key, "crypt15",
            messages=[
                {"sender": "Alice", "content": "Photo", "timestamp": 1000, "status": "READ"},
            ],
            media=[
                {"media_type": "image", "file_name": "img.jpg", "message_id": "0"},
            ],
        )
        try:
            service.decrypt_database(enc_path, enc_key.id, case.id, "inv-1")
            refs = db_session.query(MediaReference).filter_by(case_id=case.id).all()
            assert len(refs) == 1
            assert refs[0].message_id is not None
            # Verify it links to the correct message
            msg = db_session.query(MessageRecord).filter_by(id=refs[0].message_id).first()
            assert msg is not None
            assert msg.sender == "Alice"
        finally:
            os.unlink(enc_path)
            os.unlink(key_path)


class TestGetMessages:
    def test_returns_messages_ordered_by_timestamp(self, service, case, db_session):
        for ts in [3000, 1000, 2000]:
            db_session.add(MessageRecord(
                id=str(uuid4()), case_id=case.id, sender="A",
                content=f"msg-{ts}", timestamp=ts, status="READ",
            ))
        db_session.commit()

        msgs = service.get_messages(case.id)
        assert [m.timestamp for m in msgs] == [1000, 2000, 3000]

    def test_returns_empty_for_unknown_case(self, service):
        assert service.get_messages("nonexistent") == []


class TestGetContacts:
    def test_returns_contacts_for_case(self, service, case, db_session):
        db_session.add(ContactRecord(
            id=str(uuid4()), case_id=case.id,
            phone_number="+111", display_name="Alice",
        ))
        db_session.add(ContactRecord(
            id=str(uuid4()), case_id=case.id,
            phone_number="+222", display_name="Bob",
        ))
        db_session.commit()

        contacts = service.get_contacts(case.id)
        assert len(contacts) == 2

    def test_returns_empty_for_unknown_case(self, service):
        assert service.get_contacts("nonexistent") == []


class TestGetMediaReferences:
    def test_returns_media_refs_for_case(self, service, case, db_session):
        db_session.add(MediaReference(
            id=str(uuid4()), case_id=case.id,
            media_type="image", file_name="photo.jpg",
        ))
        db_session.commit()

        refs = service.get_media_references(case.id)
        assert len(refs) == 1
        assert refs[0].file_name == "photo.jpg"

    def test_returns_empty_for_unknown_case(self, service):
        assert service.get_media_references("nonexistent") == []


class TestDetectFormat:
    def test_crypt15(self):
        assert DecryptionService._detect_format("msgstore.db.crypt15") == "crypt15"

    def test_crypt14(self):
        assert DecryptionService._detect_format("msgstore.db.crypt14") == "crypt14"

    def test_unknown(self):
        assert DecryptionService._detect_format("msgstore.db") == "unknown"

    def test_case_insensitive(self):
        assert DecryptionService._detect_format("DB.CRYPT15") == "crypt15"


class TestParseDecryptedDb:
    def test_parses_all_tables(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        _create_whatsapp_sqlite(
            path,
            messages=[
                {"sender": "A", "content": "Hi", "timestamp": 100, "status": "READ",
                 "is_deleted": 0, "read_timestamp": 200, "delivered_timestamp": 150},
            ],
            contacts=[{"phone_number": "+111", "display_name": "A"}],
            media=[{"media_type": "video", "file_name": "vid.mp4", "message_id": "0"}],
        )
        try:
            msgs, contacts, refs = DecryptionService._parse_decrypted_db(path, "case-1")
            assert len(msgs) == 1
            assert msgs[0].sender == "A"
            assert msgs[0].timestamp == 100
            assert len(contacts) == 1
            assert contacts[0].phone_number == "+111"
            assert len(refs) == 1
            assert refs[0].media_type == "video"
            assert refs[0].message_id == msgs[0].id
        finally:
            os.unlink(path)

    def test_handles_empty_tables(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        _create_whatsapp_sqlite(path)
        try:
            msgs, contacts, refs = DecryptionService._parse_decrypted_db(path, "case-2")
            assert msgs == []
            assert contacts == []
            assert refs == []
        finally:
            os.unlink(path)
