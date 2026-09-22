from typing import Optional

from pydantic import BaseModel, Field


class CompanyAdminCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str
    phone: Optional[str] = None
