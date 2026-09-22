import os
from dataclasses import dataclass, field


@dataclass
class ConnectorConfig:
    """Environment-driven configuration for the local connector."""

    cloud_url: str = field(default_factory=lambda: os.environ.get("CLOUD_URL", "http://127.0.0.1:8000"))
    connector_api_key: str = field(default_factory=lambda: os.environ.get("CONNECTOR_API_KEY", "CHANGE_ME_connector_key"))
    essl_local_base_url: str = field(
        default_factory=lambda: os.environ.get("ESSL_LOCAL_BASE_URL", "http://127.0.0.1:8080/portal/api/essl/etimetracklite")
    )
    essl_local_username: str = field(default_factory=lambda: os.environ.get("ESSL_LOCAL_USERNAME", ""))
    essl_local_password: str = field(default_factory=lambda: os.environ.get("ESSL_LOCAL_PASSWORD", ""))
    poll_interval_seconds: int = field(
        default_factory=lambda: int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
    )
    queue_dir: str = field(default_factory=lambda: os.environ.get("QUEUE_DIR", "./connector_queue"))
    timeout_seconds: int = field(default_factory=lambda: int(os.environ.get("ESSL_LOCAL_TIMEOUT_SECONDS", "30")))
    upload_retry_attempts: int = field(default_factory=lambda: int(os.environ.get("UPLOAD_RETRY_ATTEMPTS", "5")))

    @classmethod
    def from_env(cls) -> "ConnectorConfig":
        """Build a config from the process environment."""
        return cls()