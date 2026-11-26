"""Test configuration.

Catalogue tests run against a real PostgreSQL database, because the features
under test (native enums, NUMERIC money, correlated EXISTS variant filters,
case-insensitive search) do not behave identically on SQLite. A dedicated
`..._test` database is created on the same server and each test runs inside a
transaction that is rolled back afterwards, so tests never see each other's rows.

If no PostgreSQL server is reachable, the database-backed tests are skipped with
a clear reason rather than reported as passing.
"""

import os
import uuid
from collections.abc import Iterator

import pytest

# Must be set before `app.*` is imported, since settings are read at import time.
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://rgthrifting:dev_local_password@127.0.0.1:5433/rg_thrifting_hub_test"
)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# At least 32 bytes, which is the minimum HS256 key length RFC 7518 recommends.
os.environ.setdefault("SECRET_KEY", "test-application-secret-0123456789abcdef")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-signing-secret-0123456789abcdef")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.user import User  # noqa: E402


def _ensure_test_database() -> str | None:
    """Create the test database if needed. Returns a skip reason on failure."""
    url = make_url(TEST_DATABASE_URL)
    admin_url = url.set(database="postgres")
    try:
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
        admin_engine.dispose()
    except SQLAlchemyError as exc:
        return f"PostgreSQL is not reachable at {admin_url.render_as_string(hide_password=True)}: {exc}"
    return None


_SKIP_REASON = _ensure_test_database()


@pytest.fixture(scope="session")
def engine():
    if _SKIP_REASON:
        pytest.skip(_SKIP_REASON, allow_module_level=True)
    test_engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:
    """A session whose writes are always rolled back.

    `join_transaction_mode="create_savepoint"` turns the service layer's
    `commit()` calls into savepoint releases, so production code can commit
    normally while the outer transaction still discards everything.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator["TestClient"]:
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------ account helpers
def unique_email(prefix: str) -> str:
    # example.com, not .test: email-validator rejects special-use TLDs.
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def create_user(db: Session, role: UserRole, password: str = "TestPass!2026") -> tuple[User, str]:
    """Insert a user directly, since registration only ever creates customers."""
    from app.core.security import hash_password

    user = User(
        email=unique_email(role.value.lower()),
        password_hash=hash_password(password),
        first_name="Test",
        last_name=role.value.title(),
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, password


def sign_in(client: "TestClient", email: str, password: str) -> None:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


# Credentials fixtures are split from the client fixtures so a test can use both
# the signed-in client and the User row behind it, and be sure they match.
@pytest.fixture
def admin_credentials(db: Session):
    return create_user(db, UserRole.ADMIN)


@pytest.fixture
def staff_credentials(db: Session):
    return create_user(db, UserRole.STAFF)


@pytest.fixture
def customer_credentials(db: Session):
    return create_user(db, UserRole.CUSTOMER)


@pytest.fixture
def admin_user(admin_credentials) -> User:
    return admin_credentials[0]


@pytest.fixture
def customer_user(customer_credentials) -> User:
    return customer_credentials[0]


@pytest.fixture
def admin_client(client, admin_credentials):
    user, password = admin_credentials
    sign_in(client, user.email, password)
    return client


@pytest.fixture
def staff_client(client, staff_credentials):
    user, password = staff_credentials
    sign_in(client, user.email, password)
    return client


@pytest.fixture
def customer_client(client, customer_credentials):
    user, password = customer_credentials
    sign_in(client, user.email, password)
    return client
