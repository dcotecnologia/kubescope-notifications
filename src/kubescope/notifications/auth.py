"""Telling a failure to sign in from the other failures of a context.

KubeScope already says "you are not signed in" in its banner, so the
notifications leave those out. The words are the ones of the app (`is_auth_error`
of `kubescope.utils.errors`); a test keeps the two together.
"""

_AUTH_WORDS = (
    "unauthorized",
    "you must be logged in",
    "token has expired",
    "sso session",
    "error loading sso token",
    "unable to locate credentials",
    "invalidclienttokenid",
    "security token included in the request",
    "signaturedoesnotmatch",
    "expiredtoken",
    "gcloud auth login",  # Google Cloud
    "reauthentication",
    "invalid_grant",
    "could not automatically determine credentials",
    "aadsts",  # Azure AD error codes
    "az login",
    "interactive authentication is needed",
)


def is_auth_error(message: str) -> bool:
    """Whether the failure means the person has to sign in again."""
    lowered = message.lower()
    return any(word in lowered for word in _AUTH_WORDS) or (
        "expired" in lowered and ("credential" in lowered or "token" in lowered)
    )
