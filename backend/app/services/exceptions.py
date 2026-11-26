"""Domain errors raised by services and translated to HTTP status codes at the API edge."""


class ServiceError(Exception):
    """Base class for expected, user-correctable service failures."""


class NotFoundError(ServiceError):
    """A referenced record does not exist."""


class ConflictError(ServiceError):
    """The request violates a uniqueness rule (duplicate slug, SKU, or email)."""


class InvalidRequestError(ServiceError):
    """The request is well-formed but semantically invalid."""


class AuthenticationError(ServiceError):
    """Credentials are missing or wrong."""
