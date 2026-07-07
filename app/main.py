from app.api.api_client import DhanAPI


def main():

    print("=" * 60)
    print("DHAN OPTION DOWNLOADER")
    print("=" * 60)

    api = DhanAPI()
    api.test_connection()


if __name__ == "__main__":
    main()