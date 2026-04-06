from pydantic import BaseModel
from typing import List

class MediaReferenceResponse(BaseModel):
    id: str
    mediaType: str
    fileName: str
    messageId: str | None

class RecoveredMediaResponse(BaseModel):
    id: str
    filePath: str
    mediaType: str

class FileResponse(BaseModel):
    fileName: str
    content: bytes
