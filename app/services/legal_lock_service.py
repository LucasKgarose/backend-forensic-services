import hashlib
from app.models.evidence_hash import EvidenceHash
from app.models.chain_of_custody_entry import ChainOfCustodyEntry
from sqlalchemy.orm import Session
from typing import Any
from datetime import datetime

class LegalLockService:
    def __init__(self, db: Session):
        self.db = db

    def compute_and_store_hash(self, artifact_id: str, artifact_data: bytes, case_id: str, investigator_id: str, action_type: str) -> EvidenceHash:
        hash_value = hashlib.sha256(artifact_data).hexdigest()
        evidence_hash = EvidenceHash(
            case_id=case_id,
            artifact_id=artifact_id,
            hash_value=hash_value,
        )
        self.db.add(evidence_hash)
        self.db.commit()
        self.db.refresh(evidence_hash)
        # Log chain of custody
        entry = ChainOfCustodyEntry(
            case_id=case_id,
            investigator_id=investigator_id,
            action_type=action_type,
            artifact_id=artifact_id,
            evidence_hash=hash_value,
            description=f"Hash computed for {artifact_id}",
        )
        self.db.add(entry)
        self.db.commit()
        return evidence_hash

    def verify_artifact(self, artifact_id: str, artifact_data: bytes, case_id: str) -> bool:
        hash_value = hashlib.sha256(artifact_data).hexdigest()
        db_hash = self.db.query(EvidenceHash).filter_by(case_id=case_id, artifact_id=artifact_id).first()
        return db_hash and db_hash.hash_value == hash_value
