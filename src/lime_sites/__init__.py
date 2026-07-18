"""Official Python SDK for LIME site backends."""

from lime_sites._errors import (
    ApiError,
    AuthenticationError,
    InvalidPassportError,
    LimeError,
    RateLimitError,
    RequestExpiredError,
)
from lime_sites._site import LimeSite
from lime_sites._types import (
    BindingRequestResult,
    LoginRequestResult,
    LoginResult,
    PassportVerificationResult,
)

__version__ = "1.2.0"

__all__ = [
    "ApiError",
    "AuthenticationError",
    "BindingRequestResult",
    "InvalidPassportError",
    "LimeError",
    "LimeSite",
    "LoginRequestResult",
    "LoginResult",
    "PassportVerificationResult",
    "RateLimitError",
    "RequestExpiredError",
    "__version__",
]
