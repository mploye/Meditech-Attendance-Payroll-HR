from typing import Optional

from pydantic import BaseModel, Field


class AdminUserCreateRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str
    role: str = "COMPANY_ADMIN"
    phone: Optional[str] = None
