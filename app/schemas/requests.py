from pydantic import BaseModel


class ConnectRequest(BaseModel):
    investigatorId: str


class DisconnectRequest(BaseModel):
    investigatorId: str


class PullFileRequest(BaseModel):
    remotePath: str
    localPath: str
    investigatorId: str


class ShellCommandRequest(BaseModel):
    command: str
    investigatorId: str


class ExtractNotificationsRequest(BaseModel):
    caseId: str
    investigatorId: str


class APKDowngradeRequest(BaseModel):
    caseId: str
    investigatorId: str
    oldApkPath: str


class DecryptRequest(BaseModel):
    encryptedDbPath: str
    keyId: str
    caseId: str
    investigatorId: str


class VerifyRequest(BaseModel):
    artifactId: str
    caseId: str
    investigatorId: str


class GenerateReportRequest(BaseModel):
    caseId: str
    investigatorId: str


class RecoverMediaRequest(BaseModel):
    caseId: str
    investigatorId: str
