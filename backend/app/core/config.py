from decimal import Decimal
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Both locations are tried so the app works when started from the repository
    # root and from backend/. Missing files are ignored, and real environment
    # variables always win, which is how the Docker containers are configured.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )
    environment: str = "development"
    database_url: str
    secret_key: str
    jwt_secret_key: str
    # Keep an active staff work session alive through a normal workday. The
    # cookie remains HTTP-only and Secure in production; deployments can still
    # override this with ACCESS_TOKEN_EXPIRE_MINUTES.
    access_token_expire_minutes: int = 30
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Session cookie carrying the access token. HTTP-only always; Secure is
    # forced on in production so the token cannot travel over plain HTTP.
    access_cookie_name: str = "rg_access_token"
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    # ---- commerce -------------------------------------------------------
    # Delivery pricing lives here so it is configurable per environment and is
    # never duplicated in frontend code. The storefront reads these values from
    # the checkout-configuration endpoint.
    currency_code: str = "PKR"
    # Business timezone. Order numbers carry the local trading date, so an order
    # taken late in the evening is not stamped with the previous UTC day.
    business_timezone: str = "Asia/Karachi"
    standard_delivery_charge: Decimal = Decimal("250.00")
    # Orders at or above this subtotal ship free. Set to 0 to disable.
    free_delivery_threshold: Decimal = Decimal("4000.00")
    # Maximum units of a single variant one customer may buy in one order.
    max_quantity_per_item: int = 10
    item_code_prefix: str = "JS"

    # Public base URL of the storefront, used to build gateway return/cancel
    # URLs and links inside notification emails.
    frontend_base_url: str = "http://localhost:3000"

    # ---- payment gateways ----------------------------------------------
    # A provider counts as configured only when all of its credentials are
    # present. Absent credentials mean the provider refuses to start a payment
    # rather than silently pretending to work.
    payfast_merchant_id: str | None = None
    payfast_secured_key: str | None = None
    payfast_api_url: str | None = None

    safepay_api_key: str | None = None
    safepay_api_url: str | None = None

    jazzcash_merchant_id: str | None = None
    jazzcash_password: str | None = None
    jazzcash_integrity_salt: str | None = None

    easypaisa_store_id: str | None = None
    easypaisa_hash_key: str | None = None
    # Manual mobile-wallet transfers; no gateway API is used.
    jazzcash_number: str | None = None
    easypaisa_number: str | None = None
    payment_whatsapp_number: str | None = None

    # ---- email ----------------------------------------------------------
    # Provider is chosen by name so a transport can be swapped without code
    # changes. "log" writes to the application log and sends nothing.
    email_provider: Literal["log", "smtp"] = "log"
    email_from_name: str = "RG Thrifting Hub"
    email_from_address: str = "no-reply@rgthriftinghub.pk"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True

    # ---- whatsapp -------------------------------------------------------
    whatsapp_provider: Literal["log"] | str = "log"
    whatsapp_api_key: str | None = None
    whatsapp_api_url: str | None = None
    whatsapp_sender: str | None = None

    # ---- courier --------------------------------------------------------
    # "manual" means staff enter tracking numbers from the courier's portal.
    courier_provider: str = "manual"
    courier_api_key: str | None = None
    courier_api_url: str | None = None

    @field_validator("standard_delivery_charge", "free_delivery_threshold")
    @classmethod
    def reject_negative_money(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("must not be negative")
        return value

    @model_validator(mode="after")
    def require_smtp_credentials_when_selected(self) -> "Settings":
        """Fail fast rather than silently dropping mail.

        Selecting the SMTP transport without a host would otherwise look like a
        working email setup while every message vanished.
        """
        if self.email_provider == "smtp" and not self.smtp_host:
            raise ValueError("EMAIL_PROVIDER=smtp requires SMTP_HOST to be set")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def reject_wildcard_cors_in_production(self) -> "Settings":
        if self.is_production and "*" in self.cors_origins:
            raise ValueError(
                "CORS_ORIGINS must list explicit frontend origins in production; '*' is not allowed."
            )
        return self

    @model_validator(mode="after")
    def require_secure_cookie_pairing(self) -> "Settings":
        # SameSite=None cookies are ignored by browsers unless also Secure.
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError(
                "COOKIE_SAMESITE=none requires a Secure cookie, which is only enabled when "
                "ENVIRONMENT=production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
