from pydantic import BaseModel


class ChainOfCustodyResponse(BaseModel):
    id: str
    timestamp: int
    investigatorId: str
    actionType: str
    artifactId: str
    evidenceHash: str
    description: str
