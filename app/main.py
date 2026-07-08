from app.api.api_client import DhanAPI
from app.config.logging_config import get_logger
from app.constants.app_info import (
    APP_NAME,
    APP_VERSION,
)

logger = get_logger()


def banner():

    logger.info("=" * 60)
    logger.info(f"{APP_NAME}  v{APP_VERSION}")
    logger.info("=" * 60)


def main():

    banner()

    api = DhanAPI()

    api.test_connection()


if __name__ == "__main__":
    main()