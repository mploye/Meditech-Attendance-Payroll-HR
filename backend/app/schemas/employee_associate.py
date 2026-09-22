from typing import Optional

from pydantic import BaseModel, Field


class EmployeeAssociateUserRequest(BaseModel):
    email: str
    full_name: Optional[str] = None
    password: Optional[str] = None
