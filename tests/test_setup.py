import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, required: bool = True) -> str | None:
    value = os.getenv(name)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def test_postgres() -> None:
    import psycopg2

    host = _env("POSTGRES_HOST")
    database = _env("POSTGRES_DB")
    user = _env("POSTGRES_USER")
    password = _env("POSTGRES_PASSWORD")
    port = _env("POSTGRES_PORT", required=False) or "5432"
    sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")

    connection = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port,
        sslmode=sslmode,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"✅ PostgreSQL connected: {version[0]}")
    finally:
        connection.close()


def test_azure_storage() -> None:
    from azure.storage.blob import BlobServiceClient

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        account_name = _env("AZURE_STORAGE_ACCOUNT")
        account_key = _env("AZURE_STORAGE_ACCOUNT_KEY")
        connection_string = (
            "DefaultEndpointsProtocol=https;"
            f"AccountName={account_name};"
            f"AccountKey={account_key};"
            "EndpointSuffix=core.windows.net"
        )

    client = BlobServiceClient.from_connection_string(connection_string)
    client.get_account_information()
    print("✅ Azure Storage connected")


def test_earth_engine() -> None:
    import ee

    credentials_path = os.getenv("GOOGLE_EARTH_ENGINE_CREDENTIALS")
    project = os.getenv("GEE_PROJECT")

    if credentials_path and os.path.isfile(credentials_path):
        credentials = ee.ServiceAccountCredentials(None, credentials_path)
        ee.Initialize(credentials=credentials, project=project)
    else:
        ee.Initialize(project=project)

    _ = ee.Number(1).getInfo()
    print("✅ Google Earth Engine authenticated")


def _run_test(name: str, fn) -> bool:
    try:
        fn()
        return True
    except Exception as exc:
        print(f"❌ {name} error: {exc}")
        return False


if __name__ == "__main__":
    checks = [
        ("PostgreSQL", test_postgres),
        ("Azure Storage", test_azure_storage),
        ("Earth Engine", test_earth_engine),
    ]

    results = [_run_test(name, fn) for name, fn in checks]
    if not all(results):
        sys.exit(1)

    print("✅ All setup checks passed")
