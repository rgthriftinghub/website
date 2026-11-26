"""Business-local time.

Order numbers and printed documents must agree on what "today" means. Both go
through here so an order taken at 2am in Karachi is stamped with that trading
day, not the previous UTC one.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings


def business_zone() -> ZoneInfo:
    """The configured business timezone, falling back to UTC if unresolvable.

    An unknown timezone name must never stop an order being placed, so this
    degrades rather than raising.
    """
    try:
        return ZoneInfo(get_settings().business_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC") if _utc_available() else UTC  # type: ignore[return-value]


def _utc_available() -> bool:
    try:
        ZoneInfo("UTC")
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def utc_now() -> datetime:
    """Timezone-aware current UTC instant.

    Everything time-sensitive (sale windows, report boundaries) goes through this
    one function so comparisons are never naive-vs-aware.
    """
    return datetime.now(UTC)


def to_business_time(moment: datetime) -> datetime:
    """Convert an aware (or assumed-UTC) timestamp into business-local time."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    try:
        return moment.astimezone(business_zone())
    except Exception:  # noqa: BLE001 - never let formatting break a response
        return moment


def business_date_stamp(moment: datetime | None = None) -> str:
    """`YYYYMMDD` for the business's current trading day."""
    return to_business_time(moment or datetime.now(UTC)).strftime("%Y%m%d")
