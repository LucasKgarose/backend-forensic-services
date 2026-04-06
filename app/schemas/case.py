from pydantic import BaseModel
from typing import List, Optional


class CreateCaseRequest(BaseModel):
    caseNumber: str
    investigatorId: str
    deviceSerial: str | None = None
    deviceIMEI: str | None = None
    osVersion: str | None = None
    notes: list[str] = []


class DataSourceSummaryResponse(BaseModel):
    type: str  # "NOTIFICATION_LOG" | "DECRYPTED_DATABASE"
    fileName: str
    loadedAt: int
    recordCount: int


class CaseResponse(BaseModel):
    caseNumber: str
    createdAt: int  # Unix epoch ms
    investigatorId: str
    deviceIMEI: str
    osVersion: str
    notes: list[str]
    dataSources: list[DataSourceSummaryResponse]


class CaseSummary(BaseModel):
    caseNumber: str
    createdAt: int  # Unix epoch ms
    investigatorId: str
    deviceIMEI: str
