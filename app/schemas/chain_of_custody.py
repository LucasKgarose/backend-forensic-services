from pydantic import BaseModel
from typing import List

class ChainOfCustodyResponse(BaseModel):
    id: str
    timestamp: int
    investigatorId: str
    actionType: str
    artifactId: str
    description: str
