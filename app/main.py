from app.api.api_client import DhanAPI
from app.constants.app_info import (
    APP_NAME,
    APP_VERSION,
)


def banner():

    print("=" * 60)
    print(f"{APP_NAME}  v{APP_VERSION}")
    print("=" * 60)


def main():

    banner()

    api = DhanAPI()

    api.test_connection()


if __name__ == "__main__":
    main()