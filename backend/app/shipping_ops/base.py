"""Courier provider contract.

**Status: only the MANUAL provider is implemented.** No courier API integration
exists, because building one requires the courier's official API documentation
and merchant credentials — endpoint URLs, authentication scheme, consignment
payload, label format, and tracking response shape. None of that is available in
this repository, and inventing it would produce shipments that look booked but
were never lodged with anyone.

The MANUAL provider is a complete, working implementation of the real-world
process most Pakistani sellers use today: staff book the consignment in the
courier's own portal and record the tracking number here. Nothing is faked — a
tracking number exists only because a human entered one.

Adding a real courier means writing one subclass; the shipment record, admin
screens, customer tracking and status history already work through this contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.models.enums import CourierProvider, ShippingStatus
from app.services.exceptions import ServiceError

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.shipping import Shipment


class CourierError(ServiceError):
    """Base class for courier-level failures."""


class CourierNotConfigured(CourierError):
    """The courier integration is not available."""


@dataclass(slots=True)
class ShipmentBooking:
    """What a courier returns when a consignment is created."""

    tracking_number: str | None = None
    shipment_id: str | None = None
    label_url: str | None = None
    tracking_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrackingUpdate:
    """A courier's current view of a consignment."""

    status: ShippingStatus
    description: str | None = None
    location: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class BaseCourierProvider(ABC):
    code: CourierProvider
    display_name: str
    #: True when this provider talks to a real API rather than recording manual input.
    is_automated: bool = False

    @property
    @abstractmethod
    def is_configured(self) -> bool: ...

    @property
    def configuration_hint(self) -> str:
        return "No additional configuration required."

    @abstractmethod
    def create_shipment(self, order: Order, shipment: Shipment) -> ShipmentBooking: ...

    def cancel_shipment(self, shipment: Shipment) -> bool:
        raise CourierNotConfigured(
            f"{self.display_name} shipments are cancelled in the courier's own portal."
        )

    def get_tracking(self, shipment: Shipment) -> TrackingUpdate:
        raise CourierNotConfigured(
            f"{self.display_name} does not provide automated tracking here."
        )

    def get_label(self, shipment: Shipment) -> str | None:
        """URL of a printable label, when the courier supplies one."""
        return shipment.label_url


class ManualCourierProvider(BaseCourierProvider):
    """Staff-operated courier handling.

    A consignment is booked in the courier's portal by a person, who then records
    the tracking number here. This provider therefore never invents identifiers:
    `create_shipment` opens an empty record for staff to fill in.
    """

    code = CourierProvider.MANUAL
    display_name = "Manual (staff-entered tracking)"
    is_automated = False

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def configuration_hint(self) -> str:
        return (
            "Staff book the consignment with the courier and enter the tracking "
            "number on the order. No API credentials required."
        )

    def create_shipment(self, order: Order, shipment: Shipment) -> ShipmentBooking:
        # Deliberately empty: a tracking number must come from the courier, via a person.
        return ShipmentBooking()


class UnconfiguredCourierProvider(BaseCourierProvider):
    """A named courier with no integration built.

    Selecting one records *which* courier is carrying the parcel — useful on its
    own — while every API operation refuses rather than pretending.
    """

    required_settings: tuple[str, ...] = ("COURIER_API_KEY", "COURIER_API_URL")
    integration_checklist: tuple[str, ...] = (
        "Merchant/shipper account and API credentials from the courier",
        "Official API documentation: authentication, booking, tracking, label endpoints",
        "Consignment payload field names and address format requirements",
        "Tracking status vocabulary, to map onto ShippingStatus",
        "Sandbox or test account for end-to-end verification",
    )
    is_automated = False

    @property
    def is_configured(self) -> bool:
        return False

    @property
    def configuration_hint(self) -> str:
        return (
            f"{self.display_name} API integration is not implemented. Tracking numbers "
            "can still be entered manually against this courier."
        )

    def create_shipment(self, order: Order, shipment: Shipment) -> ShipmentBooking:
        # Recording the courier is allowed; calling their API is not.
        return ShipmentBooking()


class TCSProvider(UnconfiguredCourierProvider):
    code = CourierProvider.TCS
    display_name = "TCS"


class LeopardsProvider(UnconfiguredCourierProvider):
    code = CourierProvider.LEOPARDS
    display_name = "Leopards Courier"


class MPProvider(UnconfiguredCourierProvider):
    code = CourierProvider.MP
    display_name = "M&P"


class TraxProvider(UnconfiguredCourierProvider):
    code = CourierProvider.TRAX
    display_name = "Trax"


class PostExProvider(UnconfiguredCourierProvider):
    code = CourierProvider.POSTEX
    display_name = "PostEx"
