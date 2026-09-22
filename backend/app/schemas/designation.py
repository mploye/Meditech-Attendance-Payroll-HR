from typing import Optional

from pydantic import BaseModel, Field


class DesignationCreateRequest(BaseModel):
    name: str
    code: Optional[str] = None
    level: Optional[int] = None
    description: Optional[str] = None


class DesignationUpdateRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    level: Optional[int] = None
    description: Optional[str] = None
