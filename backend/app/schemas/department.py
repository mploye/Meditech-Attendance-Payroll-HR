from typing import Optional

from pydantic import BaseModel, Field


class DepartmentCreateRequest(BaseModel):
    name: str
    code: Optional[str] = None
    manager_id: Optional[str] = None
    description: Optional[str] = None


class DepartmentUpdateRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    manager_id: Optional[str] = None
    description: Optional[str] = None
