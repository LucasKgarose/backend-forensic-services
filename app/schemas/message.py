from pydantic import BaseModel
from typing import List


class DecryptedDbEntryResponse(BaseModel):
    id: str
    sender: str
    content: str
    timestamp: int  # Unix epoch ms
    status: str  # "READ" | "DELIVERED" | "DELETED"
    isDeleted: bool
    readTimestamp: int | None
    deliveredTimestamp: int | None


class DecryptedDatabaseEnvelope(BaseModel):
    deviceIMEI: str
    exportDate: int
    entries: List[DecryptedDbEntryResponse]
