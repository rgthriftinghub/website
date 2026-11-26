import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.exceptions import (
    AuthenticationError,
    ConflictError,
    InvalidRequestError,
    NotFoundError,
)

settings = get_settings()


logger = logging.getLogger("app.startup")

# How often to re-scan inventory for low/out-of-stock alerts. Alerts are deduped
# per variant and condition, so a frequent scan is cheap and idempotent.
STOCK_SCAN_INTERVAL_SECONDS = 15 * 60


async def _stock_alert_loop() -> None:
    """Periodically raise low and out-of-stock alerts.

    A plain asyncio task rather than Celery or a cron container: the work is one
    indexed query and a handful of inserts, and adding a broker to run it would be
    infrastructure out of all proportion to the job.

    Every iteration is wrapped so a transient database error logs and retries on the
    next tick instead of killing the loop.
    """
    from app.db.session import SessionLocal
    from app.services.activity import scan_stock_alerts

    while True:
        try:
            await asyncio.sleep(STOCK_SCAN_INTERVAL_SECONDS)
            # Runs in a worker thread because the session is synchronous; blocking
            # the event loop here would stall every request.
            def _scan() -> dict[str, int]:
                db = SessionLocal()
                try:
                    return scan_stock_alerts(db)
                finally:
                    db.close()

            raised = await asyncio.to_thread(_scan)
            if raised.get("low_stock") or raised.get("out_of_stock"):
                logger.info(
                    "stock alerts raised: %s low, %s out of stock",
                    raised.get("low_stock", 0),
                    raised.get("out_of_stock", 0),
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - a bad tick must not end the loop
            logger.exception("Stock alert scan failed; will retry on the next interval")


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_stock_alert_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="RG Thrifting Hub API",
    version="0.2.0",
    description="Catalogue and account API for RG Thrifting Hub.",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Product uploads live beside (not inside) the replaceable application package,
# so ordinary backend deployments retain them.
PRODUCT_MEDIA_DIR = Path(__file__).resolve().parents[1] / "uploads" / "products"
PRODUCT_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/v1/media/products", StaticFiles(directory=PRODUCT_MEDIA_DIR), name="product-media")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if settings.is_production and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Required so the browser sends the HTTP-only session cookie cross-origin.
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# Domain errors are translated centrally, so endpoints stay free of repetitive
# try/except blocks and every route reports the same status code for the same
# class of failure.
_ERROR_STATUS: list[tuple[type[Exception], int]] = [
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (InvalidRequestError, status.HTTP_400_BAD_REQUEST),
    (AuthenticationError, status.HTTP_401_UNAUTHORIZED),
]


def _register_error_handler(exc_type: type[Exception], status_code: int) -> None:
    @app.exception_handler(exc_type)
    async def handler(_: Request, exc: Exception) -> JSONResponse:  # noqa: ANN202
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})


for _exc_type, _status_code in _ERROR_STATUS:
    _register_error_handler(_exc_type, _status_code)

app.include_router(api_router, prefix="/api/v1")
