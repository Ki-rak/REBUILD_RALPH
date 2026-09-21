from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import httpx


class AuthError(RuntimeError):
    """A sanitized authentication failure safe to expose through the API."""


class AuthUnavailableError(AuthError):
    """Supabase Auth could not be reached or returned an invalid response."""


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None = None


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    user: AuthUser


class SupabaseAuth:
    def __init__(
        self,
        url: str,
        publishable_key: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 20.0,
    ) -> None:
        if not url or not publishable_key:
            raise ValueError("Supabase URL and publishable key are required")
        self._url = url.rstrip("/")
        self._publishable_key = publishable_key
        self._client = client or httpx.Client()
        self._timeout = timeout

    def login(self, email: str, password: str) -> AuthSession:
        if not email or not password:
            raise AuthError("email and password are required")
        response = self._request(
            "POST",
            "/auth/v1/token",
            params={"grant_type": "password"},
            json={"email": email, "password": password},
            failure_message="authentication failed",
        )
        return self._session(response)

    def refresh(self, refresh_token: str) -> AuthSession:
        if not refresh_token:
            raise AuthError("refresh token required")
        response = self._request(
            "POST",
            "/auth/v1/token",
            params={"grant_type": "refresh_token"},
            json={"refresh_token": refresh_token},
            failure_message="session refresh failed",
        )
        return self._session(response)

    def close(self) -> None:
        self._client.close()

    def get_user(self, token: str) -> AuthUser:
        if not token:
            raise AuthError("authentication required")
        response = self._request(
            "GET",
            "/auth/v1/user",
            token=token,
            failure_message="authentication required",
        )
        return self._user(self._object(response, "authentication service returned an invalid response"))

    def logout(self, token: str) -> None:
        if not token:
            raise AuthError("authentication required")
        self._request(
            "POST",
            "/auth/v1/logout",
            token=token,
            failure_message="logout failed",
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        failure_message: str,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = {"apikey": self._publishable_key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self._client.request(
                method,
                f"{self._url}{path}",
                headers=headers,
                timeout=self._timeout,
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise AuthUnavailableError("authentication service unavailable") from exc
        if response.status_code >= 400:
            if response.status_code >= 500:
                raise AuthUnavailableError("authentication service unavailable")
            raise AuthError(failure_message)
        return response

    @classmethod
    def _session(cls, response: httpx.Response) -> AuthSession:
        message = "authentication service returned an invalid response"
        data = cls._object(response, message)
        user = cls._user(data.get("user"))
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in")
        token_type = data.get("token_type") or "bearer"
        if (
            not isinstance(access_token, str)
            or not isinstance(refresh_token, str)
            or type(expires_in) is not int
            or expires_in < 0
            or not isinstance(token_type, str)
        ):
            raise AuthUnavailableError(message)
        return AuthSession(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type=token_type,
            user=user,
        )
    @staticmethod
    def _object(response: httpx.Response, message: str) -> Mapping[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise AuthUnavailableError(message) from exc
        if not isinstance(data, Mapping):
            raise AuthUnavailableError(message)
        return data

    @staticmethod
    def _user(data: object) -> AuthUser:
        if not isinstance(data, Mapping):
            raise AuthUnavailableError("authentication service returned an invalid response")
        user_id = data.get("id")
        email = data.get("email")
        if not isinstance(user_id, str) or not user_id:
            raise AuthUnavailableError("authentication service returned an invalid response")
        return AuthUser(id=user_id, email=email if isinstance(email, str) else None)