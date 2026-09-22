from typing import Optional

from pydantic import BaseModel, Field


class CompanySettingsUpdateRequest(BaseModel):
    lop_policy: Optional[str] = None
    statutory_state: Optional[str] = None
    timezone: Optional[str] = None
    overtime_enabled: Optional[bool] = None
