import hashlib
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import CorruptedDatabaseError, DecryptionError, KeyMismatchError
from app.models.contact_record import ContactRecord
from app.models.encryption_key import EncryptionKey
from app.models.media_reference import MediaReference
from app.models.message_record import MessageRecord
from app.services.legal_lock_service import LegalLockService


@dataclass
class DecryptionResult:
    case_id: str
    message_count: int
    contact_count: int
    media_reference_count: int
    evidence_hash: str


class DecryptionService:
    def __init__(self, db: Session, legal_lock: LegalLockService):
        self.db = db
        self.legal_lock = legal_lock

    def decrypt_database(
        self,
        encrypted_db_path: str,
        key_id: str,
        case_id: str,
        investigator_id: str,
    ) -> DecryptionResult:
        # 1. Load the EncryptionKey from DB
        enc_key = self.db.query(EncryptionKey).filter_by(id=key_id).first()
        if enc_key is None:
            raise DecryptionError(
                f"Encryption key {key_id} not found",
                details={"key_id": key_id},
            )

        # 2. Read encrypted DB file
        try:
            with open(encrypted_db_path, "rb") as f:
                encrypted_data = f.read()
        except FileNotFoundError:
            raise DecryptionError(
                f"Encrypted database file not found: {encrypted_db_path}",
                details={"path": encrypted_db_path},
            )
        except OSError as e:
            raise CorruptedDatabaseError(
                f"Cannot read encrypted database: {e}",
                details={"path": encrypted_db_path},
            )

        if len(encrypted_data) == 0:
            raise CorruptedDatabaseError(
                "Encrypted database file is empty",
                details={"path": encrypted_db_path},
            )

        # 3. Read the key file
        try:
            with open(enc_key.key_data_path, "rb") as f:
                key_data = f.read()
        except FileNotFoundError:
            raise DecryptionError(
                f"Key file not found: {enc_key.key_data_path}",
                details={"key_data_path": enc_key.key_data_path},
            )
        except OSError as e:
            raise DecryptionError(
                f"Cannot read key file: {e}",
                details={"key_data_path": enc_key.key_data_path},
            )

        # 4. Detect format from file extension
        db_format = self._detect_format(encrypted_db_path)

        # 5. Compute evidence hash for encrypted file
        self.legal_lock.compute_and_store_hash(
            artifact_id=f"encrypted_db:{os.path.basename(encrypted_db_path)}",
            artifact_data=encrypted_data,
            case_id=case_id,
            investigator_id=investigator_id,
            action_type="ENCRYPTED_DB_INGEST",
        )

        # 6. Decrypt
        try:
            decrypted_data = self._decrypt_file(encrypted_data, key_data, db_format)
        except KeyMismatchError:
            raise
        except CorruptedDatabaseError:
            raise
        except Exception as e:
            raise DecryptionError(
                f"Decryption failed: {e}",
                details={"format": db_format},
            )

        # 7. Compute evidence hash for decrypted file
        decrypted_hash_record = self.legal_lock.compute_and_store_hash(
            artifact_id=f"decrypted_db:{os.path.basename(encrypted_db_path)}",
            artifact_data=decrypted_data,
            case_id=case_id,
            investigator_id=investigator_id,
            action_type="DECRYPTION",
        )

        # 8. Write decrypted SQLite DB to temp file and parse
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(decrypted_data)

            messages, contacts, media_refs = self._parse_decrypted_db(
                tmp_path, case_id
            )
        except sqlite3.DatabaseError as e:
            raise CorruptedDatabaseError(
                f"Decrypted database is not valid SQLite: {e}",
                details={"path": encrypted_db_path},
            )
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        # 9. Persist all records
        for msg in messages:
            self.db.add(msg)
        for contact in contacts:
            self.db.add(contact)
        for ref in media_refs:
            self.db.add(ref)
        self.db.commit()

        # 10. Log chain of custody
        self.legal_lock.log_custody_entry(
            case_id=case_id,
            investigator_id=investigator_id,
            action_type="DATABASE_DECRYPTION",
            artifact_id=f"decrypted_db:{os.path.basename(encrypted_db_path)}",
            evidence_hash=decrypted_hash_record.hash_value,
        )

        return DecryptionResult(
            case_id=case_id,
            message_count=len(messages),
            contact_count=len(contacts),
            media_reference_count=len(media_refs),
            evidence_hash=decrypted_hash_record.hash_value,
        )

    def get_messages(self, case_id: str) -> list[MessageRecord]:
        return (
            self.db.query(MessageRecord)
            .filter_by(case_id=case_id)
            .order_by(MessageRecord.timestamp)
            .all()
        )

    def get_contacts(self, case_id: str) -> list[ContactRecord]:
        return (
            self.db.query(ContactRecord)
            .filter_by(case_id=case_id)
            .all()
        )

    def get_media_references(self, case_id: str) -> list[MediaReference]:
        return (
            self.db.query(MediaReference)
            .filter_by(case_id=case_id)
            .all()
        )

    @staticmethod
    def _detect_format(path: str) -> str:
        lower = path.lower()
        if lower.endswith(".crypt15"):
            return "crypt15"
        elif lower.endswith(".crypt14"):
            return "crypt14"
        else:
            return "unknown"

    @staticmethod
    def _decrypt_file(
        encrypted_data: bytes, key_data: bytes, db_format: str
    ) -> bytes:
        """Decrypt a WhatsApp encrypted database file.

        This method handles the actual cryptographic decryption. The real
        WhatsApp crypt14/crypt15 format is complex (AES-GCM with specific
        header parsing). This implementation provides the structural
        framework and can be swapped for a production-grade decryptor.

        For crypt15: AES-256-GCM with key derived from the key file.
        For crypt14: AES-256-GCM with key derived from the key file.

        The method is static and modular so it can be replaced or mocked
        in tests without affecting the rest of the service.
        """
        from Crypto.Cipher import AES

        if len(key_data) < 32:
            raise KeyMismatchError(
                "Key data is too short for AES-256 decryption",
                details={"key_length": len(key_data)},
            )

        # Extract the 32-byte AES key from key_data.
        # Real WhatsApp keys have headers; we take the last 32 bytes
        # as the actual key material.
        aes_key = key_data[-32:]

        if db_format == "crypt15":
            return DecryptionService._decrypt_crypt15(encrypted_data, aes_key)
        elif db_format == "crypt14":
            return DecryptionService._decrypt_crypt14(encrypted_data, aes_key)
        else:
            raise DecryptionError(
                f"Unsupported database format: {db_format}",
                details={"format": db_format},
            )

    @staticmethod
    def _decrypt_crypt15(encrypted_data: bytes, aes_key: bytes) -> bytes:
        """Decrypt a crypt15 format database using AES-GCM."""
        from Crypto.Cipher import AES

        # crypt15 layout: header (67 bytes) | IV (12 bytes) | ciphertext | tag (16 bytes)
        HEADER_SIZE = 67
        IV_SIZE = 12
        TAG_SIZE = 16

        min_size = HEADER_SIZE + IV_SIZE + TAG_SIZE + 1
        if len(encrypted_data) < min_size:
            raise CorruptedDatabaseError(
                "Encrypted file too small for crypt15 format",
                details={"size": len(encrypted_data), "min_required": min_size},
            )

        iv = encrypted_data[HEADER_SIZE : HEADER_SIZE + IV_SIZE]
        ciphertext = encrypted_data[HEADER_SIZE + IV_SIZE : -TAG_SIZE]
        tag = encrypted_data[-TAG_SIZE:]

        try:
            cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
            decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        except (ValueError, KeyError):
            raise KeyMismatchError(
                "Decryption failed — key does not match the encrypted database",
                details={"format": "crypt15"},
            )

        return decrypted

    @staticmethod
    def _decrypt_crypt14(encrypted_data: bytes, aes_key: bytes) -> bytes:
        """Decrypt a crypt14 format database using AES-GCM."""
        from Crypto.Cipher import AES

        # crypt14 layout: header (67 bytes) | IV (16 bytes) | ciphertext | tag (16 bytes)
        HEADER_SIZE = 67
        IV_SIZE = 16
        TAG_SIZE = 16

        min_size = HEADER_SIZE + IV_SIZE + TAG_SIZE + 1
        if len(encrypted_data) < min_size:
            raise CorruptedDatabaseError(
                "Encrypted file too small for crypt14 format",
                details={"size": len(encrypted_data), "min_required": min_size},
            )

        iv = encrypted_data[HEADER_SIZE : HEADER_SIZE + IV_SIZE]
        ciphertext = encrypted_data[HEADER_SIZE + IV_SIZE : -TAG_SIZE]
        tag = encrypted_data[-TAG_SIZE:]

        try:
            cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
            decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        except (ValueError, KeyError):
            raise KeyMismatchError(
                "Decryption failed — key does not match the encrypted database",
                details={"format": "crypt14"},
            )

        return decrypted

    @staticmethod
    def _parse_decrypted_db(
        db_path: str, case_id: str
    ) -> tuple[list[MessageRecord], list[ContactRecord], list[MediaReference]]:
        """Parse a decrypted WhatsApp SQLite database.

        Expected tables:
        - messages: sender, content, timestamp, status, is_deleted,
                    read_timestamp, delivered_timestamp
        - contacts: phone_number, display_name
        - media: media_type, file_name, message_id
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            messages = DecryptionService._parse_messages(conn, case_id)
            contacts = DecryptionService._parse_contacts(conn, case_id)

            # Build a mapping from original message_id to our new UUID
            # (media table references message_id from the source DB)
            msg_id_map = {}
            for msg in messages:
                # We store the original index-based id if needed;
                # for now media references use the new UUID
                pass

            media_refs = DecryptionService._parse_media(conn, case_id, messages)
            return messages, contacts, media_refs
        finally:
            conn.close()

    @staticmethod
    def _parse_messages(
        conn: sqlite3.Connection, case_id: str
    ) -> list[MessageRecord]:
        cursor = conn.execute(
            "SELECT sender, content, timestamp, status, is_deleted, "
            "read_timestamp, delivered_timestamp FROM messages"
        )
        messages = []
        for row in cursor:
            msg = MessageRecord(
                id=str(uuid4()),
                case_id=case_id,
                sender=row["sender"],
                content=row["content"],
                timestamp=row["timestamp"],
                status=row["status"],
                is_deleted=bool(row["is_deleted"]),
                read_timestamp=row["read_timestamp"],
                delivered_timestamp=row["delivered_timestamp"],
            )
            messages.append(msg)
        return messages

    @staticmethod
    def _parse_contacts(
        conn: sqlite3.Connection, case_id: str
    ) -> list[ContactRecord]:
        cursor = conn.execute(
            "SELECT phone_number, display_name FROM contacts"
        )
        contacts = []
        for row in cursor:
            contact = ContactRecord(
                id=str(uuid4()),
                case_id=case_id,
                phone_number=row["phone_number"],
                display_name=row["display_name"],
            )
            contacts.append(contact)
        return contacts

    @staticmethod
    def _parse_media(
        conn: sqlite3.Connection,
        case_id: str,
        messages: list[MessageRecord],
    ) -> list[MediaReference]:
        cursor = conn.execute(
            "SELECT media_type, file_name, message_id FROM media"
        )
        media_refs = []
        for row in cursor:
            # message_id in the source DB is an index (e.g. "0", "1")
            # Map it to our MessageRecord UUID if possible
            linked_message_id = None
            raw_msg_id = row["message_id"]
            if raw_msg_id is not None:
                try:
                    idx = int(raw_msg_id)
                    if 0 <= idx < len(messages):
                        linked_message_id = messages[idx].id
                except (ValueError, IndexError):
                    pass

            ref = MediaReference(
                id=str(uuid4()),
                case_id=case_id,
                message_id=linked_message_id,
                media_type=row["media_type"],
                file_name=row["file_name"],
            )
            media_refs.append(ref)
        return media_refs
