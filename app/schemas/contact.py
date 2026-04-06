from pydantic import BaseModel

class ContactResponse(BaseModel):
    id: str
    phoneNumber: str
    displayName: str
