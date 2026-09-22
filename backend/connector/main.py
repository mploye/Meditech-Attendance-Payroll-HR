import argparse

from connector.config import ConnectorConfig
from connector.health import check_health
from connector.logger import get_logger
from connector.sync_worker import SyncWorker


def main() -> None:
    parser = argparse.ArgumentParser(description="ESSL local connector")
    parser.add_argument("--once", action="store_true", help="Run one sync cycle then exit")
    args = parser.parse_args()

    logger = get_logger()
    config = ConnectorConfig.from_env()
    health = check_health(config)
    logger.info("Connector config: {}", config)
    logger.info("Health check: {}", health)

    worker = SyncWorker(config)
    worker.start()
    if args.once:
        worker._run_once()
        worker.stop()
    try:
        while worker.is_alive():
            worker.join(timeout=1)
    except KeyboardInterrupt:
        logger.info("Interrupted, stopping worker")
        worker.stop()
        worker.join(timeout=5)
    logger.info("Connector exited")


if __name__ == "__main__":
    main()