from pydantic import BaseModel
from typing import List, Optional

class DecryptedDbEntryResponse(BaseModel):
    id: str
    sender: str
    content: str
    timestamp: int
    readStatus: bool
    deliveryStatus: Optional[str]
    deleted: bool
    mediaReferenceIds: Optional[List[str]]
    deliveredTimestamp: Optional[int]

class DecryptedDatabaseEnvelope(BaseModel):
    deviceIMEI: str
    exportDate: int
    entries: List[DecryptedDbEntryResponse]
