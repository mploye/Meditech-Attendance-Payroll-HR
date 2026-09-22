from sqlalchemy.orm import Session

from integrations.essl.client import ESSLClient
from integrations.essl.config import ESSLConfiguration
from integrations.essl.mock import MockESSLClient
from integrations.essl.service import ESSLService


def get_essl_service(db: Session, company_id: str) -> ESSLService:
    """Build an ESSLService for the company, using its DB config or global settings."""
    essl_db = ESSLService.get_essl_config_for_company(db, company_id)
    config = ESSLConfiguration.from_db_record(essl_db)
    return ESSLService(db=db, config=config)


__all__ = [
    "ESSLClient",
    "ESSLService",
    "MockESSLClient",
    "ESSLConfiguration",
    "get_essl_service",
]