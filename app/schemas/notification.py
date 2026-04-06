from pydantic import BaseModel
from typing import List

class NotificationEntryResponse(BaseModel):
    id: str
    sender: str
    content: str
    timestamp: int
    appPackage: str

class NotificationLogEnvelope(BaseModel):
    deviceIMEI: str
    exportDate: int
    entries: List[NotificationEntryResponse]
