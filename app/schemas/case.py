from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class DataSourceSummaryResponse(BaseModel):
    type: str
    recordCount: int

class CaseResponse(BaseModel):
    caseNumber: str
    createdAt: datetime
    investigatorId: str
    deviceSerial: str
    dataSources: List[DataSourceSummaryResponse]

class CaseSummary(BaseModel):
    caseNumber: str
    createdAt: datetime
    investigatorId: str
    deviceSerial: str
