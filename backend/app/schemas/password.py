from typing import Optional

from pydantic import BaseModel, Field


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)
