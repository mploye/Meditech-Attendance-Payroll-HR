from typing import Optional

from pydantic import BaseModel, Field


class ESSLConfigUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    base_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    company_short_name: Optional[str] = None
    timeout_sec: Optional[int] = None
    sync_interval_sec: Optional[int] = None
    capabilities: Optional[list[str]] = None
