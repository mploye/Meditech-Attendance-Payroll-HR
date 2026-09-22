import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from connector.config import ConnectorConfig
from connector.essl_client import LocalESSLClient
from connector.logger import get_logger
from connector.queue import FileOutboxQueue

logger = get_logger()


class SyncWorker(threading.Thread):
    """Poll local eSSL transactions, queue them, and upload to the cloud API."""

    def __init__(
        self,
        config: ConnectorConfig,
        client: Optional[LocalESSLClient] = None,
        queue: Optional[FileOutboxQueue] = None,
    ) -> None:
        super().__init__(name="connector-sync-worker", daemon=True)
        self.config = config
        self.client = client or LocalESSLClient(config)
        self.queue = queue or FileOutboxQueue(config.queue_dir)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Signal the worker loop to stop."""
        self._stop_event.set()

    def run(self) -> None:
        logger.info("Connector sync worker started")
        while not self._stop_event.is_set():
            try:
                self._run_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Sync cycle failed: {}", exc)
            self._stop_event.wait(self.config.poll_interval_seconds)
        logger.info("Connector sync worker stopped")

    def _run_once(self) -> None:
        now = datetime.now(timezone.utc)
        from_ = now - timedelta(seconds=self.config.poll_interval_seconds)
        transactions = self.client.fetch_transactions(from_, now)
        if not transactions:
            return
        logger.info("Fetched {} transactions", len(transactions))
        pending = [self.queue.push(tx) for tx in transactions]
        uploaded = self._upload_with_retry(pending)
        self.queue.mark_synced(uploaded)

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _upload(self, records: list[dict[str, Any]]) -> httpx.Response:
        url = self.config.cloud_url.rstrip("/") + "/api/v1/device-sync/transactions"
        headers = {"X-API-Key": self.config.connector_api_key, "Content-Type": "application/json"}
        return httpx.post(url, json=records, headers=headers, timeout=60)

    def _upload_with_retry(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        response = self._upload(records)
        response.raise_for_status()
        logger.info("Uploaded {} records to {}", len(records), self.config.cloud_url)
        return records