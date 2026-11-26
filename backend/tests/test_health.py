import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import app
from app.core.config import Settings


class HealthyDatabase:
    def execute(self, *_: object) -> None:
        return None

    def close(self) -> None:
        return None


class UnavailableDatabase(HealthyDatabase):
    def execute(self, *_: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_endpoint_confirms_api_and_database_connectivity() -> None:
    app.dependency_overrides[get_db] = lambda: HealthyDatabase()
    try:
        response = TestClient(app).get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_returns_service_unavailable_when_database_is_down() -> None:
    app.dependency_overrides[get_db] = lambda: UnavailableDatabase()
    try:
        response = TestClient(app).get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["detail"] == "Database connection is unavailable"


def test_settings_parse_comma_separated_cors_origins() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        secret_key="test-application-secret",
        jwt_secret_key="test-jwt-secret",
        cors_origins="http://localhost:3000,http://localhost:3001",
    )

    assert settings.cors_origins == ["http://localhost:3000", "http://localhost:3001"]


def test_production_rejects_wildcard_cors_origin() -> None:
    with pytest.raises(ValidationError, match="explicit frontend origins"):
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            secret_key="test-application-secret",
            jwt_secret_key="test-jwt-secret",
            environment="production",
            cors_origins="*",
        )
