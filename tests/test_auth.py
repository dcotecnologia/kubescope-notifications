import pytest
from kubescope.utils.errors import is_auth_error as the_app

from kubescope.notifications.auth import is_auth_error

SIGN_IN = [
    "exec: process returned 255. aws: Token has expired and refresh failed",
    "Error loading SSO token: Token for sso does not exist",
    "Unauthorized",
    "You must be logged in to the server",
    "ExpiredToken: the security token is expired",
    "Please run: gcloud auth login",
    "AADSTS700082: the refresh token expired",
    "Your credentials expired, sign in again",
    "interactive authentication is needed",
]
OTHER = [
    "dial tcp: i/o timeout",
    "connection refused",
    "the server could not find the requested resource",
    "forbidden: cannot list resource pods",
    "",
]


@pytest.mark.parametrize("message", SIGN_IN)
def test_a_failure_to_sign_in_is_told_from_the_rest(message: str) -> None:
    assert is_auth_error(message)


@pytest.mark.parametrize("message", OTHER)
def test_another_failure_is_not_taken_for_one(message: str) -> None:
    assert not is_auth_error(message)


@pytest.mark.parametrize("message", [*SIGN_IN, *OTHER])
def test_it_says_what_the_app_says(message: str) -> None:
    """The banner of the app and the notifications must agree on what a failed
    sign-in is, or one says it and the other lists it."""
    assert is_auth_error(message) == the_app(message)
