from pydantic import BaseModel


class MediaReferenceResponse(BaseModel):
    id: str
    mediaType: str
    fileName: str
    messageId: str | None


class RecoveredMediaResponse(BaseModel):
    id: str
    mediaType: str
    fileName: str
    devicePath: str
    localPath: str
    evidenceHash: str
    recoveredAt: int  # Unix epoch ms
    messageId: str | None = None
