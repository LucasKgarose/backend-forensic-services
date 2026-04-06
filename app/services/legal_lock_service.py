import hashlib
from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import TamperDetectedError
from app.models.evidence_hash import EvidenceHash
from app.models.chain_of_custody_entry import ChainOfCustodyEntry


class LegalLockService:
    def __init__(self, db: Session):
        self.db = db

    def compute_and_store_hash(
        self,
        artifact_id: str,
        artifact_data: bytes,
        case_id: str,
        investigator_id: str,
        action_type: str,
    ) -> EvidenceHash:
        hash_value = hashlib.sha256(artifact_data).hexdigest()
        evidence_hash = EvidenceHash(
            id=str(uuid4()),
            case_id=case_id,
            artifact_id=artifact_id,
            hash_value=hash_value,
        )
        self.db.add(evidence_hash)
        self.db.commit()
        self.db.refresh(evidence_hash)

        self.log_custody_entry(
            case_id=case_id,
            investigator_id=investigator_id,
            action_type=action_type,
            artifact_id=artifact_id,
            evidence_hash=hash_value,
        )
        return evidence_hash

    def verify_artifact(
        self,
        artifact_id: str,
        artifact_data: bytes,
        case_id: str,
        investigator_id: str,
    ) -> dict:
        actual_hash = hashlib.sha256(artifact_data).hexdigest()
        stored = (
            self.db.query(EvidenceHash)
            .filter_by(case_id=case_id, artifact_id=artifact_id)
            .first()
        )

        if stored is None or stored.hash_value != actual_hash:
            expected = stored.hash_value if stored else "N/A"
            # Log the verification attempt before raising
            self.log_custody_entry(
                case_id=case_id,
                investigator_id=investigator_id,
                action_type="VERIFICATION_FAILED",
                artifact_id=artifact_id,
                evidence_hash=actual_hash,
            )
            raise TamperDetectedError(
                artifact_id=artifact_id,
                expected_hash=expected,
                actual_hash=actual_hash,
            )

        # Log successful verification
        self.log_custody_entry(
            case_id=case_id,
            investigator_id=investigator_id,
            action_type="VERIFICATION",
            artifact_id=artifact_id,
            evidence_hash=actual_hash,
        )
        return {
            "verified": True,
            "hash_value": actual_hash,
            "message": f"Artifact {artifact_id} verified successfully",
        }

    def get_chain_of_custody(self, case_id: str) -> list[ChainOfCustodyEntry]:
        return (
            self.db.query(ChainOfCustodyEntry)
            .filter_by(case_id=case_id)
            .order_by(ChainOfCustodyEntry.timestamp)
            .all()
        )

    def log_custody_entry(
        self,
        case_id: str,
        investigator_id: str,
        action_type: str,
        artifact_id: str,
        evidence_hash: str = "",
    ) -> ChainOfCustodyEntry:
        entry = ChainOfCustodyEntry(
            id=str(uuid4()),
            case_id=case_id,
            investigator_id=investigator_id,
            action_type=action_type,
            artifact_id=artifact_id,
            evidence_hash=evidence_hash,
            description=f"{action_type} for {artifact_id}",
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def sign_report(self, report_data: bytes, signing_key_path: str) -> bytes:
        from Crypto.PublicKey import RSA
        from Crypto.Signature import pkcs1_15
        from Crypto.Hash import SHA256

        with open(signing_key_path, "rb") as f:
            private_key = RSA.import_key(f.read())

        digest = SHA256.new(report_data)
        signature = pkcs1_15.new(private_key).sign(digest)
        return signature
