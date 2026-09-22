from typing import Optional

from pydantic import BaseModel, Field


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)
