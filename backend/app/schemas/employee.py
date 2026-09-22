from typing import Optional

from pydantic import BaseModel, Field


class EmployeeCreateRequest(BaseModel):
    employee_code: str
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    joining_date: Optional[str] = None
    employment_type: Optional[str] = None
    department_id: Optional[str] = None
    designation_id: Optional[str] = None
    manager_id: Optional[str] = None
    work_location: Optional[str] = None
    status: Optional[str] = None


class EmployeeUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    joining_date: Optional[str] = None
    employment_type: Optional[str] = None
    department_id: Optional[str] = None
    designation_id: Optional[str] = None
    manager_id: Optional[str] = None
    work_location: Optional[str] = None
    status: Optional[str] = None
