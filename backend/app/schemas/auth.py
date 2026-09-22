from typing import Optional

from pydantic import BaseModel, Field


class RegisterSuperAdminRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str
