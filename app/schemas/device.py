from pydantic import BaseModel


class DeviceInfoResponse(BaseModel):
    serial: str
    model: str
    state: str  # connected, disconnected


class ConnectionResponse(BaseModel):
    serial: str
    status: str
    message: str


class StatusResponse(BaseModel):
    success: bool
    message: str


class FilePullResponse(BaseModel):
    remotePath: str
    localPath: str
    evidenceHash: str
    success: bool


class ShellResponse(BaseModel):
    output: str
    exitCode: int


class NotificationExtractionResponse(BaseModel):
    caseId: str
    recordCount: int
    evidenceHash: str


class DowngradeResponse(BaseModel):
    success: bool
    steps: list[dict]
    keyId: str | None = None
    message: str


class MediaRecoveryResponse(BaseModel):
    caseId: str
    recoveredCount: int
    message: str


class DecryptionResponse(BaseModel):
    caseId: str
    messageCount: int
    contactCount: int
    mediaReferenceCount: int
    evidenceHash: str


class VerificationResponse(BaseModel):
    artifactId: str
    verified: bool
    hashValue: str
    message: str


class ReportResponse(BaseModel):
    caseId: str
    reportId: str
    evidenceHash: str
