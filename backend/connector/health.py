import os
from typing import Any

from connector.config import ConnectorConfig
from connector.essl_client import LocalESSLClient


def check_health(config: ConnectorConfig) -> dict[str, Any]:
    """Non-FastAPI health check for the connector process."""
    essl = LocalESSLClient(config).test_connection()
    queue_writable = os.access(config.queue_dir, os.W_OK)
    checks = {
        "essl_local": essl,
        "queue_dir_writable": queue_writable,
        "queue_dir": config.queue_dir,
    }
    healthy = bool(essl.get("success")) and queue_writable
    return {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
    }