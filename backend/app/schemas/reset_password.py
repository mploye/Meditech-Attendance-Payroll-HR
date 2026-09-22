from typing import Optional

from pydantic import BaseModel, Field


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)
